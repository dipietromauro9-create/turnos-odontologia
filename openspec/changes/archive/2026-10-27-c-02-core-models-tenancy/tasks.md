# Tareas

Ciclo estricto: cada bloque de implementación empieza con un test que falla (rojo), sigue con la implementación mínima que lo pone en verde, y cierra triangulando casos borde y refactorizando. Los escenarios de `specs/core/tenancy` y `specs/core/persistence` son los criterios de aceptación.

## 1. Preparación de dependencias y harness de tests

- [x] 1.1 Agregar `argon2-cffi` a las dependencias de `backend/pyproject.toml` (U3 aprobada por el usuario el 2026-10-27) y verificar que `uv sync --group dev` resuelve y que `uv run python -c "import argon2"` funciona
- [x] 1.2 Crear en `backend/tests/conftest.py` el harness de integración: derivar/crear la base `turnos_test`, aplicar `alembic upgrade head` una vez por sesión, truncar las tablas de dominio entre tests y exponer fixtures de fábrica de sesiones y de contexto de tenant; verificar con un test de humo que la conexión responde y que la base de test es distinta de la de desarrollo
- [x] 1.3 Registrar el marcador `integration` en `backend/pyproject.toml` y agregar el servicio `postgres:16` con `DATABASE_URL` al job de backend de `.github/workflows/ci.yml`; verificar que `uv run pytest -q -m integration` corre localmente con Compose y que el YAML del workflow parsea

## 2. Modelos, mixins y migración 0002

- [x] 2.1 Escribir primero los tests de metadata (rojo) que exigen `tenant_id` UUID NOT NULL con FK a `tenant`, índices compuestos que empiezan por `tenant_id`, `creado_en`/`actualizado_en` `timestamptz` no nulos y nombres de constraints determinísticos; correr `uv run pytest tests/test_models_metadata.py` y confirmar que fallan porque los modelos no existen
- [x] 2.2 Implementar la convención de nombres en `Base.metadata`, `mixins.py` (`TenantMixin`, `AuditMixin`) y los modelos `Tenant`/`Usuario` con `UUID`, `rol` (`VARCHAR(20)` + CHECK) y `email` CITEXT; verificar que los tests de metadata de 2.1 pasan
- [x] 2.3 Escribir primero los tests de constraints que fallan (rojo): `slug` único, `slug` inmutable tras creación, email único case-insensitive por tenant y `es_dueno=true` solo con `rol=profesional`; correr `uv run pytest tests/test_models_constraints.py` y confirmar el fallo por tablas ausentes
- [x] 2.4 Crear la migración `backend/alembic/versions/0002_tenancy_usuario.py` (extensión `citext`, tablas `tenant`/`usuario`, unique `(tenant_id, email)`, CHECK de rol y de dueño, índices `(tenant_id, rol)`), importar los modelos desde `app/db/models/__init__.py` para que `Base.metadata` esté completo y verificar que `alembic upgrade head`, `alembic downgrade 0001_baseline` y `alembic upgrade head` corren limpios sobre Postgres 16 y que `alembic check` no reporta diferencias
- [x] 2.5 Triangular los casos borde de la spec: email con distinta capitalización rechazado en el mismo tenant, mismo email permitido en otro tenant, `actualizado_en` avanza al modificar y `creado_en` no cambia; verificar que los tests nuevos y los de 2.3 pasan y refactorizar duplicación de fixtures

## 3. Resolución de tenant y sesión tenant-scoped

