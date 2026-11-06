# core/huecos Specification

## Purpose
Calcula y expone los horarios reservables de un profesional para una prestación y un rango, combinando la plantilla semanal, los bloqueos y los turnos activos, sin revelar datos de pacientes.

## Requirements

### Requirement: El motor enumera huecos dentro de la disponibilidad semanal

El sistema DEBE (SHALL) generar huecos de duración igual a `duracion_min` de la prestación activa, con una grilla anclada al inicio de cada intervalo de disponibilidad. Cada hueco DEBE (SHALL) caber completo dentro de la disponibilidad, tratando franjas contiguas como un solo intervalo, y expresarse como `[inicio, fin)`. Su inicio DEBE (SHALL) ser estrictamente futuro.

#### Scenario: Hueco alineado dentro de una franja

- **WHEN** el profesional tiene disponibilidad de 09:00 a 10:00 y se consulta una prestación de 30 minutos para un día futuro
- **THEN** se ofrecen los huecos 09:00–09:30 y 09:30–10:00, ambos dentro de la franja

#### Scenario: Un hueco que no cabe completo no se ofrece

- **WHEN** la disponibilidad termina a las 10:00 y la prestación dura 30 minutos, de modo que el último inicio posible sería 09:30
- **THEN** no se ofrece ningún hueco que empiece a las 09:45 ni que termine después de las 10:00

#### Scenario: La duración de la prestación cambia la grilla

- **WHEN** se calculan huecos para la misma franja y rango con una prestación de 30 minutos y luego con una de 45 minutos
- **THEN** la cantidad, los inicios y los fines de los huecos cambian según la nueva duración

#### Scenario: Las franjas contiguas permiten un hueco que cruza el borde

- **WHEN** el profesional tiene franjas 09:00–12:00 y 12:00–15:00 y la prestación dura 30 minutos
- **THEN** la disponibilidad se trata como un único intervalo continuo y se ofrecen huecos que pueden cruzar las 12:00

#### Scenario: Un descanso entre franjas no se rellena

- **WHEN** el profesional tiene franjas 09:00–10:00 y 10:15–11:00
- **THEN** no se ofrece ningún hueco que empiece a las 10:00 ni que cubra el intervalo sin disponibilidad entre ambas franjas

#### Scenario: El inicio pasado o igual al presente se excluye

- **WHEN** el instante de consulta es 09:20 y existe una franja de 09:00 a 10:00 con prestación de 30 minutos
- **THEN** el hueco 09:00–09:30 no se ofrece y sí se ofrece el 09:30–10:00

#### Scenario: El rango de consulta es semiabierto

- **WHEN** se consulta `desde` y `hasta` y existe un hueco que empieza exactamente en `hasta`
- **THEN** ese hueco no se incluye porque el rango se interpreta como `[desde, hasta)`

### Requirement: Los bloqueos y los turnos activos excluyen huecos

El sistema DEBE (SHALL) descartar todo hueco que intersecte un bloqueo del profesional o un bloqueo de consultorio con profesional nulo (RN-AG-02). También DEBE (SHALL) descartar todo hueco que intersecte un turno cuyo estado no sea `cancelado`; reservado, confirmado, atendido y ausente ocupan su intervalo (RN-TU-01, RN-TU-05). La intersección DEBE (SHALL) evaluarse con intervalos semiabiertos, de modo que un turno o bloqueo contiguo no excluya el hueco.

#### Scenario: Un bloqueo parcial recorta la oferta

- **WHEN** existe un bloqueo personal de 09:30 a 10:00 y disponibilidad de 09:00 a 10:30 con prestación de 30 minutos
- **THEN** se omite el hueco 09:30–10:00 y se conservan los huecos 09:00–09:30 y 10:00–10:30

#### Scenario: Un bloqueo total deja la ventana sin huecos

- **WHEN** un bloqueo cubre toda la disponibilidad del profesional en el rango consultado
- **THEN** la respuesta no contiene ningún hueco para ese rango

#### Scenario: Un bloqueo de consultorio afecta a cualquier profesional

- **WHEN** existe un bloqueo con profesional nulo que intersecta la disponibilidad del profesional consultado
- **THEN** los huecos intersectados no se ofrecen aunque la plantilla semanal los permita

#### Scenario: Un bloqueo de otro profesional no afecta

- **WHEN** el único bloqueo intersectante pertenece a otro profesional del mismo tenant
- **THEN** los huecos del profesional consultado no se recortan por ese bloqueo

#### Scenario: Un turno activo ocupa su intervalo

- **WHEN** existe un turno reservado, confirmado, atendido o ausente que intersecta un hueco candidato
- **THEN** ese hueco no se ofrece

#### Scenario: Un turno cancelado libera el intervalo

- **WHEN** el único turno que intersecta un hueco candidato está en estado `cancelado`
- **THEN** el hueco sí se ofrece

#### Scenario: Un turno contiguo no excluye el hueco

