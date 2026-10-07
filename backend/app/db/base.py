"""Base declarativa + motor + fábrica de sesiones (único punto de inyección).

C-02 engancha el middleware de tenant exactamente en `get_session` (R3).
Convención: solo datetimes aware (`datetime.now(UTC)`); en C-02 los
schemas de borde usan `AwareDatetime` para rechazar naive (spec TZ).
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


_engine = None
_session_factory: sessionmaker[Session] | None = None


def get_engine(database_url: str):  # type: ignore[no-untyped-def]
    global _engine
    if _engine is None:
        _engine = create_engine(database_url, pool_pre_ping=True)
    return _engine


def get_session(database_url: str) -> Iterator[Session]:
    """Fábrica de sesiones — único punto de inyección de DB (R3-ready)."""
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(bind=get_engine(database_url), expire_on_commit=False)
    with _session_factory() as session:
        yield session


def ping_database(session: Session) -> bool:
    try:
        session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
