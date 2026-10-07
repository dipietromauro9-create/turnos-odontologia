# Propuesta

## Por qué

Todavía no existe un monorepo ejecutable (solo hay `knowledge-base/`, `CHANGES.md`, `openspec/`). Todos los changes posteriores (C-02 → C-12) asumen un shell de backend funcional, un shell de frontend, infraestructura con Compose y CI. Sin C-01, no hay dónde agregar modelos, routers ni páginas del turnero, ni forma reproducible de correr DB/Redis/worker en local.

## Qué cambia

- Armar la estructura del monorepo: `backend/app/{core,domain,workers,db}` + `backend/tests/` + `frontend/src/{features,shared,pages}` según `08_arquitectura_propuesta.md` §Estructura de directorios.
- Base del backend (FastAPI 0.110, Python 3.12): app mínima con `GET /health`, motor SQLAlchemy 2 y fábrica de sesiones (`db.session.get_session`), Alembic inicializado (todavía sin tablas de dominio), `core/` con configuración por entorno, logger estructurado, sobre de excepciones de dominio base `{"code": "RN-XX-NN", ...}` (RN-GL-01).
- Shell del frontend (Vite + React 18 + TS 5 estricto): cliente HTTP base en `shared/api` (URL base por entorno, manejo del sobre JSON), `routes.tsx` con guardianes de rutas públicas/privadas (cascarones vacíos — se completan en C-09/C-10), `tsconfig` estricto (sin `any`), componentes en PascalCase.
- Infraestructura: `docker-compose.yml` con 5 servicios (api + web + postgres 16 + redis 7 + worker), `.env.example` con las 8 variables de `08` §Variables de entorno (`DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`, `ACCESS_MINUTES`/`REFRESH_DAYS`, `TENANT_DEFAULT_SLUG=demo`, `TZ=America/Argentina/Buenos_Aires`, `FRONTEND_ORIGIN`, `RECORDATORIO_VENTANA_HS`). TZ fija desde el día uno (RN-GL-03).
- Herramientas: `backend/pyproject.toml` (pytest), `frontend/package.json` (Vitest), CI con GitHub Actions y jobs paralelos de backend/frontend.
- Pruebas: test de health-check del backend, test de carga de configuración, prueba de humo de conectividad a la DB por Compose; test de render del shell de frontend.

## Capacidades

### Nuevas capacidades

- `foundation/backend-base`: base FastAPI ejecutable — endpoint de health, configuración por entorno, fábrica de sesiones de DB, línea base de Alembic, sobre de errores de dominio, TZ por defecto.
- `foundation/frontend-shell`: shell Vite+React+TS ejecutable — cliente API base, guardianes de rutas públicas/privadas, compuerta de tipado estricto.

### Capacidades modificadas

- Ninguna (greenfield; no hay specs existentes — `openspec list --specs` devuelve vacío).

## Impacto

- Afecta: raíz del repo (nuevos `backend/`, `frontend/`, `docker-compose.yml`, `.env.example`, `.github/workflows/`). No hay código existente que migrar (greenfield).
- APIs: solo el nuevo `GET /health` (sin impacto de versionado).
- Dependencias: fija Python 3.12, FastAPI ≥0.110, SQLAlchemy 2, Alembic, Pydantic v2, Postgres 16, Redis 7, React 18, TS 5. Sin servicios externos (WA manual en v1, sin integraciones).
- Aguas abajo: desbloquea C-02 (modelos/tenancy necesitan `db.session`, Alembic, configuración). Gobernanza BAJA.
