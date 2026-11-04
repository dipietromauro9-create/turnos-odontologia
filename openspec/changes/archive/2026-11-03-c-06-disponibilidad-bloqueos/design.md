# Diseño

## Contexto

C-02 dejó el contrato sobre el que C-06 se apoya sin reimplementarlo:

- `backend/app/db/models/mixins.py`: `TenantMixin` (FK `tenant_id` NOT NULL) y `AuditMixin` (`creado_en`/`actualizado_en` `timestamptz`), con SQLAlchemy 2 declarativo (`Mapped`/`mapped_column`).
- `backend/app/db/session.py`: `TenantSession` agrega el filtro `tenant_id` a todo `SELECT` ORM (`do_orm_execute` + `with_loader_criteria`) y rechaza escrituras cruzadas en `before_flush`; `get_session()` es la dependencia tenant-scoped.
- `backend/app/domain/persistence.py`: `BaseRepository[T]` (solo acepta `TenantSession`) y `UnitOfWork` (una transacción por operación, commit al salir sin excepción).
- `backend/app/db/models/__init__.py`: punto único que completa `Base.metadata` para Alembic.
- Alembic tiene una sola cabeza: `0002_tenancy_usuario`.

C-03 dejó la autorización que C-06 consume:

- `backend/app/domain/auth/dependencies.py`: `CurrentUserDep`, `require_role(...)`, `require_dueno`, `es_dueno`, `alcance_agenda` y `require_acceso_profesional`. `require_dueno` marca `__rbac_roles__` y `__rbac_dueno__` para el test de arquitectura.
- `AuthMiddleware` ya exige JWT en toda ruta no pública; el router solo declara roles.
- `DomainError` + `ErrorEnvelope` (`code` con patrón `RN-XX-NN`) y `register_handlers()` en `app/main.py`.

C-04 **no está archivado**. El contrato de `knowledge-base/04_modelo_de_datos.md` §Profesional fija: `Profesional.id` UUID PK, `tenant_id`, `usuario_id` UUID nullable y único, `nombre`, `matricula`/`especialidad` nullables, `activo`, timestamps. C-06 solo lo referencia como FK; no crea ni duplica el CRUD. La integración real se valida en C-07.

`knowledge-base/04_modelo_de_datos.md` §Disponibilidad y §Bloqueo, `05` §RN-AG-01/02 y `06` §US-008 son la fuente de comportamiento; `specs/core/disponibilidad` y `specs/core/bloqueos` son el contrato. Ver `proposal.md` para la motivación.

## Objetivos / No objetivos

**Objetivos:**

- Dos modelos tenant-scoped con sus constraints de base y una migración reversible encadenada después de C-04/C-05.
- Un único camino de escritura para la agenda: router fino → servicio → `UnitOfWork`; la validación de rangos y solapamientos vive en el servicio, con la base como última defensa para duplicados exactos.
- Lectura con alcance por rol (recepción/dueño todo; profesional lo propio + cierres de consultorio) y escritura exclusiva del dueño.
- Tests de integración que cubren RN-AG-02, rangos inválidos, solapamientos, 403 de recepción, alcance del profesional y aislamiento por tenant.

**No objetivos:**

- CRUD de `Profesional`/`Prestacion` (C-04), `Turno` (C-07), cálculo de huecos (C-08), turnero público (C-09) y frontend de agenda (C-10).
- Excepciones recurrentes, feriados precargados, plantillas por consultorio o reemplazos temporales de la plantilla semanal: se modelan como `Bloqueo`, no como otra entidad.
- Soft delete/auditoría formal (DD-07) y RLS (post-MVP).
- Sembrar datos demo de disponibilidad: `CHANGES.md` asigna ese seed a C-04 (filas SQL si C-06 no existe). C-06 no duplica el seed; solo verifica que puede leer esas filas.

## Decisiones

- **Modelos con SQLAlchemy 2 declarativo + Pydantic v2, como C-02/C-03, no SQLModel.** El repo ya tiene `Base`, `Mapped`/`mapped_column`, `TenantSession` y `BaseRepository` construidos sobre SQLAlchemy 2; introducir SQLModel obligaría a dos stacks de persistencia. Los schemas de borde son Pydantic v2 con `extra='forbid'` (R1). Alternativa descartada: SQLModel (más conciso, pero incompatible con el harness y el repositorio existentes).

- **`dia_semana` con 0 = lunes y 6 = domingo.** La KB solo dice 0–6; se elige la convención de `datetime.date.weekday()` (ISO-8601 menos uno) porque C-08 calculará huecos en Python y así no hay traducción. Se documenta en el modelo y en la migración con un CHECK `dia_semana BETWEEN 0 AND 6`. Alternativa descartada: 0 = domingo (convención de JavaScript), que obligaría a un mapeo inverso en cada cálculo del backend.

