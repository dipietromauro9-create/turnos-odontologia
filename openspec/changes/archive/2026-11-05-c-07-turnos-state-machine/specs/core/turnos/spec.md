# Spec Delta

## Purpose

Define los turnos internos del consultorio, su duración y código de gestión, la prevención de solapamientos y las operaciones transaccionales de estado y reprogramación, respetando el alcance de tenant y profesional.

## ADDED Requirements

### Requirement: El turno conserva referencias válidas y duración congelada (RN-TU-02, RN-AG-03)

El sistema DEBE (SHALL) persistir cada turno dentro del tenant resuelto con profesional, paciente y prestación existentes en ese mismo tenant; inicio y fin con zona horaria; estado; código público único; indicador de sobreturno; motivo de urgencia cuando corresponda; motivo de cancelación nullable y timestamps. Al crear, DEBE (SHALL) calcular `fin = inicio + duracion_min` de la prestación activa. El cliente NUNCA DEBE (SHALL) enviar `fin`, estado inicial, código, tenant ni identificador de autor como campos de creación. Cambiar la duración del catálogo NO DEBE (SHALL) cambiar un turno existente. Las referencias profesional/paciente/prestación DEBEN (SHALL) ser inmutables en ese turno; no DEBE (SHALL) haber borrado físico HTTP de turnos ni borrado en cascada de sus referencias.

#### Scenario: El backend calcula el fin
- **WHEN** se crea un turno con inicio `2030-06-03T09:00:00-03:00` para una prestación activa de 30 minutos
- **THEN** el turno termina a las `09:30:00-03:00`, tiene `fin > inicio` y pertenece al tenant resuelto

#### Scenario: Cambiar el catálogo no cambia el turno
- **WHEN** después de crear el turno se cambia la prestación de 30 a 45 minutos
- **THEN** el inicio, el fin y la duración de ese turno permanecen iguales

#### Scenario: No se aceptan campos calculados o referencias editadas
- **WHEN** un cliente envía `fin` al crear o intenta cambiar profesional, paciente o prestación mediante `PATCH`
- **THEN** recibe HTTP 422 y no se persiste el cambio

#### Scenario: Una referencia ajena al tenant no se utiliza
- **WHEN** se intenta crear un turno con un profesional, paciente o prestación que solo existe en otro tenant
- **THEN** se responde HTTP 404 sin crear el turno ni revelar datos de la referencia ajena

#### Scenario: No se reserva un catálogo desactivado
- **WHEN** se intenta crear un turno con profesional inactivo o prestación inactiva del tenant
- **THEN** se responde HTTP 422 y no se crea ningún turno

### Requirement: La reserva normal usa un horario futuro habilitado (RN-AG-01, RN-AG-02)

El sistema DEBE (SHALL) crear el turno normal en `reservado` solo si `inicio` es futuro, el intervalo completo cabe en la disponibilidad semanal del profesional y no intersecta bloqueos personales o globales ni otros turnos que ocupan el horario. Los horarios semanales DEBEN (SHALL) interpretarse en America/Argentina/Buenos_Aires. Las franjas contiguas DEBEN (SHALL) poder cubrir juntas el intervalo sin inventar un descanso entre ellas. Un bloqueo global (`profesional_id = null`) DEBE (SHALL) impedir reservar a cualquier profesional. Un horario fuera de plantilla o pasado DEBE (SHALL) rechazarse con HTTP 422 y `RN-AG-01`; una intersección con bloqueo DEBE (SHALL) rechazarse con HTTP 409 y `RN-AG-02`.

#### Scenario: Reserva normal dentro de la plantilla
- **WHEN** se solicita un intervalo futuro completamente contenido en las franjas semanales del profesional y no hay bloqueos ni turnos ocupantes
- **THEN** se crea un único turno en `reservado` con HTTP 201

#### Scenario: El intervalo completo debe caber
- **WHEN** hay disponibilidad de 9 a 10 y se intenta reservar una prestación de 30 minutos a las 9:45
- **THEN** se responde HTTP 422 con `RN-AG-01` sin crear el turno

