# core/disponibilidad Specification

## Purpose

Define la plantilla semanal de atención de cada profesional: qué días y en qué franjas horarias atiende, quién puede consultarla y modificarla, y qué rangos se rechazan por inválidos o por superponerse con otro ya declarado.

## Requirements

### Requirement: La disponibilidad se declara por profesional, día de la semana y franja horaria

El sistema DEBE (SHALL) registrar cada franja de disponibilidad con el profesional al que pertenece, un día de semana entre 0 y 6 (0 = lunes, 6 = domingo) y una hora de inicio y una de fin del día. Las horas DEBEN (SHALL) interpretarse como hora local del consultorio (`America/Argentina/Buenos_Aires`, RN-GL-03), no como instantes con zona horaria. Toda franja DEBE (SHALL) pertenecer al tenant resuelto para la request (R3).

#### Scenario: Se crea una franja válida

- **WHEN** el profesional dueño envía un día de semana entre 0 y 6 y una hora de fin posterior a la hora de inicio
- **THEN** la franja se persiste asociada al profesional y al tenant, y la respuesta es exitosa

#### Scenario: Un día de semana fuera de rango se rechaza

- **WHEN** se envía un día de semana menor que 0 o mayor que 6
- **THEN** la respuesta es HTTP 422 y no se persiste ninguna franja

#### Scenario: Una franja con fin anterior o igual al inicio se rechaza

- **WHEN** se envía una franja cuya hora de fin es anterior o igual a la hora de inicio
- **THEN** la respuesta es HTTP 422 con el código de regla de agenda y no se persiste ninguna franja

### Requirement: No se admiten duplicados ni solapamientos en la disponibilidad del mismo profesional y día

El sistema DEBE (SHALL) rechazar una franja que duplique exactamente otra ya existente del mismo profesional y día, y DEBE (SHALL) rechazar también una franja que se superponga parcialmente con otra del mismo profesional y día. Dos franjas contiguas que comparten solo el instante de borde (por ejemplo, una que termina a las 13:00 y otra que empieza a las 13:00) NO DEBEN (SHALL) considerarse solapadas. El rechazo DEBE (SHALL) ser un conflicto explícito con código de regla de agenda, nunca un error genérico de servidor.

#### Scenario: Un duplicado exacto se rechaza

- **WHEN** se intenta crear una franja idéntica a otra ya existente del mismo profesional y día
- **THEN** la respuesta es HTTP 409 con el código de regla de agenda y no se inserta una segunda fila

#### Scenario: Un solapamiento parcial se rechaza

- **WHEN** se intenta crear una franja que se cruza parcialmente con otra del mismo profesional y día
- **THEN** la respuesta es HTTP 409 con el código de regla de agenda y la franja existente queda sin cambios

#### Scenario: Las franjas contiguas son válidas

- **WHEN** se crea una franja que empieza exactamente cuando termina otra del mismo profesional y día
- **THEN** la creación es exitosa porque el borde compartido no es un solapamiento

#### Scenario: El mismo rango en otro día u otro profesional es válido

- **WHEN** se crea una franja con el mismo rango horario que otra existente pero en un día distinto o para otro profesional
- **THEN** la creación es exitosa porque la unicidad y el solapamiento se evalúan por profesional y día

### Requirement: Solo el dueño crea y elimina disponibilidad; la lectura respeta el rol

El sistema DEBE (SHALL) permitir crear y eliminar franjas de disponibilidad únicamente al profesional dueño (`rol = profesional` y `es_dueno = true`, RN-AU-02). La recepción NUNCA DEBE (SHALL) crear ni eliminar disponibilidad, y un profesional sin el flag tampoco. La lectura SÍ DEBE (SHALL) estar disponible para la recepción (todas las franjas del consultorio), para el profesional (solo las propias) y para el dueño (todas). Un profesional sin flag que intente leer la disponibilidad de otro profesional DEBE (SHALL) recibir HTTP 403 (RN-AU-03).

#### Scenario: La recepción no puede crear disponibilidad

- **WHEN** un usuario con rol `recepcion` envía una franja válida a `POST /disponibilidad`
- **THEN** la respuesta es HTTP 403 con `RN-AU-02` y no se crea ninguna franja

#### Scenario: El profesional sin flag no puede crear disponibilidad

- **WHEN** un usuario con rol `profesional` y `es_dueno = false` envía una franja válida a `POST /disponibilidad`
- **THEN** la respuesta es HTTP 403 y no se crea ninguna franja

#### Scenario: La recepción puede leer toda la disponibilidad

- **WHEN** un usuario con rol `recepcion` consulta la disponibilidad del consultorio
- **THEN** la respuesta es exitosa e incluye las franjas de todos los profesionales del tenant

#### Scenario: El profesional lee solo su propia disponibilidad

- **WHEN** un usuario con rol `profesional` y `es_dueno = false` consulta la disponibilidad
- **THEN** la respuesta contiene únicamente sus propias franjas

#### Scenario: El profesional no lee la disponibilidad ajena

- **WHEN** un usuario con rol `profesional` y `es_dueno = false` solicita la disponibilidad de otro profesional
- **THEN** la respuesta es HTTP 403 con `RN-AU-03` y no se devuelven franjas ajenas

#### Scenario: La recepción no puede eliminar disponibilidad

- **WHEN** un usuario con rol `recepcion` envía `DELETE /disponibilidad/{id}` sobre una franja existente
- **THEN** la respuesta es HTTP 403 con `RN-AU-02` y la franja sigue existiendo

### Requirement: La disponibilidad está aislada por tenant

El sistema DEBE (SHALL) impedir que una request de un tenant lea, cree o elimine disponibilidad de otro tenant, y DEBE (SHALL) rechazar una franja que referencie un profesional que no pertenece al tenant resuelto.

#### Scenario: La lectura no devuelve franjas de otro tenant

- **WHEN** existen franjas en dos tenants y se consulta la disponibilidad desde el tenant A
- **THEN** la respuesta contiene únicamente franjas del tenant A

#### Scenario: No se puede crear disponibilidad para un profesional de otro tenant

- **WHEN** se intenta crear una franja referenciando un profesional que pertenece a otro tenant
- **THEN** la operación se rechaza y no se persiste ninguna franja

#### Scenario: No se puede eliminar disponibilidad de otro tenant

- **WHEN** se intenta eliminar por identificador una franja que pertenece a otro tenant
- **THEN** la operación no elimina nada y la franja del otro tenant permanece intacta

### Requirement: Eliminar una franja deja de ofrecer ese horario

El sistema DEBE (SHALL) eliminar la franja indicada por su identificador cuando la solicitud la hace el dueño, y DEBE (SHALL) responder con éxito solo si la franja existía en el tenant resuelto. Después de la eliminación, la franja NO DEBE (SHALL) aparecer en las consultas de disponibilidad.

#### Scenario: El dueño elimina una franja existente

- **WHEN** el profesional dueño elimina una franja existente de su consultorio
- **THEN** la respuesta es exitosa y la franja ya no aparece en la consulta de disponibilidad

#### Scenario: Eliminar una franja inexistente responde 404

- **WHEN** el dueño intenta eliminar un identificador que no existe en el tenant resuelto
- **THEN** la respuesta es HTTP 404 y no se modifica ninguna franja