- **`Disponibilidad.hora_desde/hora_hasta` como `TIME` sin zona; `Bloqueo.desde/hasta` como `timestamptz`.** La plantilla semanal es hora de pared local del consultorio (RN-GL-03): "los lunes de 9 a 13" no es un instante. Un bloqueo sí es un intervalo absoluto y por eso usa `timestamptz`. El schema de disponibilidad rechaza `time` con `tzinfo`; el de bloqueo exige `AwareDatetime` y rechaza naive con 422. Alternativa descartada: guardar la plantilla como `timestamptz` de una semana de referencia (introduce una fecha ficticia y complica la lectura).

- **Intervalos semiabiertos `[desde, hasta)` para el solapamiento.** Dos franjas se solapan si y solo si `a.desde < b.hasta` y `b.desde < a.hasta`; dos franjas contiguas (13:00–17:00 después de 09:00–13:00) no se solapan. Fundamento: es la semántica natural de una agenda de turnos y evita rechazar turnos consecutivos. Alternativa descartada: intervalos cerrados, que considerarían solapadas dos franjas contiguas y obligarían a dejar huecos artificiales de un minuto.

- **Duplicado exacto en la base; solapamiento en el servicio.** La migración crea un UNIQUE `(tenant_id, profesional_id, dia_semana, hora_desde, hora_hasta)`, que ataja el duplicado exacto incluso con concurrencia. El solapamiento parcial no se puede expresar con un UNIQUE simple; se valida en el servicio con una consulta de intersección dentro de la misma transacción. Fundamento: en v1 hay un solo dueño que escribe la plantilla, así que la ventana de carrera es despreciable; se evita agregar `btree_gist`/`EXCLUDE` (extensión y tipos de rango adicionales) por una garantía que C-07 sí necesita para turnos. Alternativa considerada y postergada: `EXCLUDE USING gist` con minutos-del-día en `int4range` y `btree_gist`; si aparecen escrituras concurrentes de varios usuarios, se suma sin cambiar el contrato. El rechazo del servicio usa `RN-AG-01` con `details.reason = "rango_solapado"` (409) o `"rango_invalido"` (422).

- **`Bloqueo.profesional_id` nullable con semántica explícita de consultorio.** Nulo significa "todo el consultorio" (RN-AG-02), nunca "sin efecto". La consulta del profesional filtra `profesional_id = propio OR profesional_id IS NULL`; la recepción y el dueño ven todo. La FK se declara `ON DELETE RESTRICT` (no se borra un profesional con bloqueos) y la columna queda nullable. Alternativa descartada: una fila por profesional al crear un feriado (explota en filas y no expresa la intención).

- **Escritura dueño-only; lectura por rol con alcance.** `POST`/`DELETE` declaran `Depends(require_dueno)`; la recepción y el profesional sin flag reciben 403 `RN-AU-02`. `GET` declara `Depends(require_role(RolUsuario.RECEPCION, RolUsuario.PROFESIONAL))` a nivel de router y resuelve el alcance en el servicio: recepción/dueño ven todo el tenant; el profesional sin flag solo lo propio (más los bloqueos nulos). Si el profesional pide explícitamente otro `profesional_id`, recibe 403 `RN-AU-03`. Fundamento: replica la matriz de `03_actores_y_roles.md` ("Prestaciones / horarios: recepción R, profesional R, dueño CRUD") sin inventar permisos.

- **Resolver `Usuario` → `Profesional` por `Profesional.usuario_id`.** C-06 no puede crear el vínculo, pero lo necesita para saber qué disponibilidad/bloqueos son "propios". Se agrega un helper interno `profesional_de_usuario(session, usuario)` que consulta `Profesional` por `usuario_id` en la sesión tenant-scoped. Si un usuario con rol profesional no tiene fila vinculada, responde 403 `RN-AU-03` con `details.reason = "profesional_no_vinculado"` en lugar de asumir un profesional arbitrario. La comparación de alcance reutiliza `require_acceso_profesional(usuario, profesional.usuario_id)`. Alternativa descartada: agregar `profesional_id` al JWT (C-03 no lo emite y un cambio de vínculo quedaría stale hasta el refresh).

