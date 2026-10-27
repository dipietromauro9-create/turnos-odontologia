"""Acceso a datos compartido: repositorio tenant-scoped y unidad de trabajo (RN-GL-02)."""

from __future__ import annotations

import uuid
from types import TracebackType
from typing import Any

from sqlalchemy import select

from app.db.models import TenantMixin
from app.db.session import (
    TenantIsolationError,
    TenantSession,
    get_tenant_session_factory,
    require_tenant,
)


class TenantSessionRequiredError(RuntimeError):
    """El repositorio solo acepta sesiones con tenant asociado (R3)."""


class BaseRepository[T]:
    """Repositorio genérico: no puede construirse sin sesión tenant-scoped."""

    def __init__(self, session: TenantSession, modelo: type[T]) -> None:
        if not isinstance(session, TenantSession):
            raise TenantSessionRequiredError(
                "BaseRepository requiere una TenantSession (el filtro de tenant es obligatorio)"
            )
        self._session = session
        self._modelo = modelo

    @property
    def tenant_id(self) -> uuid.UUID:
        return self._session.tenant_id

    def get(self, entidad_id: uuid.UUID) -> T | None:
        stmt = select(self._modelo).where(self._modelo.id == entidad_id)
        return self._session.execute(stmt).scalar_one_or_none()

    def list(self, **filtros: Any) -> list[T]:
        stmt = select(self._modelo)
        for campo, valor in filtros.items():
            stmt = stmt.where(getattr(self._modelo, campo) == valor)
        return list(self._session.execute(stmt).scalars().all())

    def add(self, entidad: T) -> T:
        if not isinstance(entidad, TenantMixin):
            raise TenantIsolationError("Solo se persisten entidades con TenantMixin")
        entidad.tenant_id = self._session.tenant_id
        self._session.add(entidad)
        self._session.flush()
        return entidad

    def update(self, entidad_id: uuid.UUID, **cambios: Any) -> T | None:
        if "tenant_id" in cambios:
            raise TenantIsolationError("El tenant_id no puede modificarse desde el repositorio")
        entidad = self.get(entidad_id)
        if entidad is None:
            return None
        for campo, valor in cambios.items():
            setattr(entidad, campo, valor)
        self._session.flush()
        return entidad

    def delete(self, entidad_id: uuid.UUID) -> bool:
        entidad = self.get(entidad_id)
        if entidad is None:
            return False
        self._session.delete(entidad)
        self._session.flush()
        return True


class UnitOfWork:
    """Una transacción por operación de negocio; commit único al cerrar sin error."""

    def __init__(self) -> None:
        contexto = require_tenant()
        self._tenant_id = contexto.tenant_id
        self._session = get_tenant_session_factory()(tenant_id=self._tenant_id)

    @property
    def tenant_id(self) -> uuid.UUID:
        return self._tenant_id

    @property
    def session(self) -> TenantSession:
        return self._session

    def repository[T](self, modelo: type[T]) -> BaseRepository[T]:
        return BaseRepository(self._session, modelo)

    def __enter__(self) -> UnitOfWork:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool:
        try:
            if exc_type is None:
                try:
                    self._session.commit()
                except Exception:
                    self._session.rollback()
                    raise
            else:
                self._session.rollback()
        finally:
            self._session.close()
        return False
