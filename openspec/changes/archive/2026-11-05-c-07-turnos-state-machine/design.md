# Design

## Context

Ver `proposal.md` para la motivación y los dos deltas para el contrato observable. C-04/C-05/C-06 están archivados; el head real es `0005_disponibilidad_bloqueo`. El ordinal «migración 005» del roadmap quedó histórico: este change agregará `0006_turno`.

La inspección encontró SQLAlchemy declarativo, `TenantSession` con filtro automático, `UnitOfWork` transaccional, roles existentes, vínculo `Profesional.usuario_id`, repositorios de franjas/bloqueos y alcance de pacientes provisional por creador. La guarda `infracciones_turno_en_agenda` impide referencias a `Turno` dentro del catálogo de agenda. C-06 terminó con 409 tests verdes; es antecedente, no una baseline ejecutada por esta planificación.

El usuario resolvió tres contradicciones antes de crear estos artefactos:

1. Reprogramar mueve el mismo registro y conserva código, estado y duración (memoria 379); prevalece sobre «cancelación + reserva» de RN-TU-07 en KB05.
2. Una ficha pertenece al profesional si la creó, ya atendió al paciente o tiene un turno reservado/confirmado con él; cancelado/ausente solos no bastan (memoria 381).
3. Solo se editan estado y horario. Cambiar paciente, profesional o prestación exige cancelar y crear otro turno; no habrá DELETE físico (memoria 383).

**Gobernanza CRÍTICA: implementación pendiente de aprobación humana explícita.** La propuesta no ejecuta tests, no edita producción ni la KB principal y no inicia `apply`.

## Goals / Non-Goals

**Goals:** integrar los dominios existentes con una frontera única de escritura de turnos, transacciones verificables en PostgreSQL y permisos coherentes en la ficha del paciente; mantener explícita la duración congelada.

**Non-Goals:** enumerar huecos o sugerir el siguiente horario (C-08), abrir rutas por código (C-09), agregar UI (C-10), recordatorios, auditoría formal o modificar el core de JWT/tenancy. Tampoco se impedirán aquí cambios de plantilla/bloqueo por la mera existencia de turnos previos: C-06 no cancela turnos automáticamente.

## Decisions

### 1. Dominio de turnos separado y servicio único

Crear `app/domain/turnos/{schemas,repository,service,router,estados,codigos}.py`; dejar `app/domain/agenda` sin importar `Turno`. El servicio puede leer catálogos, franjas y bloqueos mediante la sesión del mismo UoW. Routers y seed invocan el servicio: no crean entidades ni asignan estados por fuera de él (R4). Reutilizar `alcance_agenda`, `profesional_de_usuario` y las dependencias de roles actuales; no cambiar su semántica ni archivos de auth/core.

Alternativa descartada: colocar turnos dentro de `agenda`, lo que obligaría a debilitar una guarda que protege al catálogo de escrituras laterales. Las consultas futuras de C-08 consumirán el contrato de turnos sin mover las escrituras fuera de este dominio.

### 2. Modelo y migración que reflejan el esquema real

`Turno` usa `TenantMixin`/`AuditMixin`, UUID, FKs `profesional_id`, `paciente_id`, `prestacion_id` con `RESTRICT`, `inicio/fin` timezone-aware, enum con valores españoles, `codigo_publico String(12)` unique, flag y `motivo_sobreturno` nullable, `motivo_cancelacion` nullable. Incluir CHECK de `fin > inicio`, código de longitud 12 y consistencia flag/motivo. Los índices son `(tenant_id, profesional_id, inicio)` y `(tenant_id, estado, inicio)` además del unique del código.

La revisión `0006_turno` tendrá `down_revision = '0005_disponibilidad_bloqueo'`, creará `btree_gist` si falta y el enum explícitamente. El downgrade elimina solo los objetos propios de turno; conserva extensiones compartidas y las tablas C-04/C-05/C-06.

