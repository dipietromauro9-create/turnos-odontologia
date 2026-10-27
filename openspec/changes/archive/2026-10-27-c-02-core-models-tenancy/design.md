# Diseño

## Contexto

C-01 dejó `app/db/base.py` con `Base`, el motor y `get_session(database_url)`; `app/main.py` consume esa fábrica vía `session_dep`. Alembic tiene una única revisión `0001_baseline` vacía y `env.py` ya importa `Base.metadata`. `Settings` es `extra='forbid'`, por lo que C-02 no puede introducir variables de entorno nuevas sin tocar el contrato tipado. La KB `08` fija Repository + Service, tenant discriminator y DB como última defensa; `09` §DD-02 exige que el filtro sea imposible de olvidar. Ver proposal.md para la motivación; las specs `core/tenancy` y `core/persistence` son el contrato de comportamiento.

## Objetivos / No objetivos

**Objetivos:**

- Un único camino de acceso a datos de dominio: contexto de tenant → sesión tenant-scoped → repositorio/UoW. Ningún router ni servicio recibe un `Session` sin tenant.
- Modelos `Tenant`/`Usuario` y mixins listos para que C-04+ agregue `Profesional`, `Prestacion`, `Turno`, etc. sin re-decidir convenciones.
- Migración reversible y seed repetible; tests de aislamiento ejecutables en CI con Postgres real.

**No objetivos:**

- Auth, JWT, hashing de login y endpoints de usuarios (C-03). El seed crea hashes Argon2id porque la columna es NOT NULL, no porque C-02 exponga login.
- Entidad `Profesional` ni la relación 1─1 `Usuario`↔`Profesional` (C-04).
- PostgreSQL RLS, selector de tenant por header/subdominio o tenants múltiples activos (post-MVP; DD-02 solo pide la frontera lógica).
- CRUD de tenants/usuarios por API y soft delete/auditoría formal (DD-07).

## Decisiones

- **Resolución de tenant en middleware + `ContextVar`, no en cada router.** Un `TenantContextMiddleware` resuelve el slug (v1: solo `settings.tenant_default_slug`) y publica `TenantContext(tenant_id, slug)` en un `ContextVar`; la dependencia de sesión lee el contexto. Fundamento: el contexto sigue disponible en el threadpool de endpoints `def` y también lo pueden setear workers/tests sin una `Request`; un dependency por router permitiría olvidarlo. Alternativa descartada: pasar `tenant_id` como parámetro por router (R3 depende de disciplina). Si el tenant no existe, la request de dominio falla con 503 de configuración (no hay código RN aplicable: no es una regla de negocio); `/health` usa sesión de sistema y no resuelve tenant. El `tenant_id` se cachea en memoria tras la primera resolución y se re-resuelve si el cache está vacío (permite correr el seed después del arranque).

- **Aislamiento forzado por la sesión con `do_orm_execute` + `with_loader_criteria`, más guarda de escritura en `before_flush`.** La sesión tenant-scoped agrega automáticamente `tenant_id = :contexto` a todo `SELECT` ORM (incluidos alias y lazy loads) y rechaza inserts/updates cuyo `tenant_id` no coincida con el contexto. Fundamento: cumple "imposible olvidar el filtro" sin confiar en cada repositorio y sin exigir una extensión de Postgres. Alternativa descartada para v1: RLS (`SET LOCAL app.tenant_id` + policies) — es la defensa más fuerte, pero exige roles/credenciales separados y complica tests/Compose; queda como evolución post-MVP. Limitación aceptada: SQL crudo y APIs `bulk_*` de SQLAlchemy (que no disparan eventos ORM) evitan la guarda; se prohíben en código de dominio por revisión y un test de arquitectura, y el `tenant_id` explícito del repositorio actúa como segunda barrera.

