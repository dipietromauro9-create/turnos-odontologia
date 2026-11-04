"""Fábricas locales C-06, independientes de factories.py compartido."""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Bloqueo, Disponibilidad
from app.db.session import TenantSession
from tests.agenda_factories import crear_bloqueo, crear_disponibilidad, crear_profesional
from tests.factories import crear_tenant

pytestmark = pytest.mark.integration


def test_fabricas_persisten_en_su_tenant_y_no_filtran_al_otro(
    session_factory: sessionmaker[Session], db_engine: object
) -> None:
    with session_factory() as session:
        tenant = crear_tenant(session)
        otro = crear_tenant(session, "otro")
        profesional = crear_profesional(session, tenant)
        franja = crear_disponibilidad(session, tenant, profesional)
        bloqueo = crear_bloqueo(session, tenant, profesional)
        global_ = crear_bloqueo(session, tenant)
    assert franja.tenant_id == bloqueo.tenant_id == global_.tenant_id == tenant.id
    assert global_.profesional_id is None
    with TenantSession(bind=db_engine, tenant_id=otro.id) as scoped:
        assert scoped.execute(select(Disponibilidad)).scalars().all() == []
        assert scoped.execute(select(Bloqueo)).scalars().all() == []
    with TenantSession(bind=db_engine, tenant_id=tenant.id) as scoped:
        assert len(scoped.execute(select(Bloqueo)).scalars().all()) == 2