Usar `ExcludeConstraint` equivalente a `(tenant_id WITH =, profesional_id WITH =, tstzrange(inicio, fin, '[)') WITH &&) WHERE estado <> 'cancelado'`. `tstzrange`, no el `tsrange` histórico del documento, corresponde a `timestamptz`. La frontera semiabierta admite contiguos; `ausente` permanece en el predicado según RN-TU-05. Nombre estable: `ex_turno_profesional_no_solape`; unique del código: `uq_turno_codigo_publico`.

Las FKs por UUID siguen el patrón existente. Antes de crear se resuelven las tres referencias con repositorios tenant-scoped; el profesional y la prestación deben estar activos. No agregar constraints ni migraciones a los catálogos solo para duplicar sus PKs. Las pruebas de API/servicio deben demostrar que ninguna referencia de otro tenant llega a la escritura.

### 3. Validador de candidato, sin construir el motor de huecos

El servicio de creación valida el intervalo concreto recibido, con reloj inyectable en pruebas: input `AwareDatetime`, conversión a `ZoneInfo(settings.tz)`, inicio estrictamente futuro, fin calculado con la duración vigente de la prestación. Para la plantilla, leer franjas del profesional/día, unir contiguas y comprobar cobertura completa del intervalo; no basta que el inicio caiga dentro. Si cruza medianoche, comprobar los segmentos de ambos días. Consultar intersección `bloqueo.desde < fin AND inicio < bloqueo.hasta` con `(profesional_id = solicitado OR profesional_id IS NULL)`. Consultar ocupación con el mismo criterio y todos los estados excepto cancelado.

El sobreturno exige motivo de urgencia no vacío y flag explícito, se conserva como `motivo_sobreturno`, nace confirmado y omite únicamente la comprobación de plantilla. Mantiene futuro, bloqueos, referencias, alcance y anti-solape. No se depende del nombre de la prestación «Urgencia»: no existe un marcador de catálogo que permita esa vinculación y la regla exige flag/motivo, no una comparación de nombres.

Alternativa descartada: diferir toda validación a C-08 y permitir escrituras inválidas entretanto. C-08 enumerará opciones; C-07 garantiza las invariantes de una reserva puntual. No se devuelve una sugerencia de siguiente hueco desde C-07.

### 4. Transacciones, concurrencia y códigos

Cada escritura abre un solo UoW; las operaciones sobre un turno existente obtienen su fila tenant-scoped con `SELECT FOR UPDATE`, verifican alcance y evalúan el estado persistido bajo el lock. Las consultas de disponibilidad y ocupación están dentro de esa transacción. La restricción EXCLUDE resuelve la carrera de dos inserciones aun cuando ambas consultas previas resulten libres. Traducir la violación del constraint nombrado a 409 `RN-TU-01`; no reinterpretar cualquier `IntegrityError` como solape.

Generar el código con `secrets.token_urlsafe(9)`: 9 bytes aleatorios, 12 caracteres base64url, 72 bits. La unicidad es global como pide el modelo. Una colisión del constraint específico reintenta hasta cinco veces dentro de savepoints con una entidad nueva por intento; un agotamiento responde 409 `RN-GL-01`, `details.reason='codigo_no_disponible'`, sin turno parcial. No reintentar un EXCLUDE ni violaciones de otras reglas.

La máquina pura define solo cinco aristas permitidas y no escribe DB. El servicio es quien bloquea, valida, asigna estado y confirma. Se parametrizan las 25 combinaciones origen/destino; repetir el mismo estado también es 422. La cancelación guarda motivo opcional y no borra filas.

### 5. Reprogramación in situ con duración congelada

Bloquear fila, admitir solo reservado/confirmado, guardar `duracion = fin - inicio`, validar `nuevo_inicio` y `nuevo_fin = nuevo_inicio + duracion`, excluir el id propio de la consulta anti-solape y actualizar solo inicio/fin. La excepción de plantilla se conserva si el turno era sobreturno; ni flag ni motivo se editan en este paso. No recalcular desde la prestación ni cancelar/crear filas. El UoW revierte cualquier violación del EXCLUDE al confirmar, incluida una carrera por el destino.

