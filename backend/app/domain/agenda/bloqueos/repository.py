"""Nulo es consultorio completo: nunca se asigna un profesional por defecto."""

import uuid

from sqlalchemy import or_, select

from app.db.models import Bloqueo
from app.db.session import TenantSession
from app.domain.persistence import BaseRepository


class BloqueoRepository(BaseRepository[Bloqueo]):
    def __init__(self, session: TenantSession) -> None:
        super().__init__(session, Bloqueo)

    def listar(self, profesional_id: uuid.UUID | None) -> list[Bloqueo]:
        consulta = select(Bloqueo)
        if profesional_id is not None:
            consulta = consulta.where(
                or_(Bloqueo.profesional_id == profesional_id, Bloqueo.profesional_id.is_(None))
            )
        return list(self._session.execute(consulta.order_by(Bloqueo.desde, Bloqueo.id)).scalars())
