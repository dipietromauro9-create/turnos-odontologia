# Spec Delta — publico/turnero

## Purpose

Permite a los pacientes consultar la disponibilidad de un consultorio por su slug público, agendar citas sin registrar cuenta, y consultar, cancelar o reprogramar sus turnos usando un código único de gestión.

## ADDED Requirements

### Requirement: Consulta pública de catálogo y disponibilidad por slug

El sistema DEBE (SHALL) permitir consultar profesionales activos, prestaciones activas y huecos libres de un consultorio mediante su slug sin requerir autenticación JWT. La respuesta NUNCA DEBE (SHALL) exponer datos personales de pacientes (RN-AG-04).

#### Scenario: Consulta exitosa de disponibilidad por slug
- **WHEN** un paciente consulta la disponibilidad para un slug existente con profesional, prestación y rango de fechas válidos
- **THEN** el sistema responde HTTP 200 con la lista de huecos libres sin datos de pacientes

#### Scenario: Slug inexistente o inactivo devuelve 404
- **WHEN** se consulta un slug que no corresponde a ningún consultorio activo
- **THEN** el sistema responde HTTP 404 con código de error de dominio

#### Scenario: Catálogo público sin datos sensibles
- **WHEN** se solicita el catálogo de profesionales y prestaciones de un slug
- **THEN** el sistema responde con nombres, especialidades, duraciones y precios de referencia sin incluir información privada

### Requirement: Reserva pública anónima de turnos

El sistema DEBE (SHALL) permitir agendar un turno indicando nombre, teléfono, profesional, prestación e inicio. DEBE (SHALL) crear o reutilizar el paciente (RN-PA-01), calcular fin en backend (RN-TU-02), validar anti-solape (RN-TU-01) y emitir un código público seguro en estado reservado.

#### Scenario: Reserva exitosa crea turno y devuelve código
- **WHEN** se envía una solicitud de reserva con hueco libre y datos de contacto válidos
- **THEN** el sistema crea el turno en estado reservado, genera el código público alfanumérico y responde HTTP 201

#### Scenario: Reutilización de paciente por teléfono
- **WHEN** el teléfono ingresado ya existe en el consultorio
- **THEN** el turno se asocia al paciente existente y advierte posible homónimo si el nombre difiere

#### Scenario: Horario ocupado devuelve conflicto legible
- **WHEN** se intenta reservar un hueco que ya fue tomado por otro turno o bloqueo
- **THEN** el sistema responde HTTP 409 con el código RN-TU-01 sin crear el turno

### Requirement: Autogestión de turnos con código público

El sistema DEBE (SHALL) permitir consultar, cancelar y reprogramar un turno mediante su código público (RN-TU-06). Si el código no existe o es inválido, DEBE (SHALL) responder HTTP 404 genérico sin enumerar turnos. La cancelación libera el hueco (RN-TU-05) y la reprogramación es atómica (RN-TU-07).

#### Scenario: Consulta de turno propio por código
- **WHEN** un paciente solicita ver su turno ingresando su código público válido
- **THEN** el sistema responde HTTP 200 con la fecha, hora, profesional, prestación y estado del turno

#### Scenario: Código público inexistente devuelve 404 genérico
- **WHEN** se consulta, cancela o reprograma con un código público inválido o inexistente
- **THEN** el sistema responde HTTP 404 sin revelar si el turno existe

#### Scenario: Cancelación con código libera el hueco
- **WHEN** un paciente envía la cancelación de su turno con código válido y motivo opcional
- **THEN** el turno pasa a estado cancelado, se guarda el motivo y el horario queda liberado para nuevas reservas

#### Scenario: Reprogramación atómica exitosa
- **WHEN** un paciente solicita reprogramar su turno a un nuevo hueco válido
- **THEN** el turno actualiza su inicio y fin conservando su estado y código público

#### Scenario: Reprogramación fallida mantiene intacto el turno
- **WHEN** el nuevo horario elegido para reprogramar no se encuentra disponible
- **THEN** el sistema rechaza la solicitud con HTTP 409 y el turno original permanece sin modificaciones

### Requirement: Rate limiting en endpoints públicos

El sistema DEBE (SHALL) limitar la tasa de peticiones en los endpoints públicos por dirección IP de origen para prevenir abusos, denegación de servicio y raspado de disponibilidad.

#### Scenario: Peticiones dentro del umbral permitido
- **WHEN** un cliente realiza peticiones públicas respetando el límite de 10 peticiones por minuto
- **THEN** el sistema procesa cada solicitud normalmente

#### Scenario: Exceso de peticiones responde 429
- **WHEN** una dirección IP supera el límite establecido de peticiones por minuto
- **THEN** el sistema responde HTTP 429 Too Many Requests indicando que se debe esperar

### Requirement: Interfaz web de turnero público y autogestión

La aplicación web DEBE (SHALL) ofrecer una interfaz accesible sin autenticación para explorar huecos por semana, filtrar por profesional o prestación, reservar con nombre y teléfono, y autogestionar turnos por código.

#### Scenario: Navegación y selección de huecos
- **WHEN** un paciente navega por las fechas en el turnero de un consultorio
- **THEN** la interfaz muestra los huecos disponibles agrupados por día y permite seleccionarlos

#### Scenario: Confirmación de reserva y copia de código
- **WHEN** el paciente confirma el formulario de reserva
- **THEN** la interfaz muestra la pantalla de confirmación con el código público destacado y opción de copiarlo

#### Scenario: Autogestión en vista de mis turnos
- **WHEN** el paciente ingresa su código en la página de mis turnos
- **THEN** la interfaz presenta los datos del turno y los controles para cancelar o elegir nuevo horario
