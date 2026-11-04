# Propuesta

## Por qué

C-03 cerró el acceso del panel, pero el dueño todavía no puede declarar cuándo atiende ni cerrar el consultorio en fechas puntuales. Sin esa fuente de verdad, C-07 y C-08 no tienen contra qué validar un turno ni qué huecos ofrecer, y el turnero terminaría publicando horarios que el consultorio no trabaja (RN-AG-01, RN-AG-02).

## Qué cambia

- Agregar el modelo `Disponibilidad` (plantilla semanal): `profesional_id`, `dia_semana` 0–6, `hora_desde`/`hora_hasta`, con `hora_hasta > hora_desde`, sin duplicados exactos por `(profesional, día, rango)` y rechazo de rangos solapados del mismo profesional y día. Usa `TenantMixin`/`AuditMixin` de C-02.
- Agregar el modelo `Bloqueo` (cierre puntual): `profesional_id` nullable, `desde`/`hasta` en `timestamptz`, `motivo`, con `hasta > desde`. Un `profesional_id` nulo significa que el cierre afecta a todo el consultorio (RN-AG-02: feriado, desinfección).
- Agregar los endpoints internos de panel:
  - `GET/POST/DELETE /disponibilidad` y `GET/POST/DELETE /bloqueos`.
  - Lectura: recepción ve todo el consultorio; el profesional ve su propia disponibilidad y sus bloqueos más los cierres de consultorio (`profesional_id` nulo); el dueño ve todo.
  - Escritura (`POST`/`DELETE`): exclusiva del profesional dueño (`require_dueno`); recepción y profesional sin flag reciben 403 `RN-AU-02`.
- Agregar la migración Alembic de las tablas `disponibilidad` y `bloqueo` con sus CHECK, unique e índices, reversible, encadenada después de las migraciones de C-04 y C-05.
- Declarar `profesional_id` como FK a `profesional.id` según `knowledge-base/04_modelo_de_datos.md`, sin implementar ni duplicar el CRUD de profesionales (C-04). La integración real se verifica en C-07.
- Pruebas: bloqueo con profesional nulo cierra todo el consultorio (RN-AG-02), rangos inválidos → 422, solapamiento/duplicado de rangos por profesional y día, recepción no puede crear (403), profesional solo lee lo propio y el aislamiento por tenant.

## Capacidades

### Nuevas capacidades

- `core/disponibilidad`: plantilla semanal del profesional — alta, consulta y baja de rangos por día de la semana, validación de rangos y de solapamientos, y alcance de lectura por rol.
- `core/bloqueos`: cierres puntuales del consultorio o de un profesional — alta, consulta y baja, semántica de `profesional_id` nulo (RN-AG-02), validación del intervalo y alcance de lectura por rol.

### Capacidades modificadas

- Ninguna. `core/rbac` ya provee `require_dueno`, `require_role`, `es_dueno` y `alcance_agenda`; C-06 los consume sin cambiar su contrato. `core/tenancy` y `core/persistence` aportan la sesión tenant-scoped y el `UnitOfWork` que se reutilizan tal cual.

## Impacto

- Afecta: `backend/app/db/models/` (nuevos `disponibilidad.py` y `bloqueo.py`), `backend/app/domain/agenda/` (nuevo: schemas, repositorio, servicio y router de disponibilidad y bloqueos), `backend/app/main.py` (registro del router), `backend/alembic/versions/` (nueva migración), `backend/tests/` (nuevos tests de reglas, RBAC, validación y aislamiento).
- APIs: seis endpoints nuevos bajo `/disponibilidad` y `/bloqueos`; ninguna ruta existente cambia de contrato. Siguen siendo de panel (JWT obligatorio) y no se exponen en el turnero público.
- Dependencias: ninguna nueva de runtime ni de test (U3 no se dispara). Se reutilizan `BaseRepository`/`UnitOfWork`, la sesión tenant-scoped y los helpers RBAC de C-02/C-03.
- Base de datos: una migración aditiva con dos tablas, CHECK, unique e índices; sin datos previos que migrar. La tabla `profesional` es un prerrequisito blando de C-04.
- Aguas abajo: desbloquea C-07 (`turnos-state-machine` consume la FK y la validación de agenda) y C-08 (`motor-disponibilidad` calcula huecos a partir de estas tablas). Gobernanza **MEDIO**: RN-AG-02 y la matriz de roles quedan enforced acá.
