# core/reportes Specification

## Purpose

Da al dueño del consultorio métricas accionables sobre el uso de la agenda —ocupación, ausentismo y efectividad de los recordatorios— y una salida CSV asíncrona de sus turnos y pacientes, para decidir horarios y evitar el lock-in sin bloquear la API.

## Requirements

### Requirement: La ocupación se mide en minutos sobre la capacidad disponible

El sistema DEBE (SHALL) calcular la ocupación de cada profesional en un período como minutos ocupados por turnos divididos por minutos disponibles, ambos dentro del rango solicitado (RN-RP-01). Los minutos disponibles DEBEN (SHALL) surgir de la plantilla semanal del profesional menos los bloqueos que la intersectan (propios o globales del consultorio). Los minutos ocupados DEBEN (SHALL) sumar la duración de los turnos cuyo inicio cae en el rango y cuyo estado no es `cancelado`; un turno `ausente` SÍ DEBE (SHALL) ocupar su intervalo (RN-TU-05). Si no hay minutos disponibles, la ocupación DEBE (SHALL) informarse como cero, nunca como división por cero.

#### Scenario: Ocupación de una agenda con turnos y huecos

- **WHEN** en el período hay 120 minutos de plantilla, un turno `confirmado` de 30 minutos y un turno `atendido` de 30 minutos
- **THEN** la respuesta informa 60 minutos ocupados sobre 120 disponibles y una ocupación de 0,5

#### Scenario: Un turno ausente sigue ocupando

- **WHEN** el único turno del período está en estado `ausente`
- **THEN** sus minutos cuentan como ocupados

#### Scenario: Un turno cancelado libera el hueco

- **WHEN** el único turno del período está en estado `cancelado`
- **THEN** los minutos ocupados son cero y la ocupación es 0

#### Scenario: Un bloqueo reduce la capacidad disponible

- **WHEN** la plantilla del período suma 120 minutos y existe un bloqueo de 60 minutos que la intersecta
- **THEN** los minutos disponibles son 60 y la ocupación se calcula sobre ese valor

#### Scenario: Sin disponibilidad configurada la ocupación es cero

- **WHEN** el profesional no tiene franjas de plantilla en el período
- **THEN** la ocupación informada es 0 sin error de división

### Requirement: La tasa de ausencia se calcula sobre atendidos y ausentes

El sistema DEBE (SHALL) calcular la tasa de ausencia de cada profesional como turnos `ausente` divididos por la suma de turnos `atendido` y `ausente` del período (RN-RP-01). Los turnos en otros estados NO DEBEN (SHALL NOT) entrar en el denominador, y sin atendidos ni ausentes la tasa DEBE (SHALL) informarse como cero.

#### Scenario: Cálculo de la tasa

- **WHEN** en el período hay 3 turnos `atendido` y 1 turno `ausente`
- **THEN** la tasa de ausencia informada es 0,25

#### Scenario: Sin turnos cerrados la tasa es cero

- **WHEN** en el período solo hay turnos `reservado` y `confirmado`
- **THEN** la tasa de ausencia informada es 0

### Requirement: La efectividad de recordatorios expone la métrica IN-03

El sistema DEBE (SHALL) informar, por profesional y período, la cantidad de turnos `confirmado` y la cantidad de recordatorios en estado `enviado`, junto con su ratio `enviados / confirmados` (IN-03). Sin turnos confirmados el ratio DEBE (SHALL) informarse como cero. Solo los recordatorios `enviado` DEBEN (SHALL) contar en el numerador.

#### Scenario: Ratio de recordatorios enviados

- **WHEN** en el período hay 4 turnos confirmados y 3 recordatorios enviados
- **THEN** el reporte informa 4 confirmados, 3 enviados y un ratio de 0,75

#### Scenario: Un recordatorio pendiente no cuenta como enviado

- **WHEN** existe un recordatorio `pendiente` para un turno confirmado del período
- **THEN** el numerador de enviados no lo incluye

### Requirement: Los reportes respetan rol y alcance por profesional

El sistema DEBE (SHALL) permitir los reportes solo a usuarios con rol `profesional`; la recepción NO DEBE (SHALL NOT) acceder (RN-AU-02). El profesional dueño DEBE (SHALL) ver el consolidado de todos los profesionales del tenant; un profesional sin `es_dueno` DEBE (SHALL) ver únicamente sus propios datos. Toda lectura DEBE (SHALL) quedar acotada al tenant resuelto (R3).

#### Scenario: El dueño ve el consolidado

- **WHEN** el dueño consulta ocupación sin indicar profesional
- **THEN** la respuesta incluye a todos los profesionales activos del tenant

#### Scenario: El profesional sin dueño ve solo lo propio

- **WHEN** un profesional sin `es_dueno` consulta ocupación sin indicar profesional
- **THEN** la respuesta incluye únicamente su propio profesional

#### Scenario: La recepción no accede a reportes

- **WHEN** un usuario de recepción consulta un reporte
- **THEN** la respuesta es 403 con código `RN-AU-02` y no se devuelven métricas