#### Scenario: La frontera contigua no genera un cierre ficticio
- **WHEN** existen franjas 9–12 y 12–15 del mismo día y se solicita un turno futuro de 11:45 a 12:15
- **THEN** el intervalo satisface la disponibilidad semanal porque las franjas son contiguas

#### Scenario: El inicio pasado o igual al presente se rechaza
- **WHEN** se solicita un inicio anterior o igual al instante actual
- **THEN** se responde HTTP 422 con `RN-AG-01` sin crear el turno

#### Scenario: El cierre de todo el consultorio impide reservar
- **WHEN** un bloqueo con profesional nulo intersecta el intervalo solicitado
- **THEN** se responde HTTP 409 con `RN-AG-02`, incluso si la plantilla semanal lo permite

#### Scenario: Los bloqueos personales no cierran otra agenda
- **WHEN** el único bloqueo intersectante pertenece a otro profesional del mismo tenant
- **THEN** ese bloqueo no impide la reserva del profesional solicitado

### Requirement: El horario ocupado nunca se superpone bajo concurrencia (RN-TU-01, RN-TU-05)

El sistema DEBE (SHALL) impedir dos turnos superpuestos del mismo tenant y profesional, tanto mediante una validación legible como mediante la garantía final de la base de datos. Los intervalos DEBEN (SHALL) ser semiabiertos `[inicio, fin)`, de modo que dos turnos contiguos sean válidos. Todo estado distinto de `cancelado`, incluido `ausente`, DEBE (SHALL) ocupar su intervalo. Un conflicto de ocupación DEBE (SHALL) responder HTTP 409 con `RN-TU-01`, sin exponer datos del turno que ocupa el horario y sin dejar escrituras parciales. El sobreturno NO DEBE (SHALL) eludir esta regla.

#### Scenario: Los turnos contiguos se permiten
- **WHEN** existe un turno de 9 a 9:30 y se reserva otro de 9:30 a 10 para el mismo profesional
- **THEN** no se considera solapamiento

#### Scenario: La carrera entre dos reservas tiene un único ganador
- **WHEN** dos transacciones independientes intentan reservar intervalos intersectantes para el mismo profesional y ambas superan la consulta previa
- **THEN** exactamente una confirma el alta y la otra recibe conflicto `RN-TU-01`; solo queda una fila ocupante

#### Scenario: El sobreturno también respeta el conflicto
- **WHEN** un sobreturno de urgencia intersecta un turno no cancelado
- **THEN** se responde HTTP 409 con `RN-TU-01` sin crear el sobreturno

#### Scenario: Cancelar libera y ausente conserva la ocupación
- **WHEN** se intenta reservar sobre el intervalo de un turno cancelado y sobre el de otro marcado ausente
- **THEN** el cancelado no impide reservar y el ausente sí produce HTTP 409 con `RN-TU-01`

#### Scenario: Distintos profesionales no comparten la restricción
- **WHEN** dos profesionales del tenant reciben turnos en el mismo intervalo
- **THEN** no hay conflicto por superposición entre esos profesionales

### Requirement: El sobreturno de urgencia es explícito y trazable (RN-TU-03)

El sistema DEBE (SHALL) exigir `es_sobreturno = true` y un motivo de urgencia no vacío para un sobreturno. DEBE (SHALL) conservar ese motivo y crear el turno en `confirmado`. El sobreturno DEBE (SHALL) permitir un intervalo futuro fuera de la plantilla semanal, pero NUNCA DEBE (SHALL) ignorar bloqueos personales/globales ni la ocupación anti-solape. Un motivo de sobreturno sin el flag, o el flag sin motivo, DEBE (SHALL) rechazarse con HTTP 422 y código `RN-TU-03`.

#### Scenario: Urgencia fuera de horario semanal
- **WHEN** se crea un sobreturno futuro fuera de la plantilla, con motivo de urgencia no vacío y sin bloqueos ni ocupación
- **THEN** responde HTTP 201 en `confirmado` y conserva el motivo

#### Scenario: El flag sin motivo no basta
- **WHEN** se envía `es_sobreturno = true` sin motivo o con un motivo de solo espacios
- **THEN** se responde HTTP 422 con `RN-TU-03` y no se crea el turno