- **Un paquete por recurso dentro de `app/domain/agenda/`.** `app/domain/agenda/disponibilidad/{schemas,service,router}.py` y `app/domain/agenda/bloqueos/{schemas,service,router}.py`, con `agenda/__init__.py` vacío. Fundamento: C-04 está creando en paralelo `agenda/profesionales` y `agenda/prestaciones`; separar por subpaquete evita que dos agentes editen los mismos `schemas.py`/`service.py`. Los modelos van a `app/db/models/disponibilidad.py` y `app/db/models/bloqueo.py` y se exportan desde `app/db/models/__init__.py` (punto compartido inevitable, cambio de una línea). Alternativa descartada: un único `agenda/schemas.py` para todo el dominio (conflicto seguro entre C-04 y C-06).

- **Repositorios específicos sobre `BaseRepository[T]`; `UnitOfWork` sigue siendo el dueño del commit.** `DisponibilidadRepository` y `BloqueoRepository` agregan las consultas de intersección y de alcance, pero no abren sesiones ni hacen commit. El servicio recibe el `UnitOfWork`/repositorio desde la dependencia de la request. Fundamento: R3 y RN-GL-02 se mantienen por construcción. Alternativa descartada: queries directas en el router (salta la frontera de tenant).

- **Errores de dominio reutilizando `RN-AG-01`/`RN-AG-02` y `RN-AU-02`/`RN-AU-03`.** No se inventan códigos nuevos: rango inválido/solapado de disponibilidad → 422/409 `RN-AG-01`; intervalo inválido de bloqueo → 422 `RN-AG-02`; recurso inexistente → 404 con el código de la entidad (`RN-AG-01`/`RN-AG-02`) y `details.reason = "no_encontrado"`; permisos → `RN-AU-02`/`RN-AU-03`. Fundamento: RN-GL-01 exige un código `RN-XX-NN` y el frontend ya distingue por `details.reason`. Queda como pregunta abierta proponer `RN-AG-05` (rango inválido) y `RN-AG-06` (no encontrado) si el equipo prefiere códigos específicos.

- **Sin paginación y con orden determinístico.** `GET /disponibilidad` ordena por `(dia_semana, hora_desde)`; `GET /bloqueos` por `(desde, id)`. La plantilla semanal tiene cardinalidad acotada (7 días × pocas franjas) y los bloqueos se consultan por período en C-08; agregar paginación ahora sería prematuro. `GET` acepta `profesional_id` opcional como filtro (sujeto al alcance del rol).

- **Borrado físico de franjas y bloqueos.** No hay soft delete en v1 (DD-07 post-MVP); eliminar una franja o un bloqueo lo quita de la agenda y libera el intervalo. `DELETE` responde 204 si existía en el tenant y 404 si no. Alternativa descartada: baja lógica, que exigiría columnas y filtros adicionales sin requisito de auditoría en v1.

- **Auditoría con `AuditMixin` aunque la KB no liste timestamps para estas entidades.** Aporta trazabilidad barata y consistencia con el resto de los modelos de dominio; no cambia el contrato visible. `Bloqueo.motivo` es NOT NULL (la KB lo lista sin marca de nulabilidad) y se valida no vacío, para que todo cierre tenga justificación operativa.

- **Migración encadenada al head real, no a un id supuesto.** `CHANGES.md` numera las migraciones por ordinal de dominio: C-02 = "001" (real `0002_tenancy_usuario`), C-04 = "002", C-05 = "003", C-06 = "004", C-07 = "005". Por eso la migración de C-06 es la cuarta migración de dominio y su revisión literal será `0005_disponibilidad_bloqueo` si C-04 usa `0003_*` y C-05 usa `0004_*`; el `down_revision` se fija contra el head que exista al implementar (esperado `0004_*`) y se verifica con `alembic heads` (una sola cabeza) y `alembic history`. No se crea una tabla `profesional` de relleno: si C-04 no está aplicado, la migración de C-06 falla por FK y ese es el orden correcto (ver Riesgos).

- **Tests de integración contra Postgres real, sin mocks de sesión.** Se reutiliza el harness de C-02 (`db_url`, `db_engine`, `clean_db`, `session_factory`, marcador `integration`). Los tests de constraints (CHECK, UNIQUE, FK) y de aislamiento no se pueden reproducir en SQLite. Los tests de API montan la app real con `app_env` y tokens de C-03; las fábricas de agenda viven en un archivo local `backend/tests/agenda_factories.py` (`crear_profesional`, `crear_disponibilidad`, `crear_bloqueo`) para no editar el `factories.py` compartido con C-04/C-05. `crear_profesional` solo se habilita cuando C-04 ya expone el modelo (ver Riesgos).

## Riesgos / Compromisos