- [x] 3.1 Escribir primero los tests de integración en rojo: una request de dominio usa el tenant de `TENANT_DEFAULT_SLUG`, una request sin tenant resuelto falla antes de consultar, `GET /health` sigue 200 sin tenant, y una consulta desde el tenant A no devuelve filas del tenant B; correr `uv run pytest tests/test_tenancy_session.py -m integration` y confirmar el fallo
- [x] 3.2 Implementar el mínimo para verde: `TenantContext` + `ContextVar`, `TenantContextMiddleware` con resolución y cache del slug por defecto, `system_session()` acotada a la tabla de tenants y la sesión tenant-scoped con `do_orm_execute` + `with_loader_criteria`; verificar que los tests de lectura y de `/health` de 3.1 pasan
- [x] 3.3 Reemplazar `get_session(database_url)` por la dependencia `get_session()` tenant-scoped en `backend/app/db/session.py`, actualizar `backend/app/main.py` y `session_dep`, y agregar la guarda `before_flush` que rechaza inserts/updates con `tenant_id` ajeno; verificar que el test de escritura cruzada y toda la suite de 3.1 pasan
- [x] 3.4 Triangular alias/joins/lazy loads, actualización de una fila propia intentando moverla a otro tenant y un test de arquitectura que falla si `app/domain` usa SQL crudo o `bulk_*` y que exige `TenantMixin` en todo modelo de dominio; verificar todos los escenarios de `core/tenancy` en verde y refactorizar el resolver para que no consulte dos veces por request

## 4. Repositorio base y unidad de trabajo

- [x] 4.1 Escribir primero los tests en rojo de `BaseRepository[T]` y `UnitOfWork`: listar/obtener solo del tenant de la sesión, crear asigna el `tenant_id` de la sesión, construir el repositorio con una sesión sin tenant falla, y `UnitOfWork` hace commit de todo el grupo o rollback de todo ante un fallo intermedio; correr `uv run pytest tests/test_repository_uow.py -m integration` y confirmar el fallo
- [x] 4.2 Implementar la mínima `BaseRepository[T]` (get/list/add/update/delete scoped) y `UnitOfWork` (context manager con commit al salir sin excepción y rollback ante excepción, exponiendo `repository(Modelo)`); verificar que los tests de 4.1 pasan
- [x] 4.3 Triangular que `get`/`update`/`delete` por id de otro tenant no encuentran ni modifican la fila, que dos escrituras válidas quedan visibles juntas después del commit y que una sesión externa no ve escrituras antes del commit; verificar todos los escenarios de `core/persistence` en verde y refactorizar el tipado genérico del repositorio

## 5. Seed demo idempotente

- [x] 5.1 Escribir primero los tests en rojo de `python -m app.db.seed`: crea tenant `demo`, `dueno@demo` (`profesional`, `es_dueno=true`, `activo`) y `recepcion@demo` (`recepcion`, `es_dueno=false`, `activo`), el hash de contraseña verifica con Argon2id, no crea pacientes y una segunda ejecución no duplica ni cambia valores; confirmar el fallo
- [x] 5.2 Implementar el seed con `get-or-create` por slug/email dentro de una `UnitOfWork`, usando solo datos ficticios (R9), y encadenarlo en el `command` de la API en `docker-compose.yml` después de `alembic upgrade head`; verificar que los tests de 5.1 pasan
- [x] 5.3 Triangular el caso de un tenant existente con otro `nombre` (el seed no lo pisa) y el de una base donde ya existen ambos usuarios; verificar que correr el seed dos veces seguidas deja exactamente las mismas filas y refactorizar el seed para separar creación de tenant y de usuarios

## 6. Verificación integral

- [x] 6.1 Correr `uv run ruff check app tests`, `uv run ruff format --check app tests`, `uv run pytest -q` (unitarios e integración) y `uv run alembic check`, y verificar cero errores y una sola cabeza de migraciones
- [x] 6.2 Levantar el stack desde cero (`docker compose down -v && cp .env.example .env && docker compose up --build -d`), correr el seed dos veces y verificar `GET /health` → 200, `alembic current` en `0002_tenancy_usuario` y que un test de aislamiento manual entre dos tenants no filtra filas
- [x] 6.3 Correr `openspec validate c-02-core-models-tenancy --strict` y verificar cero errores (specs parsean, cada requisito tiene sus escenarios, Propósito de las capacidades nuevas ≥ 50 caracteres)
