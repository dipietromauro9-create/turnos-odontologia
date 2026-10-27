# Propuesta

## Por qué

C-01 dejó una API sana, una fábrica de sesiones y una línea base de Alembic vacía, pero todavía no existe ninguna entidad de dominio ni forma de aislar datos por consultorio. Todo el resto del roadmap (auth, agenda, turnos, pacientes) necesita `Tenant`, `Usuario`, una sesión que aplique la frontera multi-tenant sin depender de la disciplina de cada query y una base transaccional para las operaciones atómicas de RN-GL-02.

## Qué cambia

- Agregar los modelos `Tenant` y `Usuario` con `TenantMixin` y `AuditMixin`:
  - `Tenant.slug` único e inmutable tras la creación.
  - `Usuario.email` único por tenant (tipo `citext`, case-insensitive), `rol` con valores `recepcion | profesional`, `es_dueno` booleano con constraint `es_dueno = true` solo si `rol = 'profesional'` (RN-AU-02) y `activo`.
  - `TenantMixin` aporta `tenant_id` (FK a `tenant`) e índices compuestos `(tenant_id, ...)`; `AuditMixin` aporta `creado_en` / `actualizado_en` en `timestamptz`.
- Agregar resolución e inyección de tenant: un middleware/dependencia resuelve el tenant de la request (v1: `TENANT_DEFAULT_SLUG`, sin selector multi-tenant) y publica el `tenant_id` en un contexto de request; la fábrica de sesiones de `app/db` abre sesiones **tenant-scoped**. La sesión agrega el filtro `tenant_id` a toda query ORM (lecturas y `with_loader_criteria`) y rechaza escrituras con `tenant_id` ajeno. Queda un accessor explícito y auditado de sesión de sistema para la resolución del propio tenant.
- Agregar `BaseRepository[T]` y `UnitOfWork`: repositorio genérico que recibe la sesión tenant-scoped (nunca un `Session` crudo) y una unidad de trabajo con `commit`/`rollback` único por operación, para que reserva, reprogramación y transiciones de turno sean atómicas (RN-GL-02). C-07/C-08 construyen sobre esta base.
- Agregar la migración Alembic `0002_tenancy_usuario` (siguiente revisión libre tras `0001_baseline`): extensión `citext`, tablas `tenant` y `usuario`, constraints e índices; `downgrade` reversible.
- Agregar seed demo idempotente (`python -m app.db.seed`): tenant `demo`, `dueno@demo` (rol `profesional`, `es_dueno=true`), `recepcion@demo` (rol `recepcion`), sin datos de pacientes (R9).
- Fijar `timestamptz` en todas las columnas de tiempo y la zona `America/Argentina/Buenos_Aires` a nivel de conexión/DB (RN-GL-03), sin datetimes naive.
- Pruebas: unicidad `(tenant_id, email)` case-insensitive, constraint `es_dueno`, aislamiento multi-tenant (la sesión del tenant A no ve filas de B y no puede escribir filas de B), `slug` inmutable, seed idempotente y atomicidad de `UnitOfWork`.

## Capacidades

### Nuevas capacidades

- `core/tenancy`: identidad del consultorio (`Tenant`), usuarios (`Usuario`) con su rol y flag de dueño, resolución del tenant por request y garantía de aislamiento de datos por tenant. Path elegido porque la KB agrupa estos elementos como "Núcleo multi-tenant" y porque `core/` ya es la carpeta de infraestructura transversal del backend; se separa de `core/persistence` para que el aislamiento y el acceso a datos evolucionen con contratos independientes.
- `core/persistence`: acceso a datos reusable — `TenantMixin`/`AuditMixin` como contrato de modelos, `BaseRepository[T]` tenant-scoped y `UnitOfWork` transaccional (RN-GL-02), más la convención `timestamptz`/TZ única (RN-GL-03).

### Capacidades modificadas

- Ninguna. `foundation/backend-base` sigue cumpliendo su contrato: la fábrica de sesiones continúa siendo el único punto de inyección; C-02 la extiende con el scope de tenant sin cambiar sus requisitos.

## Impacto

- Afecta: `backend/app/core/` (contexto y resolución de tenant), `backend/app/db/` (`base.py`, nueva sesión tenant-scoped, `models/`, `seed.py`), `backend/app/domain/` (repositorios/UoW compartidos), `backend/alembic/versions/0002_tenancy_usuario.py`, `backend/tests/`, `backend/pyproject.toml`.
- APIs: sin endpoints nuevos de negocio; `GET /health` sigue público y sin tenant. No hay cambio de contrato externo todavía (los endpoints de usuarios/auth llegan en C-03).
- Dependencias: nueva dependencia de runtime `argon2-cffi` para hashear las contraseñas demo del seed (Argon2id, el algoritmo que C-03 usará para login). **Aprobada por el usuario (U3) el 2026-10-27.**
- Base de datos: primera migración con tablas reales; `citext` habilitado; los cambios son aditivos (no hay datos previos que migrar).
- Aguas abajo: desbloquea C-03 (`auth-rbac` necesita `Usuario.rol`/`es_dueno` y sesión tenant-scoped) y es la base obligatoria de C-04 → C-12. Gobernanza **CRÍTICO**: R3 y R7 se enforcean acá.