#### Scenario: El motivo no activa el flag implícitamente
- **WHEN** se envía un motivo de sobreturno con el flag ausente o falso
- **THEN** se responde HTTP 422 con `RN-TU-03`

#### Scenario: Un bloqueo conserva su efecto ante una urgencia
- **WHEN** un sobreturno válido intersecta un cierre global o personal
- **THEN** se responde HTTP 409 con `RN-AG-02` sin reservar

### Requirement: Toda transición usa la máquina y es atómica (RN-TU-04, RN-GL-02)

El sistema DEBE (SHALL) admitir únicamente `reservado → confirmado|cancelado` y `confirmado → atendido|cancelado|ausente`. Los estados `atendido`, `cancelado` y `ausente` DEBEN (SHALL) ser terminales. Cualquier otra transición, incluidas las repeticiones del mismo estado, DEBE (SHALL) responder HTTP 422 con `RN-TU-04` sin modificar la fila. Las acciones y `PATCH` DEBEN (SHALL) compartir esta misma semántica y serializar operaciones concurrentes sobre el turno. Cancelar DEBE (SHALL) conservar el turno y guardar el motivo opcional de cancelación, sin exigir un texto. Ninguna transición DEBE (SHALL) cambiar el horario, el código o las referencias del turno.

#### Scenario: Se recorren todas las transiciones permitidas
- **WHEN** se pide cada uno de los cinco pares origen/destino admitidos
- **THEN** se persiste exactamente el estado destino y se conservan las demás propiedades del turno

#### Scenario: Todas las demás combinaciones se rechazan
- **WHEN** se pide cualquier par de estados fuera de los cinco permitidos, incluidos pares idénticos y salidas de terminales
- **THEN** se responde HTTP 422 con `RN-TU-04` y el turno queda intacto

#### Scenario: Cancelar conserva el motivo opcional
- **WHEN** se cancela un turno permitido con motivo o sin motivo
- **THEN** el registro permanece en `cancelado`, con el motivo enviado o nulo, y su hueco deja de estar ocupado

#### Scenario: Dos transiciones concurrentes no usan un estado obsoleto
- **WHEN** una cancelación y una confirmación concurrentes apuntan al mismo turno reservado
- **THEN** se evalúan secuencialmente contra el estado persistido y ninguna operación sobrescribe una transición prohibida

### Requirement: Reprogramar mueve el mismo turno y conserva su duración (RN-TU-07 aprobado)

El sistema DEBE (SHALL) reprogramar únicamente turnos `reservado` o `confirmado`, moviendo el mismo registro y conservando id, código público, estado, profesional, paciente, prestación, indicador y motivo de sobreturno, y duración congelada `fin - inicio`. El nuevo fin DEBE (SHALL) calcularse sumando esa duración al nuevo inicio, incluso si cambió el catálogo. El destino DEBE (SHALL) revalidar futuro, plantilla o excepción de sobreturno, bloqueos y anti-solape, excluyendo el propio turno del conflicto. Todo DEBE (SHALL) ocurrir en una sola transacción: un destino inválido DEBE (SHALL) dejar intacto el turno original, sin crear otra fila ni cancelar la existente. Reprogramar un terminal DEBE (SHALL) responder HTTP 422 con `RN-TU-04`.

#### Scenario: Se conserva identidad y estado al mover
- **WHEN** se reprograma un turno reservado o confirmado hacia un destino válido
- **THEN** solo cambian inicio, fin y timestamp de actualización; id, código, estado y duración permanecen iguales

#### Scenario: Cambiar la prestación no cambia la duración congelada
- **WHEN** un turno de 30 minutos se reprograma después de aumentar la prestación a 45 minutos
- **THEN** el nuevo intervalo sigue durando 30 minutos y no se sustituye su código

#### Scenario: El destino ocupado deja el original intacto
- **WHEN** el destino intersecta otro turno ocupante
- **THEN** se responde HTTP 409 con `RN-TU-01` y el turno original conserva todas sus propiedades, sin filas nuevas

