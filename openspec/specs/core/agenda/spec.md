# Agenda Specification

## Purpose

Da a recepción y al dueño una vista consolidada de la agenda día/semana y al profesional su propia agenda, con los datos mínimos para operar turnos desde el panel sin exponer fichas clínicas.

## Requirements

### Requirement: La agenda se agrega por día y por semana en una sola respuesta

El sistema DEBE (SHALL) exponer `GET /agenda/dia` y `GET /agenda/semana` bajo JWT de panel. `dia` DEBE aceptar `fecha` en formato `YYYY-MM-DD`; `semana` DEBE aceptar `desde` como el lunes de la semana. Ambos DEBEN (SHALL) devolver en una sola respuesta el rango resuelto, los profesionales visibles, las prestaciones activas y los turnos del rango con los nombres necesarios para la vista, junto con los bloqueos que intersectan el rango (incluidos los de profesional nulo, que alcanzan a todos). El rango DEBE (SHALL) ser semiabierto `[inicio, fin)` y calcularse en la zona horaria del consultorio (RN-GL-03): el día cubre 24 horas y la semana cubre lunes a domingo, un máximo de 7 días. Un rango inválido o mayor al máximo DEBE (SHALL) responder HTTP 422.

#### Scenario: Vista diaria con turnos

- **WHEN** recepción consulta `GET /agenda/dia` para una fecha con turnos
- **THEN** la respuesta incluye los turnos cuyo inicio cae en ese día, con profesional, paciente y prestación identificados por id y nombre

#### Scenario: La semana empieza el lunes y es semiabierta

- **WHEN** se consulta `GET /agenda/semana` con `desde` un lunes
- **THEN** la respuesta cubre desde ese lunes 00:00 hasta el lunes siguiente 00:00 exclusivo, en la zona horaria del consultorio

#### Scenario: Rango inválido

- **WHEN** se envía una fecha mal formada o un rango mayor a 7 días
- **THEN** la respuesta es HTTP 422 con el sobre de error de dominio

#### Scenario: Los bloqueos del rango se informan

- **WHEN** existe un bloqueo del profesional o un bloqueo global que intersecta el rango
- **THEN** ambos aparecen en la respuesta para que la vista pueda marcarlos

#### Scenario: Aislamiento por tenant

- **WHEN** se consulta la agenda del tenant resuelto
- **THEN** la respuesta nunca incluye turnos, profesionales, prestaciones ni bloqueos de otro tenant

### Requirement: El alcance de la agenda respeta RN-AU-03

El sistema DEBE (SHALL) aplicar el alcance de agenda del usuario autenticado: recepción y dueño DEBEN (SHALL) ver todas las agendas del tenant; el profesional con `rol = profesional` y `es_dueno = false` DEBE (SHALL) ver únicamente su propia agenda. Para ese profesional, el pedido explícito de otro `profesional_id` DEBE (SHALL) responder HTTP 403 con `RN-AU-03`, y la lista de profesionales y turnos DEBE (SHALL) quedar acotada a su propio profesional. Sin token, la respuesta DEBE (SHALL) ser HTTP 401.

#### Scenario: Recepción ve todas las agendas

- **WHEN** un usuario con `rol = recepcion` consulta la semana sin filtro
- **THEN** la respuesta incluye los turnos de todos los profesionales activos del tenant

#### Scenario: El dueño ve todas las agendas

- **WHEN** un usuario con `rol = profesional` y `es_dueno = true` consulta la agenda
- **THEN** la respuesta incluye todas las agendas del tenant, como la recepción

#### Scenario: El profesional sin flag solo ve la propia

- **WHEN** un usuario con `rol = profesional` y `es_dueno = false` consulta la agenda sin filtro
- **THEN** la respuesta contiene únicamente los turnos de su profesional vinculado y una sola columna de profesional

#### Scenario: Pedir otra agenda devuelve RN-AU-03

- **WHEN** el profesional sin flag envía el `profesional_id` de otro profesional del tenant
- **THEN** la respuesta es HTTP 403 con código `RN-AU-03` y no se devuelven datos de esa agenda

#### Scenario: Sin autenticación

- **WHEN** se llama a `/agenda/dia` o `/agenda/semana` sin token
- **THEN** la respuesta es HTTP 401 antes de evaluar permisos

### Requirement: La vista recibe datos mínimos y nunca la ficha clínica

La agregación DEBE (SHALL) incluir para cada turno su id, inicio, fin, estado, indicador de sobreturno, motivo de sobreturno, motivo de cancelación, `profesional_id` y los nombres del paciente y de la prestación. NUNCA DEBE (SHALL) incluir documento, teléfono, fecha de nacimiento, observaciones ni cualquier otro dato clínico del paciente. Los profesionales se identifican por id, nombre, especialidad y estado activo; las prestaciones, por id, nombre y duración.

#### Scenario: Los nombres alcanzan para operar la vista

- **WHEN** la agenda devuelve un turno
- **THEN** el cliente puede mostrar hora, paciente, profesional, prestación y estado sin pedidos adicionales de detalle

#### Scenario: Sin datos clínicos en el payload

- **WHEN** se inspecciona la respuesta de la agenda
- **THEN** no aparecen documento, teléfono, fecha de nacimiento ni observaciones del paciente

