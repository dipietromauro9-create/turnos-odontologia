# core/bloqueos Specification

## Purpose

Define los cierres puntuales de agenda —vacaciones, feriados, trámites o desinfección— que impiden ofrecer turnos en un intervalo, distinguiendo el cierre de un profesional del cierre de todo el consultorio, y quién puede consultarlos, crearlos y eliminarlos.

## Requirements

### Requirement: Un bloqueo cierra un intervalo del consultorio o de un profesional

El sistema DEBE (SHALL) registrar cada bloqueo con un instante de inicio y uno de fin conscientes de zona horaria, un motivo y un profesional opcional. El instante de fin DEBE (SHALL) ser estrictamente posterior al de inicio. Cuando el profesional está informado, el bloqueo afecta únicamente a ese profesional; cuando el profesional es nulo, el bloqueo afecta a todo el consultorio (RN-AG-02). Todo bloqueo DEBE (SHALL) pertenecer al tenant resuelto para la request (R3).

#### Scenario: Se crea un bloqueo de un profesional

- **WHEN** el profesional dueño crea un bloqueo con un profesional informado, un motivo y un fin posterior al inicio
- **THEN** la respuesta es exitosa y el bloqueo queda asociado a ese profesional y al tenant

#### Scenario: Se crea un bloqueo de todo el consultorio

- **WHEN** el profesional dueño crea un bloqueo sin profesional, con un motivo y un fin posterior al inicio
- **THEN** la respuesta es exitosa y el bloqueo queda registrado como cierre de todo el consultorio

#### Scenario: Un bloqueo con fin anterior o igual al inicio se rechaza

- **WHEN** se envía un bloqueo cuyo instante de fin es anterior o igual al de inicio
- **THEN** la respuesta es HTTP 422 con el código de regla de agenda y no se persiste ningún bloqueo

#### Scenario: Un bloqueo con instantes sin zona horaria se rechaza

- **WHEN** se envía un bloqueo con un inicio o un fin sin información de zona horaria
- **THEN** la respuesta es HTTP 422 y no se persiste ningún bloqueo

### Requirement: Un bloqueo con profesional nulo cierra todo el consultorio (RN-AG-02)

El sistema DEBE (SHALL) tratar un bloqueo con profesional nulo como un cierre que alcanza a todos los profesionales del consultorio. La consulta de bloqueos de cualquier profesional DEBE (SHALL) incluir los cierres de consultorio junto con los propios, y la ausencia de profesional NUNCA DEBE (SHALL) interpretarse como "sin efecto" ni como un bloqueo de un profesional arbitrario.

#### Scenario: El cierre de consultorio aparece para cualquier profesional

- **WHEN** existe un bloqueo con profesional nulo y se consultan los bloqueos de un profesional cualquiera del consultorio
- **THEN** el cierre de consultorio aparece en el resultado

#### Scenario: El cierre de consultorio no se atribuye a un profesional

- **WHEN** se inspecciona un bloqueo creado sin profesional
- **THEN** su profesional sigue siendo nulo y no se completa con un profesional por defecto

#### Scenario: Un bloqueo de un profesional no cierra a los demás

- **WHEN** existe un bloqueo asociado a un profesional y se consultan los bloqueos de otro profesional
- **THEN** el bloqueo del primero no aparece en el resultado del segundo

### Requirement: Solo el dueño crea y elimina bloqueos; la lectura respeta el rol

El sistema DEBE (SHALL) permitir crear y eliminar bloqueos únicamente al profesional dueño (`rol = profesional` y `es_dueno = true`, RN-AU-02). La recepción NUNCA DEBE (SHALL) crear ni eliminar bloqueos, y un profesional sin el flag tampoco. La lectura SÍ DEBE (SHALL) estar disponible para la recepción (todos los bloqueos del consultorio), para el profesional (sus propios bloqueos más los cierres de consultorio) y para el dueño (todos). Un profesional sin flag que intente leer los bloqueos individuales de otro profesional DEBE (SHALL) recibir HTTP 403 (RN-AU-03).

#### Scenario: La recepción no puede crear bloqueos

- **WHEN** un usuario con rol `recepcion` envía un bloqueo válido a `POST /bloqueos`
- **THEN** la respuesta es HTTP 403 con `RN-AU-02` y no se crea ningún bloqueo

#### Scenario: El profesional sin flag no puede crear bloqueos

- **WHEN** un usuario con rol `profesional` y `es_dueno = false` envía un bloqueo válido a `POST /bloqueos`
- **THEN** la respuesta es HTTP 403 y no se crea ningún bloqueo

#### Scenario: La recepción puede leer todos los bloqueos

- **WHEN** un usuario con rol `recepcion` consulta los bloqueos del consultorio
- **THEN** la respuesta es exitosa e incluye los bloqueos de todos los profesionales y los cierres de consultorio

#### Scenario: El profesional lee sus bloqueos y los cierres de consultorio

- **WHEN** un usuario con rol `profesional` y `es_dueno = false` consulta los bloqueos
- **THEN** la respuesta incluye sus propios bloqueos y los cierres de consultorio, y excluye los bloqueos individuales de otros profesionales

#### Scenario: El profesional no lee bloqueos individuales ajenos

- **WHEN** un usuario con rol `profesional` y `es_dueno = false` solicita los bloqueos de otro profesional
- **THEN** la respuesta es HTTP 403 con `RN-AU-03` y no se devuelven bloqueos individuales ajenos

#### Scenario: La recepción no puede eliminar bloqueos

- **WHEN** un usuario con rol `recepcion` envía `DELETE /bloqueos/{id}` sobre un bloqueo existente
- **THEN** la respuesta es HTTP 403 con `RN-AU-02` y el bloqueo sigue existiendo

### Requirement: Los bloqueos están aislados por tenant

El sistema DEBE (SHALL) impedir que una request de un tenant lea, cree o elimine bloqueos de otro tenant, y DEBE (SHALL) rechazar un bloqueo que referencie un profesional que no pertenece al tenant resuelto.

#### Scenario: La lectura no devuelve bloqueos de otro tenant

- **WHEN** existen bloqueos en dos tenants y se consultan los bloqueos desde el tenant A
- **THEN** la respuesta contiene únicamente bloqueos del tenant A

#### Scenario: No se puede crear un bloqueo para un profesional de otro tenant

- **WHEN** se intenta crear un bloqueo referenciando un profesional que pertenece a otro tenant
- **THEN** la operación se rechaza y no se persiste ningún bloqueo

#### Scenario: No se puede eliminar un bloqueo de otro tenant

- **WHEN** se intenta eliminar por identificador un bloqueo que pertenece a otro tenant
- **THEN** la operación no elimina nada y el bloqueo del otro tenant permanece intacto

### Requirement: Eliminar un bloqueo vuelve a habilitar el intervalo

El sistema DEBE (SHALL) eliminar el bloqueo indicado por su identificador cuando la solicitud la hace el dueño, y DEBE (SHALL) responder con éxito solo si el bloqueo existía en el tenant resuelto. Después de la eliminación, el bloqueo NO DEBE (SHALL) aparecer en las consultas y el intervalo deja de estar cerrado por ese bloqueo.

#### Scenario: El dueño elimina un bloqueo existente

- **WHEN** el profesional dueño elimina un bloqueo existente de su consultorio
- **THEN** la respuesta es exitosa y el bloqueo ya no aparece en la consulta de bloqueos

#### Scenario: Eliminar un bloqueo inexistente responde 404

- **WHEN** el dueño intenta eliminar un identificador que no existe en el tenant resuelto
- **THEN** la respuesta es HTTP 404 y no se modifica ningún bloqueo