#### Scenario: El destino bloqueado o fuera de plantilla también revierte
- **WHEN** se intenta mover un turno normal a un bloqueo o fuera de disponibilidad
- **THEN** se responde el error correspondiente de agenda y el original permanece intacto

#### Scenario: Reprogramar a un intervalo que intersecta al propio turno es posible
- **WHEN** el nuevo horario intersecta únicamente el intervalo original del mismo turno y cumple las demás reglas
- **THEN** no se lo trata como conflicto contra sí mismo

#### Scenario: Un terminal no se mueve
- **WHEN** se pide reprogramar un turno atendido, cancelado o ausente
- **THEN** se responde HTTP 422 con `RN-TU-04` sin modificarlo

#### Scenario: La carrera por el destino no deja una cancelación parcial
- **WHEN** una reserva concurrente ocupa el destino antes de confirmar la reprogramación
- **THEN** la reprogramación responde HTTP 409 con `RN-TU-01` y el turno original permanece en su horario y estado anteriores

### Requirement: La API interna limita la edición y el alcance (RN-AU-03)

El sistema DEBE (SHALL) exponer `GET/POST /turnos`, `GET/PATCH /turnos/{id}` y `POST /turnos/{id}/confirmar|atender|cancelar|registrar-ausencia|reprogramar` bajo autenticación y roles explícitos. Recepción y dueño DEBEN (SHALL) operar todos los turnos de su tenant; el profesional sin flag DEBE (SHALL) consultar y operar solo los vinculados a su propio profesional. Los listados DEBEN (SHALL) permitir filtros opcionales de profesional, estado y rango `desde`/`hasta` de inicio `[desde, hasta)`, con `limit` de 1 a 100 (20 por defecto) y `offset >= 0`, ordenados por inicio e id. Un recurso de otro tenant o inexistente DEBE (SHALL) devolver 404; uno del mismo tenant fuera del alcance DEBE (SHALL) devolver 403 `RN-AU-03`. `PATCH` DEBE (SHALL) exigir estado destino y admitir únicamente `estado` y `motivo_cancelacion` cuando el destino es cancelado; reprogramar DEBE (SHALL) admitir únicamente `nuevo_inicio`. Cambiar paciente/profesional/prestación requiere cancelar y crear otro turno. No DEBE (SHALL) existir `DELETE /turnos/{id}`. Las respuestas DEBEN (SHALL) mostrar referencias por id y datos del turno, sin incrustar fichas de pacientes. Todas las fechas de entrada DEBEN (SHALL) llevar zona horaria y todos los esquemas DEBEN (SHALL) rechazar campos desconocidos.

Para crear un turno, el profesional sin flag DEBE (SHALL) tener acceso previo a la ficha seleccionada según el alcance asistencial vigente, además de operar su propia agenda. No DEBE (SHALL) poder concederse acceso a una ficha ajena creando unilateralmente una cita con su id. Recepción y dueño DEBEN (SHALL) poder asignar cualquier paciente existente del tenant.

#### Scenario: Sin login ninguna operación accede a turnos
- **WHEN** se llama sin token a cualquiera de las rutas internas de turnos
- **THEN** se responde HTTP 401 antes de leer o escribir datos

#### Scenario: Recepción y dueño operan todas las agendas del tenant
- **WHEN** recepción o dueño consulta, crea o transiciona un turno de cualquier profesional del tenant
- **THEN** el alcance no impide la operación, manteniéndose las demás reglas de negocio

#### Scenario: El profesional solo opera su propia agenda
- **WHEN** un profesional sin flag lista turnos sin filtro
- **THEN** recibe únicamente los de su profesional vinculado; un filtro, id o alta para otro profesional del tenant devuelve 403 `RN-AU-03`

#### Scenario: Sin profesional vinculado no se abre la agenda
- **WHEN** un profesional sin flag y sin vínculo de profesional usa la API de turnos
- **THEN** recibe HTTP 403 con `RN-AU-03`

