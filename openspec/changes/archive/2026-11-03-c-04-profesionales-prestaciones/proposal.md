# Propuesta

## Por qué

C-03 cerró el gate de acceso y dejó el panel protegido, pero todavía no existe el catálogo clínico-administrativo que todo turno referencia: no hay profesionales ni prestaciones. Sin ellos C-07 no puede crear un turno (necesita `profesional_id` y `prestacion_id`), C-08 no puede calcular huecos (necesita la grilla de `duracion_min`) y el dueño no puede configurar el consultorio (US-008 parcial).

## Qué cambia

- Agregar los modelos de catálogo `Profesional` y `Prestacion` sobre `TenantMixin`/`AuditMixin` de C-02:
  - `Profesional`: `usuario_id` UUID nullable con FK a `usuario.id` y unicidad global (un login = un profesional), `nombre` obligatorio, `matricula`/`especialidad` nullables, `activo` booleano (default `true`) e índice `(tenant_id, activo)`.
  - `Prestacion`: `nombre` obligatorio, `duracion_min` entero con CHECK `> 0` y múltiplo de 5, `precio_ref` `numeric(12,2)` nullable e informativo (v1 no calcula cobros), `activa` booleana (default `true`) e índice `(tenant_id, activa)`.
- Agregar el CRUD dueño-only del catálogo, montado bajo `/profesionales` y `/prestaciones`:
  - `GET /profesionales` (filtro opcional por `activo`), `POST /profesionales`, `PATCH /profesionales/{id}`.
  - `GET /prestaciones` (filtro opcional por `activa`), `POST /prestaciones`, `PATCH /prestaciones/{id}` y `POST /prestaciones/{id}/desactivar` (idempotente).
  - Todos los endpoints declaran `require_dueno` (RN-AU-02): recepción y profesional sin flag reciben 403; sin token, 401.
- No exponer borrado físico: las entidades referenciadas por turnos se desactivan (`activo=false` / `activa=false`) y dejan de ofrecerse, pero conservan su historial.
- Garantizar RN-AG-03 en el lado del catálogo: actualizar `duracion_min` solo modifica la fila de `prestacion`; la migración no declara `ON UPDATE CASCADE` ni ninguna cascada hacia turnos, y el dominio de agenda no escribe turnos. La duración queda congelada en cada turno vía `fin` cuando C-07 lo cree (contrato de frontera documentado en `design.md`).
- Agregar la migración Alembic `0003_profesional_prestacion` (siguiente revisión libre tras `0002_tenancy_usuario`; `CHANGES.md` la llama "002" por el desfase de numeración de C-02): tablas `profesional` y `prestacion`, FKs, CHECK de duración, unicidad de `usuario_id` e índices; `downgrade` reversible.
- Extender el seed demo idempotente: vincular el usuario `dueno@demo` a un `Profesional` demo y sembrar las cinco prestaciones base (Consulta 30, Limpieza 60, Extracción 45, Control 20, Urgencia 30). Si la tabla `disponibilidad` de C-06 ya existe, sembrar además la plantilla Lun–Vie 9–13 / 16–20 para el profesional demo; si no existe, omitir ese bloque sin fallar (el CRUD de disponibilidad sigue siendo de C-06).
- Pruebas: CRUD completo como dueño, 403 para recepción y para profesional sin flag, 401 sin token, `duracion_min` inválida (0, negativa, no múltiplo de 5) → 422 con código `RN-AG-03`, `usuario_id` duplicado y `usuario_id` de otro tenant rechazados, desactivar no borra, aislamiento por tenant y seed idempotente.

## Capacidades

### Nuevas capacidades

- `core/profesionales`: directorio de profesionales del consultorio — alta, consulta y edición por el dueño, vínculo opcional 1─1 con un usuario de login, desactivación sin borrado y aislamiento por tenant.
- `core/prestaciones`: catálogo de prestaciones — alta, consulta, edición y desactivación por el dueño, duración válida (positiva y múltiplo de 5) congelada por turno (RN-AG-03), precio de referencia informativo y aislamiento por tenant.

### Capacidades modificadas

- `core/tenancy`: se modifica el requisito del seed demo. La versión de C-02 exigía que el seed creara "solo datos ficticios de tenant y usuarios"; C-04 (y luego C-05/C-06) extiende el escenario demo con filas de catálogo. El requisito pasa a exigir datos exclusivamente ficticios (R9) e idempotencia, sin enumerar taxativamente qué entidades puede sembrar, para no bloquear los seeds de C-05/C-06.

## Impacto

- Afecta: `backend/app/db/models/` (`profesional.py`, `prestacion.py`, `__init__.py`), `backend/app/domain/agenda/` (nuevo: `profesionales/` y `prestaciones/` con `schemas.py`, `service.py`, `router.py`), `backend/app/main.py` (registro de routers), `backend/app/db/seed.py` (profesional + prestaciones + disponibilidad condicional), `backend/alembic/versions/0003_profesional_prestacion.py`, `backend/tests/`.
- APIs: ocho endpoints nuevos (`/profesionales` ×3, `/prestaciones` ×4 más el `PATCH`), todos dueño-only. Ninguna ruta existente cambia de contrato; `/health`, `/auth/*` y `/turnero/*` quedan igual.
- Dependencias: **ninguna nueva**. Se reutilizan `fastapi`, `sqlmodel`/SQLAlchemy 2, `pydantic` v2, Alembic y los helpers de C-02/C-03 (`TenantMixin`, `AuditMixin`, `BaseRepository`, `UnitOfWork`, `require_dueno`, `CurrentUserDep`).
- Base de datos: migración aditiva `0003_profesional_prestacion`; sin datos previos que migrar. Riesgo de múltiples cabezas Alembic por el paralelismo de C-04/C-05/C-06 (ver `design.md` §Riesgos).
- Aguas abajo: desbloquea C-07 (FK `profesional_id`/`prestacion_id` y `fin = inicio + duracion_min`) y C-08 (grilla de huecos por `duracion_min`); C-06 consume `Profesional` como FK. Gobernanza **MEDIO**.