### Requirement: La interfaz de agenda ofrece vistas de día y semana

La aplicación web DEBE (SHALL) ofrecer una vista de día y una de semana con navegación entre períodos, columnas por profesional y tarjetas de turno que muestran la hora, el paciente, la prestación y el estado con color y etiqueta textual visible. El sobreturno DEBE (SHALL) mostrarse con etiqueta explícita, nunca solo por color. La vista DEBE (SHALL) cubrir los estados de carga, vacío, error y con datos, y los errores de dominio DEBEN (SHALL) mostrar su código `RN-XX-NN`. El profesional sin flag NUNCA DEBE (SHALL) ver el selector de otros profesionales.

#### Scenario: Vista semanal con datos

- **WHEN** recepción abre la agenda semanal con turnos
- **THEN** ve una columna por profesional y las tarjetas con hora, paciente, prestación, etiqueta de estado y, si corresponde, la etiqueta "Sobreturno"

#### Scenario: Estado vacío

- **WHEN** el rango consultado no tiene turnos
- **THEN** la vista muestra un mensaje de agenda vacía y no una grilla sin explicación

#### Scenario: Error de dominio

- **WHEN** el backend rechaza la consulta con un código de regla
- **THEN** la vista muestra el mensaje y el código `RN-XX-NN`

#### Scenario: El profesional sin flag no elige otro profesional

- **WHEN** un usuario con `rol = profesional` y `es_dueno = false` abre la agenda
- **THEN** el selector de profesional no está disponible y la vista muestra solo su agenda

### Requirement: El panel permite crear turnos y sobreturnos con las reglas existentes

Desde la agenda, recepción y dueño DEBEN (SHALL) poder crear un turno normal y un sobreturno; el profesional sin flag DEBE (SHALL) poder crear únicamente en su propia agenda y para pacientes bajo su alcance vigente. El alta DEBE (SHALL) usar el alta de turnos existente: el cliente nunca calcula `fin` (RN-TU-02) y el sobreturno exige indicador explícito y motivo de urgencia no vacío. Los rechazos por anti-solape, disponibilidad o alcance DEBEN (SHALL) mostrarse con su código `RN-XX-NN` sin dejar el turno creado.

#### Scenario: Alta normal en un hueco válido

- **WHEN** recepción completa profesional, paciente, prestación e inicio de un hueco libre
- **THEN** el turno queda creado en estado `reservado` y la agenda lo muestra al refrescar

#### Scenario: Sobreturno sin motivo

- **WHEN** se intenta crear un sobreturno sin motivo de urgencia
- **THEN** la operación se rechaza y la agenda no muestra un turno nuevo

#### Scenario: Anti-solape

- **WHEN** el inicio elegido se superpone con otro turno activo del profesional
- **THEN** la vista muestra el error `RN-TU-01` y no se crea el turno

### Requirement: Las transiciones se operan desde la agenda con RN-TU-04

La agenda DEBE (SHALL) ofrecer solo las acciones válidas para cada estado: `reservado` → confirmar o cancelar; `confirmado` → atender, registrar ausencia o cancelar; los estados `atendido`, `ausente` y `cancelado` NO DEBEN (SHALL) ofrecer acciones. Cada acción DEBE (SHALL) usar el endpoint de transición existente y, si el backend responde 422 `RN-TU-04` porque otro usuario cambió el estado, la vista DEBE (SHALL) mostrar el código y refrescar la agenda en lugar de mantener el cambio optimista.

#### Scenario: Un turno reservado ofrece confirmar y cancelar

- **WHEN** la tarjeta muestra un turno `reservado`
- **THEN** solo se ofrecen las acciones confirmar y cancelar

#### Scenario: Un estado terminal no ofrece acciones

- **WHEN** la tarjeta muestra un turno `atendido`, `ausente` o `cancelado`
- **THEN** no se ofrece ninguna acción de transición

#### Scenario: Transición inválida por cambio concurrente

- **WHEN** el usuario intenta confirmar un turno que otro usuario ya canceló
- **THEN** la vista muestra `RN-TU-04` y recarga el estado real del turno

### Requirement: El dueño gestiona disponibilidad y bloqueos desde el panel

La interfaz DEBE (SHALL) permitir al dueño listar, crear y eliminar franjas de disponibilidad y bloqueos, incluyendo bloqueos globales sin profesional. Recepción y profesional sin flag NUNCA DEBEN (SHALL) ver esos controles, y el backend DEBE (SHALL) seguir respondiendo HTTP 403 si los invocan directamente. Un bloqueo global DEBE (SHALL) verse en las agendas de todos los profesionales.

#### Scenario: El dueño crea una franja

- **WHEN** el dueño agrega una franja de disponibilidad para un profesional y día
- **THEN** la franja queda visible en la configuración de agenda y el backend la persiste

#### Scenario: La recepción no ve la configuración

- **WHEN** un usuario con `rol = recepcion` abre la agenda
- **THEN** los controles de disponibilidad y bloqueos no están disponibles

#### Scenario: Bloqueo global visible para todos

- **WHEN** el dueño crea un bloqueo sin profesional
- **THEN** el bloqueo aparece en la agenda de todos los profesionales del consultorio