#### Scenario: Un profesional no puede pedir otro profesional

- **WHEN** un profesional sin `es_dueno` consulta un reporte indicando el id de otro profesional
- **THEN** la respuesta es 403 con código `RN-AU-03`

### Requirement: La solicitud de exportación es asíncrona y no bloquea la API

El sistema DEBE (SHALL) aceptar la solicitud de exportación de turnos o pacientes, registrar una exportación en estado `pendiente`, encolarla en el worker y responder **202** con el identificador del job. La respuesta de la solicitud NO DEBE (SHALL NOT) incluir el contenido del CSV. Un rango inválido (fin anterior al inicio o superior al máximo permitido) DEBE (SHALL) rechazarse con 422 antes de encolar.

#### Scenario: Solicitud aceptada y encolada

- **WHEN** el dueño solicita exportar turnos de un período válido
- **THEN** la respuesta es 202 con el id del job y la exportación queda en estado `pendiente`

#### Scenario: La solicitud no devuelve el CSV

- **WHEN** se acepta una exportación
- **THEN** la respuesta no contiene filas ni el contenido del archivo

#### Scenario: Rango inválido se rechaza antes de encolar

- **WHEN** se solicita un export con `hasta` anterior a `desde`
- **THEN** la respuesta es 422 y no se crea ni se encola ninguna exportación

### Requirement: El CSV incluye metadata de tenant y timestamp en la primera línea

El CSV generado DEBE (SHALL) tener como primera línea una metadata con el `tenant_id` y el timestamp de generación (RN-RP-02), seguida de la fila de encabezados y de los datos. El archivo DEBE (SHALL) codificarse en UTF-8 con BOM para abrirse correctamente en planillas, y solo DEBE (SHALL) contener datos del tenant de la exportación.

#### Scenario: Primera línea con metadata

- **WHEN** el worker termina de generar un export
- **THEN** la primera línea del CSV contiene el `tenant_id` y el timestamp de generación

#### Scenario: Encabezados y filas después de la metadata

- **WHEN** se descarga un export de turnos con dos turnos en el rango
- **THEN** la segunda línea contiene los encabezados y hay exactamente dos filas de datos después

#### Scenario: El export no mezcla tenants

- **WHEN** existen turnos en dos tenants y el dueño de uno exporta
- **THEN** el CSV solo contiene turnos de su tenant

### Requirement: La exportación y la descarga son exclusivas del dueño

El sistema DEBE (SHALL) permitir solicitar, consultar, descargar y reintentar exportaciones solo al profesional dueño (RN-AU-02). Un profesional sin `es_dueno` o un usuario de recepción DEBEN (SHALL) recibir 403. Una exportación de otro tenant DEBE (SHALL) responder como inexistente (404 genérico).

#### Scenario: Un profesional sin dueño no puede exportar

- **WHEN** un profesional sin `es_dueno` solicita un export
- **THEN** la respuesta es 403 y no se encola ningún job

#### Scenario: Un export de otro tenant no es visible

- **WHEN** el dueño consulta el estado de una exportación de otro tenant
- **THEN** la respuesta es 404 y no se filtra su estado ni su contenido

### Requirement: La descarga exige una exportación lista

El sistema DEBE (SHALL) entregar el CSV únicamente cuando la exportación está en estado `listo`, como descarga con nombre de archivo y tipo `text/csv`. Si la exportación está `pendiente` o `procesando`, DEBE (SHALL) responder 409 con un código de dominio; si está `fallido`, DEBE (SHALL) responder 409 informando el error sin entregar archivo.

#### Scenario: Descarga de un export listo

- **WHEN** el dueño descarga una exportación en estado `listo`
- **THEN** recibe el CSV como adjunto con tipo `text/csv`

#### Scenario: Descarga antes de terminar

- **WHEN** el dueño intenta descargar una exportación `pendiente` o `procesando`
- **THEN** la respuesta es 409 y no se entrega archivo

#### Scenario: Descarga de un export fallido

- **WHEN** el dueño intenta descargar una exportación `fallido`
- **THEN** la respuesta es 409 con el mensaje de error registrado

### Requirement: Una exportación fallida puede reintentarse

El sistema DEBE (SHALL) permitir reencolar una exportación en estado `fallido`, devolviéndola a `pendiente` y respondiendo 202. Una exportación `listo` o `pendiente` NO DEBE (SHALL NOT) poder reintentarse. Si el worker falla, la exportación DEBE (SHALL) quedar en `fallido` con un mensaje, sin afectar la disponibilidad de la API.

#### Scenario: Reintento de un export fallido

- **WHEN** el dueño reintenta una exportación `fallido`
- **THEN** la respuesta es 202, la exportación vuelve a `pendiente` y se encola de nuevo

#### Scenario: No se reintenta un export listo

- **WHEN** el dueño intenta reintentar una exportación `listo`
- **THEN** la respuesta es 409 y la exportación no cambia

#### Scenario: El fallo del worker queda registrado

- **WHEN** el job de exportación lanza un error
- **THEN** la exportación queda en `fallido` con un mensaje y la API sigue respondiendo