- **Un accessor de sistema explícito y acotado (`system_session`) solo para resolver tenants.** La tabla `tenant` no puede filtrarse por `tenant_id` (es la raíz), así que necesita una sesión sin scope. Se expone únicamente en `core/tenancy` para el resolver y el seed, con nombre que grita "system"; las sesiones de dominio nunca se construyen a partir de ella. Alternativa descartada: tabla de tenants en otro schema/DB (complejidad innecesaria para v1).

- **`get_session` pasa a ser la dependencia tenant-scoped; `db/session.py` concentra motor y fábricas.** `Base` queda en `db/base.py` para no romper el import de Alembic. `get_session()` (sin argumentos, lee el contexto) reemplaza a `get_session(database_url)`; se agregan `system_session()` y un context manager `tenant_context(...)` para workers/tests. Fundamento: mantiene el "único punto de inyección" de `foundation/backend-base`, pero hace que el tipo que reciben servicios/repositorios ya esté scoped. Alternativa descartada: mantener la firma vieja y pasar tenant por parámetro a cada query (R3).

- **Modelos ORM en `app/db/models/` con `mixins.py`.** `Tenant` y `Usuario` viven ahí y `app/db/models/__init__.py` los importa para que `Base.metadata` esté completo en Alembic. Fundamento: los modelos son transversales (los usan todos los dominios) y una sola superficie de metadata evita migraciones incompletas. Alternativa descartada: `app/domain/<dominio>/models.py` — reparte el metadata entre paquetes y obliga a Alembic a importar todos los dominios.

- **UUID v4 como PK, generado en Python con `server_default=gen_random_uuid()`.** Fundamento: los objetos tienen id antes del flush (tests y referencias), y SQL crudo/seed sigue funcionando. PG 16 incluye `gen_random_uuid()` sin extensión.

- **`rol` como `VARCHAR(20)` + CHECK, no ENUM nativo de Postgres.** El ORM usa `Enum(RolUsuario, native_enum=False, create_constraint=True)` y Pydantic valida el literal. Fundamento: agregar/renombrar valores o hacer downgrade con enums nativos requiere DDL especial y bloquea transacciones; el CHECK da la misma garantía para dos valores estables. Alternativa considerada: ENUM nativo (más "tipado" en DB) descartado por costo de migración.

- **`email` como `CITEXT` con índice único `(tenant_id, email)`; `slug` único y guarda de inmutabilidad en el mapper.** La migración crea `CREATE EXTENSION IF NOT EXISTS citext`; el case-insensitive lo resuelve la DB, no `lower()` en queries. `slug` se protege con un evento `before_update` del mapper que rechaza el cambio (no hay endpoint que lo actualice). Alternativa descartada: trigger `BEFORE UPDATE` en Postgres — más fuerte, pero duplica la regla y complica el seed/administración; se puede sumar luego sin cambiar el contrato.

- **`BaseRepository[T]` recibe obligatoriamente una sesión tenant-scoped y `UnitOfWork` es el dueño del commit.** `UnitOfWork` abre una sesión desde la fábrica con el `tenant_id` del contexto, expone `repository(Modelo)`, y hace `commit` al salir sin excepción o `rollback` si algo falla. Un repositorio construido con una sesión sin tenant lanza al construirse. Fundamento: RN-GL-02 se cumple por construcción (una sola transacción por operación de servicio) y C-07/C-08 solo escriben servicios. Alternativa descartada: cada servicio maneja `session.commit()` — repite el patrón y facilita commits parciales.

- **`timestamptz` + TZ por conexión.** Todas las columnas usan `DateTime(timezone=True)` con `server_default=func.now()`; el motor agrega `options=-c timezone=America/Argentina/Buenos_Aires` (psycopg). No se cambia el default del cluster. Los schemas de borde usan `AwareDatetime` (R1: `extra='forbid'`). Fundamento: RN-GL-03 y SU-04; `timestamptz` guarda el instante y la conexión fija la interpretación. Alternativa descartada: `ALTER DATABASE ... SET timezone` — acopla el deploy a un paso manual fuera de Alembic.