Alternativa descartada por decisión del usuario: cancelar y crear otro turno, que cambiaría identidad/código y podría perder el estado confirmado. El test concurrente debe comprobar el horario original después del rollback, no solo el status de respuesta.

### 6. Contrato HTTP explícito y compatible con el roadmap

| Operación | Entrada y resultado |
|---|---|
| `GET /turnos` | Filtros profesional/estado/desde/hasta y limit/offset; rango de inicio semiabierto; orden inicio/id; lista de turnos del alcance |
| `POST /turnos` | profesional_id, paciente_id, prestacion_id, inicio, es_sobreturno=false, motivo_sobreturno opcional; 201 |
| `GET /turnos/{id}` | 200 o 404; 403 si existe en tenant pero fuera de alcance |
| `PATCH /turnos/{id}` | estado requerido; motivo_cancelacion solo para cancelado; 200 tras máquina común |
| `POST .../confirmar`, `.../atender`, `.../registrar-ausencia` | Sin campos de negocio; fijan el destino correspondiente; 200 |
| `POST .../cancelar` | motivo_cancelacion opcional; 200 y registro conservado |
| `POST .../reprogramar` | nuevo_inicio únicamente; 200 y mismo turno |

No registrar DELETE. Los esquemas `extra='forbid'` y sus restricciones rechazan fin/código/tenant/referencias editadas. Body vacío del PATCH es 422 por falta de estado; motivo_cancelacion con otro destino es 422. Las acciones sin datos usan un esquema vacío para rechazar campos inesperados cuando se envía un body; no se ignoran parámetros de negocio enviados a esas acciones. Los datos de salida contienen ids de referencias y datos del turno, no la ficha de Paciente.

Usar APIRouter con prefix/tags/dependencia de roles, alias Annotated y rutas sync con la sesión sync del proyecto. Recepción/dueño operan todas las agendas; el profesional vinculado opera solo la propia. Para crear, además del profesional propio, un profesional sin flag debe tener acceso a la ficha seleccionada mediante el predicado del apartado siguiente; recepción/dueño pueden asignar cualquier paciente del tenant. Esto evita que alguien se conceda acceso a una ficha ajena enviando su id al crear una cita. Las rutas internas nunca aceptan código en sustitución de JWT.

Errores de dominio: ocupación 409 RN-TU-01; sobreturno inconsistente 422 RN-TU-03; transición/reprogramación terminal 422 RN-TU-04; fuera de plantilla/pasado 422 RN-AG-01; bloqueo 409 RN-AG-02; fuera de alcance 403 RN-AU-03; referencia inexistente/ajena 404 RN-TU-01 con `details.reason='no_encontrado'`; catálogo inactivo 422 RN-TU-02 con `details.reason='referencia_inactiva'`. Los errores ordinarios de validación de esquema conservan el contrato 422 del proyecto.

### 7. Predicado único de pertenencia del paciente

Ampliar `app/domain/pacientes` con un helper de condición SQL reutilizable: `creado_por_usuario_id == usuario_id OR EXISTS(...)`. El EXISTS correlaciona paciente, tenant, Turno y el `Profesional.usuario_id`; solo admite estados reservado/confirmado/atendido. El filtro tenant se expresa también en las subconsultas, no se infiere de los ids recibidos. La condición de permiso de lectura/edición debe consultar el mismo predicado usando la sesión del llamador; cambiar las firmas de los helpers y sus call sites, sin abrir otra sesión ni duplicar reglas.