- [Riesgo] C-04 no está archivado y C-06 depende de la tabla `profesional` → Mitigación: la migración y los tests de C-06 se ejecutan después de C-04; el `down_revision` se toma del head real y se verifica `alembic heads`. Si al implementar C-06 la tabla no existe, se detiene la implementación y se coordina con C-04; no se crea una tabla de relleno (R7) ni se duplica el CRUD.
- [Riesgo] Numeración de migraciones ambigua entre `CHANGES.md` (ordinal 004) y la revisión literal (`0005_*`) → Mitigación: documentar la correspondencia en la migración y en `tasks.md`; el id final se confirma con `alembic history` y `alembic check` en la verificación integral.
- [Riesgo] Carrera entre dos altas de franjas solapadas (el UNIQUE solo ataja duplicados exactos) → Mitigación: en v1 solo escribe el dueño; el chequeo de solapamiento corre dentro de la transacción del `UnitOfWork`. Si se habilitan varios usuarios con escritura, agregar `EXCLUDE` con `btree_gist` sin cambiar el contrato.
- [Riesgo] `Profesional.usuario_id` nulo o profesional sin login → Mitigación: 403 `RN-AU-03` con `profesional_no_vinculado`; no se asume un profesional por defecto. C-04 decide si todo profesional debe tener usuario.
- [Riesgo] El seed de disponibilidad demo queda a cargo de C-04 y podría no existir si C-04 asume que C-06 lo hace → Mitigación: C-06 no duplica el seed; `tasks.md` incluye una verificación explícita de las filas demo (Lun–Vie 9–13/16–20) y, si faltan, se corrige en C-04 (no en C-06) para no tener dos fuentes de seed.
- [Riesgo] Los timestamps de `Bloqueo` llegan naive desde un cliente mal implementado → Mitigación: `AwareDatetime` en Pydantic y `timestamptz` en la base; test de 422 para naive. La TZ de conexión ya está fijada por C-02.
- [Riesgo] Cambios concurrentes en `app/db/models/__init__.py` y `app/main.py` con C-04/C-05 → Mitigación: cambios mínimos y aditivos (dos imports y dos `include_router`), resueltos al integrar en el orden C-04 → C-05 → C-06.
- [Riesgo] El test de arquitectura de C-03 exige que toda ruta declare auth y roles → Mitigación: declarar `require_role(...)` a nivel de `APIRouter` y `require_dueno` en las escrituras; correr `tests/test_architecture.py` en la verificación.

## Plan de migración

1. Aplicar C-04 (tabla `profesional`) y C-05 (tabla `paciente`) antes que C-06. Verificar `alembic heads` con una sola cabeza y que `profesional` exista.
2. `alembic upgrade head` aplica la revisión de C-06 (esperada `0005_disponibilidad_bloqueo`): tablas `disponibilidad` y `bloqueo`, CHECK de día y de rangos, UNIQUE de duplicado exacto, FKs e índices; `downgrade` las elimina en orden inverso.
3. Registrar los routers en `app/main.py`; no hay variables de entorno nuevas ni dependencias nuevas.
4. Verificación de humo: el dueño crea una franja (201), la recepción la lee (200) y no puede crearla (403); el dueño crea un bloqueo con `profesional_id` nulo (201) y el profesional lo ve en su consulta de bloqueos; un rango invertido responde 422.
5. Rollback: `alembic downgrade <revisión anterior>` elimina las dos tablas; revertir el change quita routers y modelos. No hay datos productivos en v1; el seed demo de disponibilidad de C-04 no se toca.

## Preguntas abiertas

- **Códigos de error específicos de agenda.** Se usan `RN-AG-01`/`RN-AG-02` con `details.reason` porque la KB solo define esos dos. Si el equipo quiere distinguir rango inválido, solapamiento y no encontrado sin parsear `details`, se pueden agregar `RN-AG-05`/`RN-AG-06` en una actualización de `05_reglas_de_negocio.md`; no cambia el contrato HTTP ni los escenarios.
- **`dia_semana` 0 = lunes.** Se asume la convención de Python/ISO. Si el frontend de C-10 usa 0 = domingo, debe traducir en el borde; confirmarlo al implementar C-10.
- **Obligatoriedad de `motivo` en `Bloqueo`.** Se toma NOT NULL porque la KB no lo marca nullable. Si operaciones necesita bloqueos sin motivo, se relaja con una migración aditiva sin cambiar los escenarios.
- **Profesional con login propio.** Se asume que C-04 puede dejar `usuario_id` nulo; C-06 responde 403 si un usuario profesional no tiene profesional vinculado. Confirmar con C-04 si el vínculo será obligatorio para usuarios con rol profesional.