- **WHEN** existe un turno de 09:00 a 09:30 y el hueco candidato es 09:30–10:00
- **THEN** el hueco se ofrece porque comparten solo el borde

### Requirement: El cálculo respeta el tenant y no expone datos de pacientes

El sistema DEBE (SHALL) leer disponibilidad, bloqueos, turnos, prestaciones y profesionales únicamente del tenant resuelto para la request (R3), sin aceptar identificadores que pertenezcan a otro tenant. La respuesta DEBE (SHALL) contener solo intervalos de huecos y referencias de agenda; NUNCA DEBE (SHALL) incluir nombre, teléfono, documento, observaciones ni cualquier otro dato de pacientes (RN-AG-04).

#### Scenario: Datos de otro tenant no se mezclan

- **WHEN** existen disponibilidad, bloqueos o turnos en dos tenants y se consulta el tenant A
- **THEN** el cálculo solo considera los registros del tenant A y no devuelve huecos condicionados por datos del tenant B

#### Scenario: Una referencia de otro tenant no se utiliza

- **WHEN** se consulta un profesional o una prestación que solo existen en otro tenant
- **THEN** la respuesta es HTTP 404 sin revelar datos de esa referencia

#### Scenario: La respuesta no contiene datos de pacientes

- **WHEN** un turno activo ocupa un intervalo y el motor devuelve los huecos restantes
- **THEN** ningún elemento de la respuesta contiene identificadores ni atributos del paciente del turno ocupante

### Requirement: El endpoint interno está autenticado y limitado por rol

El sistema DEBE (SHALL) exponer `GET /disponibilidad/huecos` con `profesional_id`, `prestacion_id`, `desde` y `hasta` obligatorios, bajo JWT de panel. Recepción y dueño DEBEN (SHALL) consultar cualquier profesional del tenant; el profesional sin flag, solo el propio, con HTTP 403 `RN-AU-03` si pide otro. La ruta NO DEBE (SHALL) ser pública ni aceptar `codigo_publico` como token.

#### Scenario: Sin login el cálculo no responde

- **WHEN** se llama a `GET /disponibilidad/huecos` sin token
- **THEN** la respuesta es HTTP 401 antes de leer datos

#### Scenario: Recepción y dueño consultan cualquier agenda

- **WHEN** recepción o dueño consulta los huecos de cualquier profesional de su tenant
- **THEN** la respuesta es exitosa y respeta las demás reglas de cálculo

#### Scenario: El profesional solo consulta su propia agenda

- **WHEN** un profesional sin flag consulta los huecos de otro profesional del mismo tenant
- **THEN** la respuesta es HTTP 403 con `RN-AU-03` y no devuelve huecos ajenos

#### Scenario: Un código público no autentica la ruta

- **WHEN** se llama a `GET /disponibilidad/huecos` sin JWT enviando un `codigo_publico` válido
- **THEN** la respuesta es HTTP 401 y no se devuelven huecos

#### Scenario: Referencias inexistentes o inactivas se rechazan

- **WHEN** el profesional o la prestación no existe en el tenant, o la prestación está inactiva
- **THEN** la consulta se rechaza con un error de dominio explícito y no se inventan huecos

### Requirement: La ruta de plantilla semanal conserva su contrato

El `GET /disponibilidad` de C-06 DEBE (SHALL) seguir listando la plantilla semanal sin cambios; el motor de huecos se publica en una subruta distinta.

#### Scenario: La plantilla semanal conserva su contrato

- **WHEN** se llama a `GET /disponibilidad` sin los parámetros del motor de huecos
- **THEN** la respuesta sigue siendo el listado de franjas semanales existente

### Requirement: La consulta se pagina por rango y cumple performance semanal

El sistema DEBE (SHALL) interpretar `desde` y `hasta` como instantes con zona horaria y como un rango semiabierto `[desde, hasta)`, rechazar un rango invertido o mayor al máximo permitido, y devolver los huecos ordenados de forma determinista por inicio y referencias de agenda. Para una semana completa DEBE (SHALL) responder en menos de 1 segundo en el entorno de referencia del proyecto.

#### Scenario: Un rango invertido o vacío se rechaza

- **WHEN** `hasta` es anterior o igual a `desde`
- **THEN** la respuesta es HTTP 422 y no se ejecuta el cálculo

#### Scenario: Un rango excesivo se rechaza

- **WHEN** el rango solicitado supera el máximo permitido para una sola consulta
- **THEN** la respuesta es HTTP 422 y se indica que debe paginarse en rangos menores

#### Scenario: La respuesta es determinista

- **WHEN** se repite la misma consulta con los mismos datos y el mismo instante de referencia
- **THEN** los huecos se devuelven en el mismo orden, sin duplicados ni faltantes

#### Scenario: Una semana se calcula en menos de un segundo

- **WHEN** se consulta una semana completa con datos representativos de un consultorio
- **THEN** el tiempo de respuesta es menor a 1 segundo