Aplicarlo a `_consulta_busqueda`, `_buscar_duplicados`, `crear_o_reutilizar_paciente` con alcance propio y `exigir_acceso_paciente`. Conservar la rama pública de reutilización TODOS/usuario_id=None y su advertencia sin ficha. Si el profesional no tiene vínculo, la rama EXISTS no concede pacientes; sí conserva los que creó. No se materializa una tabla de propiedad ni se otorga acceso permanente al crear un turno: la consulta refleja su estado actual, de modo que cancelar la última cita no atendida revoca el vínculo al siguiente request. No se alteran tokens, roles ni la guarda del core.

### 8. Seed y reconciliación documental

Ampliar el seed a través del servicio: tres ejemplos no superpuestos del profesional demo y los pacientes ficticios existentes, con creación normal y transiciones válidas hasta confirmado/atendido. Elegir al crearlos un día futuro cubierto por las franjas demo; el estado atendido de ejemplo no incorpora una regla nueva de tiempo de atención. El servicio ofrece una entrada interna de seed con identificadores deterministas por tenant/ejemplo, nunca aceptados desde HTTP, para reconocerlos sin depender del horario o estado que luego cambie el usuario. La reejecución no modifica ejemplos existentes; si el catálogo no permite crear un ejemplo nuevo, informar omisión y no forzar una escritura inválida.

Durante apply, alinear KB05 RN-TU-07, KB02 rutas, KB03 fila de turnos/alcance, KB04 `tstzrange` y atributo motivo_sobreturno, y CHANGES C-07 (ordinal de migración y acción atender). No cambiar el contenido de decisiones aún no implementadas de C-08/C-09/C-10. Se conserva la deuda DD-07: no se agrega auditoría formal ni soft delete; la cancelación y las FKs RESTRICT preservan la fila del turno.

## Risks / Trade-offs

- [El core de pacientes amplía un permiso crítico] → predicado único, pruebas positivas y negativas por cada vía, casos cancelado/ausente y rollback; aprobar este diseño antes de apply.
- [La consulta previa no bloquea una reserva competidora] → EXCLUDE es la defensa final; pruebas de dos conexiones con barrera real, sin simular la carrera con mocks.
- [Un cambio de horario/bloqueo concurrente puede volver inválida una agenda existente] → no se promete cancelación automática ni serialización con la configuración C-06; cada alta/reprogramación valida lo visible en su transacción. No ampliar C-06 silenciosamente.
- [Las FKs por UUID no codifican pertenencia compuesta] → toda alta usa resolución tenant-scoped y guardas del servicio; no se exponen escrituras directas. Si se pidiera reforzar SQL manual con FKs compuestas, sería un change adicional sobre catálogos.
- [El seed interactúa con tests que simulan esquemas antiguos] → extender sus regresiones sin borrar tablas reales al finalizar; mantener las 409 pruebas previas.
- [Entorno Python o servicios de prueba incorrectos] → Python 3.12 y `uv run --frozen`, Postgres/Redis aislados; base literal `turnos_test` en el Postgres de pruebas, sin puertos del stack manual. Ningún `down -v` ni sobreescritura de `.env`.

## Migration Plan

1. Tras aprobación explícita de implementación, recuperar estado CLI y baseline de pruebas de los archivos afectados antes de producción; detenerse ante fallos preexistentes reales.
2. Ejecutar los ciclos RED/GREEN/TRIANGULATE/REFACTOR definidos en `tasks.md` sobre PostgreSQL real. La nueva revisión se prueba desde una base vacía y desde head C-06; downgrade/upgrade conserva los datos y tablas anteriores.
3. Verificar suite completa, guardas, E2E en base nueva, Ruff, metadata sin diferencias, un único head y validación estricta de change/specs. No se actualiza automáticamente la demo manual del usuario.
4. Revisar el resultado y después sincronizar deltas/archivar según el flujo solicitado. Actualizar CHANGES al cerrar; no commit ni push sin pedido explícito.
5. Rollback de despliegue: detener escrituras y volver a la imagen C-06; ejecutar downgrade solo con aprobación porque elimina datos de turnos. No eliminar extensiones compartidas, pacientes, catálogos ni datos C-06.
