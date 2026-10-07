# Reglas de Negocio

Cada regla tiene un código único `RN-{DOMINIO}-{NN}` para trazabilidad (referenciadas desde `06` y testeadas según `08`).

## Dominio: Turnos (RN-TU)

- **RN-TU-01**: Un profesional no puede tener dos turnos superpuestos en estado activo (reservado, confirmado, atendido). La DB lo garantiza con `EXCLUDE`; el servicio lo valida antes para devolver error legible.
- **RN-TU-02**: `fin = inicio + duracion(prestacion)` siempre; el cliente nunca envía `fin` (se calcula en backend).
- **RN-TU-03**: El sobreturno es explícito (`es_sobreturno=true`) y solo sobre huecos libres o con motivo `urgencia`; nunca viola RN-TU-01.
- **RN-TU-04**: Máquina de estados — transiciones permitidas únicamente:
  `reservado → confirmado | cancelado` · `confirmado → atendido | cancelado | ausente` · terminales (`atendido, cancelado, ausente`) sin salida. Cualquier otra transición se rechaza con 422.
- **RN-TU-05**: Solo turnos `cancelado` liberan el hueco; `ausente` conserva el registro histórico (métrica de ausentismo).
- **RN-TU-06**: Cancelación/reprogramación del paciente con código exige el `codigo_publico` del turno; sin código, solo recepción/profesional.
- **RN-TU-07**: La reprogramación es cancelación + reserva atómica (misma transacción): si no hay hueco destino, el turno original queda intacto.

## Dominio: Agenda y disponibilidad (RN-AG)

- **RN-AG-01**: Un hueco es reservable solo si cae dentro de `Disponibilidad` del profesional, no intersecta `Bloqueo` ni turnos activos, y `inicio` es futuro.
- **RN-AG-02**: `Bloqueo` con `profesional_id` nulo cierra todo el consultorio (feriado, desinfección).
- **RN-AG-03**: Cambiar la `duracion_min` de una prestación no altera turnos ya creados (la duración queda congelada en cada turno vía `fin`).
- **RN-AG-04**: La disponibilidad pública del turnero nunca expone datos de pacientes, solo huecos libres.

## Dominio: Pacientes (RN-PA)

- **RN-PA-01**: Reserva sin cuenta: basta nombre + teléfono; el sistema crea o reutiliza el paciente (match por teléfono, con advertencia de posible duplicado).
- **RN-PA-02**: La ficha básica (observaciones) solo es visible para profesional y recepción; nunca por el turnero público.
- **RN-PA-03**: Borrado físico permitido en v1 (Q-datos:c) — deuda explícita: sin auditoría ni soft delete hasta post-MVP (ver `10`, IN/Riesgo).

## Dominio: Comunicación (RN-CO)

- **RN-CO-01**: Por cada turno `confirmado` con inicio en las próximas 24–48 h existe exactamente un `Recordatorio` pendiente (sin duplicados).
- **RN-CO-02**: El texto del recordatorio lo genera el sistema por plantilla (nombre, profesional, fecha/hora, dirección); la recepción lo envía por WhatsApp y marca `enviado`.
- **RN-CO-03**: Marcar `enviado` registra quién lo envió (`enviado_por`); `fallido` exige reintento o escalado a la recepción.

## Dominio: Autenticación y autorización (RN-AU)

- **RN-AU-01**: Panel bajo JWT (access 15 min + refresh 7 días); turnero público sin login, solo con `codigo_publico` por turno.
- **RN-AU-02**: `es_dueno` solo válido con `rol=profesional`; la recepción nunca accede a configuración, usuarios ni exports.
- **RN-AU-03**: Un profesional no ve fichas de pacientes de otro profesional salvo dueño (ver matriz en `03`).

## Dominio: Reportes y exportación (RN-RP)

- **RN-RP-01**: Ocupación = turnos activos / huecos disponibles por profesional y período; ausencias = `ausente` / (atendido + ausente).
- **RN-RP-02**: Export CSV incluye `tenant_id` y timestamp de generación en la primera línea de metadata (trazabilidad mínima ante Q-datos:c).

## Dominio: Excepciones globales

- **RN-GL-01**: Todo error de dominio devuelve código de regla (ej. `RN-TU-01`) en la respuesta, para que el frontend muestre mensajes exactos y los tests aserten por código.
- **RN-GL-02**: Ninguna operación deja estados intermedios visibles: reserva, reprogramación y transiciones son transaccionales.
- **RN-GL-03**: Zona horaria única del sistema: America/Argentina/Buenos_Aires en DB y API; el frontend convierte solo para mostrar.
