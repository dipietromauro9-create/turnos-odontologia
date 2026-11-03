# Propuesta

## Por qué

C-03 dejó el panel cerrado por JWT + RBAC, pero todavía no existe ninguna entidad de negocio que el personal pueda gestionar. Sin un directorio de pacientes no se puede reservar un turno (C-07 necesita `paciente_id`), ni reutilizar un paciente por teléfono en el turnero público (RN-PA-01, C-09), ni mostrar la ficha básica que pide US-009. C-05 entrega el primer recurso de dominio protegido y, con él, el contrato de "duplicado advertido" que consume C-09.

## Qué cambia

- Agregar el modelo `Paciente` tenant-scoped con `nombre`, `telefono`, `documento` (nullable), `fecha_nac` (nullable), `observaciones` (ficha básica, nullable) y timestamps. Los duplicados por nombre o teléfono se **advierten, no se bloquean**; no hay unicidad sobre `(nombre, telefono)`.
- Agregar los endpoints de panel `GET /pacientes` (listado + búsqueda `?q=`), `POST /pacientes` y `PATCH /pacientes/{id}`. Ninguno se expone en rutas públicas (RN-PA-02).
- Implementar la búsqueda por nombre con trigram (`pg_trgm`) y por teléfono normalizado a dígitos; el teléfono normalizado es también la clave de reutilización de RN-PA-01.
- Aplicar la matriz de `03_actores_y_roles.md`: recepción gestiona todos los pacientes; el profesional dueño también; el profesional sin flag solo gestiona los suyos y recibe 403 `RN-AU-03` sobre los ajenos.
- Devolver `201` con una advertencia `RN-PA-01` cuando el alta crea un posible duplicado, incluyendo las coincidencias visibles para el llamador. El mismo resultado se expone como contrato de servicio (`creado` + `advertencia`) para que C-09 reutilice por teléfono sin ver la ficha.
- Dejar el borrado como **físico** a nivel de dominio (sin `deleted_at` ni `activo`), con la deuda de auditoría/soft delete documentada en código y en el design (RN-PA-03, DD-07, IN-01). El scope de C-05 no agrega una ruta HTTP de borrado.
- Agregar la migración `0003_paciente` con la tabla, los índices `(tenant_id, telefono)` y trigram `(tenant_id, lower(nombre))`, y el seed de 2 pacientes ficticios creados por el dueño demo (R9).

## Capacidades

### Nuevas capacidades

- `core/pacientes`: directorio y ficha básica del paciente — alta con advertencia de duplicado, búsqueda por nombre/teléfono, reutilización por teléfono, alcance recepción/profesional/dueño (RN-AU-03) y frontera de no exposición pública (RN-PA-02).

### Capacidades modificadas

- Ninguna. `core/auth` y `core/rbac` se consumen sin cambiar su contrato (`CurrentUserDep`, `require_role`, `es_dueno`, `require_acceso_profesional`); `core/tenancy`/`core/persistence` siguen aportando el filtro y la sesión tenant-scoped. `foundation/backend-base` mantiene el sobre `{code, message, details}` de RN-GL-01.

## Impacto

- Afecta: `backend/app/db/models/` (`paciente.py` nuevo, export en `__init__.py`), `backend/app/domain/pacientes/` (nuevo: `schemas.py`, `service.py`, `dependencies.py`, `router.py`), `backend/app/main.py` (registro del router), `backend/app/db/seed.py` (2 pacientes demo), `backend/alembic/versions/0003_paciente.py` (nueva) y `backend/tests/` (nuevos tests de modelo, búsqueda, CRUD, RBAC, frontera pública, aislamiento, seed y borrado).
- APIs: tres endpoints nuevos bajo `/pacientes`; ninguna ruta existente cambia de contrato. `/health`, docs y `/turnero/*` siguen siendo las únicas superficies públicas.
- Base de datos: **sí hay migración** (R7). Se agregan la tabla `paciente`, el FK a `tenant`, el FK nullable a `usuario` para el alcance provisional del profesional y los índices de búsqueda. Se requieren las extensiones `pg_trgm` y `btree_gin` (contrib de Postgres 16, ya disponible en la imagen).
- Dependencias: **ninguna nueva** de Python; `pg_trgm`/`btree_gin` son extensiones de la base, no paquetes.
- Aguas abajo: C-07 usa `Paciente` como FK de `Turno`; C-09 consume `crear_o_reutilizar_paciente` para RN-PA-01 y la frontera pública; C-10 consume los endpoints de ficha. Gobernanza **MEDIO**: RN-PA-01/02/03 y RN-AU-03 quedan enforced acá.