#### Scenario: Crear una cita no permite apropiarse de una ficha ajena
- **WHEN** un profesional sin flag intenta crear en su agenda un turno para un paciente que no cumple ningún vínculo de acceso previo
- **THEN** se responde HTTP 403 con `RN-AU-03` y no se crea el turno; recepción o dueño sí pueden efectuar la asignación dentro del tenant

#### Scenario: La lectura y la escritura no cruzan tenant
- **WHEN** se pide un id o se envían referencias que pertenecen solo a otro tenant
- **THEN** se responde HTTP 404 sin datos ni efectos en el otro tenant

#### Scenario: La edición no permite cambiar referencias o horario indirectamente
- **WHEN** `PATCH` recibe `inicio`, `fin`, `paciente_id`, `profesional_id`, `prestacion_id`, `codigo_publico` o un campo desconocido
- **THEN** responde HTTP 422 y el turno conserva su contenido

#### Scenario: Cambiar estado usa el mismo contrato por ambas rutas
- **WHEN** una transición se solicita por su acción POST o por `PATCH` con el mismo destino
- **THEN** produce los mismos efectos y los mismos errores de máquina y alcance

#### Scenario: Los filtros y la paginación son deterministas
- **WHEN** se lista por profesional, estado y rango de inicio con `limit` y `offset`
- **THEN** se devuelve solo la intersección de filtros dentro del alcance y en orden inicio/id; límites inválidos o `hasta <= desde` producen 422

#### Scenario: No se borra el historial por HTTP
- **WHEN** se llama `DELETE /turnos/{id}`
- **THEN** se rechaza el método y el turno no se elimina

### Requirement: El código público es aleatorio y no abre rutas todavía (RN-TU-06)

El sistema DEBE (SHALL) generar un código único de exactamente 12 caracteres con al menos 70 bits de entropía criptográfica por turno y conservarlo durante transiciones y reprogramaciones. No DEBE (SHALL) derivarlo del id, paciente o fecha. Una colisión DEBE (SHALL) provocar un nuevo intento acotado sin dejar un turno parcial ni devolver un código ya usado. C-07 NO DEBE (SHALL) agregar rutas públicas, aceptar el código como sustituto de JWT en las rutas internas ni devolver datos de pacientes desde rutas públicas existentes. Las rutas de operación por código se incorporarán en C-09.

#### Scenario: Los códigos tienen el formato y entropía previstos
- **WHEN** se crean turnos diferentes
- **THEN** cada código tiene 12 caracteres del alfabeto base64url, proviene de 9 bytes criptográficamente aleatorios (72 bits) y es único

#### Scenario: La colisión no deja una reserva duplicada
- **WHEN** el generador devuelve primero un código ya existente y después uno libre
- **THEN** se crea un único turno con el segundo código; si se agotan los intentos se devuelve un error de dominio controlado sin crear el turno

#### Scenario: Un código válido no autentica una ruta de panel
- **WHEN** se llama a `/turnos/{id}` sin JWT, enviando solo un código válido
- **THEN** se responde HTTP 401 y no se devuelve información del turno

### Requirement: El seed agrega tres turnos ficticios sin duplicar (R4, R9)

El sistema DEBE (SHALL) ampliar el seed del tenant demo con tres turnos de ejemplo, uno reservado, uno confirmado y uno atendido, con intervalos distintos y datos exclusivamente ficticios. Las creaciones y transiciones del seed DEBEN (SHALL) pasar por el mismo dominio de turnos. Reejecutar el seed DEBE (SHALL) conservar ids, códigos, horarios y estados existentes sin duplicar turnos ni reabrirlos, incluso si un usuario ya modificó esos ejemplos.

#### Scenario: El primer seed crea los tres ejemplos
- **WHEN** se ejecuta el seed sobre una base recién migrada con el catálogo, pacientes y horarios demo
- **THEN** hay tres turnos ficticios no superpuestos, uno por cada estado de ejemplo, y todos tienen fin calculado y código único

#### Scenario: Repetir no modifica los ejemplos
- **WHEN** se vuelve a ejecutar el seed, incluso después de que uno de los ejemplos fue cancelado o reprogramado manualmente
- **THEN** no se crean duplicados ni se sobrescriben ids, códigos, estados, motivos u horarios existentes