- **Seed idempotente con `get-or-create` y contraseñas Argon2id.** `python -m app.db.seed` resuelve/crea el tenant `demo`, luego cada usuario por email; si ya existe no lo modifica (no re-hashea ni pisa roles). Todo en una `UnitOfWork`. Se agrega `argon2-cffi` (U3: avisar antes de instalar) porque `password_hash` es NOT NULL y C-03 usará Argon2id; alternativa considerada: dejar `password_hash` nullable o un placeholder y completarlo en C-03 — se descarta porque debilita el modelo y obliga a otra migración.

- **Tests de integración contra Postgres real (`turnos_test`), no SQLite.** Fixture de sesión crea la base si falta, corre `alembic upgrade head` una vez y trunca las tablas de dominio entre tests. CI agrega un servicio `postgres:16` y exporta `DATABASE_URL`; los tests que no tocan DB siguen corriendo sin servicio. Fundamento: `citext`, constraints e índices son parte del contrato y SQLite no los reproduce. Alternativa descartada: mocks de sesión — no prueban aislamiento ni constraints.

- **Convención de nombres de constraints en `Base.metadata`.** Se agrega `naming_convention` (`ix`, `uq`, `ck`, `fk`, `pk`) antes de crear las tablas de C-02 para que Alembic genere nombres determinísticos; las migraciones futuras no dependen de nombres autogenerados por Postgres.

## Riesgos / Compromisos

- [Riesgo] SQL crudo o `Session.bulk_*` esquivan la guarda ORM → Mitigación: prohibición explícita en el diseño/tasks, test de arquitectura que falla si aparece `execute(text(` o `bulk_` en `app/domain`, y `tenant_id` obligatorio en el repositorio como segunda barrera. RLS queda como deuda post-MVP registrada.
- [Riesgo] `with_loader_criteria` no cubre colecciones cargadas por SQL manual o relaciones sin `TenantMixin` → Mitigación: todo modelo de dominio usa el mixin (test de metadata) y las relaciones entre tenants se validan en `before_flush`.
- [Riesgo] El middleware resuelve el tenant con una consulta extra por request → Mitigación: cache en memoria por slug; en v1 hay un solo tenant y el costo es despreciable.
- [Riesgo] Cambiar la firma de `get_session` rompe `main.py`/tests de C-01 → Mitigación: actualizar el consumidor en el mismo change y mantener `get_session` como nombre de la dependencia; los tests de health se ajustan al nuevo fixture.
- [Riesgo] Tests de integración más lentos y dependientes de Docker → Mitigación: marcador `integration`, base `turnos_test` dedicada y servicio de Postgres en CI; los tests unitarios (reglas puras, schemas) no requieren DB.
- [Riesgo] El seed automático en Compose podría pisar un entorno con datos → Mitigación: el seed solo crea lo que falta y nunca actualiza filas existentes; se ejecuta después de `alembic upgrade head` y es seguro repetirlo.

## Plan de migración

1. `alembic upgrade head` aplica `0002_tenancy_usuario` (extensión `citext`, tablas `tenant` y `usuario`, constraints e índices).
2. `python -m app.db.seed` crea el escenario demo (idempotente). En Compose se encadena al comando de la API después de las migraciones.
3. Verificación: `GET /health` sigue 200; un test de integración confirma aislamiento y seed.
4. Rollback: `alembic downgrade 0001_baseline` elimina índices, constraints, tablas y la extensión `citext`. Es destructivo y aceptable porque v1 no tiene datos productivos; el seed se puede recrear. Si la extensión ya existía por otro uso, el downgrade no debe eliminarla (se documenta y se omite el `DROP EXTENSION`).

## Decisiones confirmadas

- **Dependencia `argon2-cffi` (U3) — APROBADA por el usuario el 2026-10-27.** Se instala en C-02 para hashear el seed con Argon2id. La alternativa (placeholder no utilizable + re-hash en C-03) queda descartada.
- **Seed automático — CONFIRMADO por el usuario el 2026-10-27.** `python -m app.db.seed` se encadena en el `command` de la API en `docker-compose.yml`, después de `alembic upgrade head`. No es un paso manual.
