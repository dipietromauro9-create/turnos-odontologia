# Funcionalidades

Organizadas por **épica** y luego por **historia de usuario** (formato US-NNN). MVP v1.0 = P2:a.

## Épica 1: Turnero público

### US-001 — Ver disponibilidad pública
**Como** paciente
**Quiero** ver los huecos libres por profesional y semana desde un link
**Para** elegir cuándo atenderme sin llamar

**Criterios de aceptación**:
- [ ] Muestra solo huecos reservables (RN-AG-01) y ningún dato de pacientes (RN-AG-04)
- [ ] Permite navegar por semana y filtrar por profesional/prestación
- [ ] Responde en < 1 s para una semana (paginado por rango)

**Reglas relacionadas**: RN-AG-01, RN-AG-04

### US-002 — Reservar turno sin cuenta
**Como** paciente
**Quiero** reservar con nombre + teléfono
**Para** asegurar mi horario en el momento

**Criterios de aceptación**:
- [ ] Crea o reutiliza paciente por teléfono con advertencia de duplicado (RN-PA-01)
- [ ] Calcula `fin` en backend, nunca lo pide (RN-TU-02)
- [ ] Devuelve código de gestión del turno (`codigo_publico`)
- [ ] Rechaza huecos ocupados con error `RN-TU-01` legible

**Reglas relacionadas**: RN-TU-01, RN-TU-02, RN-PA-01, RN-GL-01, RN-GL-02

### US-003 — Cancelar con código
**Como** paciente
**Quiero** cancelar mi turno con el código recibido
**Para** liberar el horario si no puedo ir

**Criterios de aceptación**:
- [ ] Exige `codigo_publico` válido (RN-TU-06)
- [ ] El hueco vuelve a ofrecerse como disponible (RN-TU-05)
- [ ] Pide motivo (opcional) y lo guarda en `motivo_cancelacion`

**Reglas relacionadas**: RN-TU-04, RN-TU-05, RN-TU-06

### US-004 — Reprogramar con código
**Como** paciente
**Quiero** mover mi turno a otro horario
**Para** no perder la reserva si surge un imprevisto

**Criterios de aceptación**:
- [ ] Operación atómica: sin hueco destino, el turno original queda intacto (RN-TU-07)
- [ ] Revalida disponibilidad y anti-solape en el nuevo horario

**Reglas relacionadas**: RN-TU-01, RN-TU-04, RN-TU-07, RN-GL-02

## Épica 2: Agenda del consultorio

### US-005 — Agenda día/semana multi-profesional
**Como** recepción
**Quiero** ver la agenda del día y la semana por profesional
**Para** gestionar todos los turnos de un vistazo

**Criterios de aceptación**:
- [ ] Vista día y semana, con estados diferenciados por color
- [ ] Filtra por profesional; respeta RBAC (profesional ve la propia) (RN-AU-03)

**Reglas relacionadas**: RN-AU-02, RN-AU-03

### US-006 — Cargar turno interno y sobreturno
**Como** recepción
**Quiero** cargar turnos y sobreturnos de urgencia
**Para** atender demanda telefónica/presencial

**Criterios de aceptación**:
- [ ] El sobreturno exige flag explícito + motivo urgencia (RN-TU-03)
- [ ] Nunca permite solape (RN-TU-01), ni siquiera como sobreturno

**Reglas relacionadas**: RN-TU-01, RN-TU-03

### US-007 — Transicionar estados del turno
**Como** recepción o profesional
**Quiero** confirmar, registrar atención, ausencia o cancelación
**Para** mantener la agenda fiel a la realidad

**Criterios de aceptación**:
- [ ] Solo transiciones permitidas por la máquina (RN-TU-04); otra = 422 con código de regla
- [ ] `ausente` conserva historial para métricas (RN-TU-05)

**Reglas relacionadas**: RN-TU-04, RN-TU-05, RN-GL-01

### US-008 — Gestionar bloqueos y disponibilidad
**Como** profesional dueño
**Quiero** definir horarios semanales y bloqueos puntuales
**Para** que el turnero ofrezca solo lo real

**Criterios de aceptación**:
- [ ] Bloqueo con profesional nulo cierra todo el consultorio (RN-AG-02)
- [ ] Cambiar duración de prestación no altera turnos existentes (RN-AG-03)

**Reglas relacionadas**: RN-AG-02, RN-AG-03, RN-AU-02

## Épica 3: Pacientes

### US-009 — Ficha básica del paciente
**Como** profesional
**Quiero** ver y editar datos, motivo y observaciones del paciente
**Para** atender con contexto

**Criterios de aceptación**:
- [ ] Ficha visible solo para profesional/recepción, jamás pública (RN-PA-02)
- [ ] Búsqueda por nombre (trigram) y teléfono

**Reglas relacionadas**: RN-PA-01, RN-PA-02, RN-AU-03

## Épica 4: Recordatorios manuales

### US-010 — Cola de recordatorios pendientes
**Como** recepción
**Quiero** ver qué recordatorios toca enviar hoy
**Para** confirmar asistencia por WhatsApp

**Criterios de aceptación**:
- [ ] Un pendiente por turno confirmado próximo, sin duplicados (RN-CO-01)
- [ ] Texto pre-generado por plantilla, copiable en un clic (RN-CO-02)

**Reglas relacionadas**: RN-CO-01, RN-CO-02

### US-011 — Marcar envío de recordatorio
**Como** recepción
**Quiero** marcar cada recordatorio como enviado o fallido
**Para** saber qué está confirmado y qué hay que reintentar

**Criterios de aceptación**:
- [ ] Registra quién lo envió (RN-CO-03)
- [ ] `fallido` mantiene el pendiente visible para reintento

**Reglas relacionadas**: RN-CO-03

## Épica 5: Gestión y reportes

### US-012 — Reportes de ocupación y ausencias
**Como** profesional dueño
**Quiero** ver ocupación y ausentismo por profesional y período
**Para** decidir horarios y detectar problemas

**Criterios de aceptación**:
- [ ] Fórmulas según RN-RP-01, con rango de fechas seleccionable
- [ ] Solo dueño ve el consolidado; profesional ve lo propio

**Reglas relacionadas**: RN-RP-01, RN-AU-02

### US-013 — Exportación CSV
**Como** profesional dueño
**Quiero** exportar turnos y pacientes a CSV
**Para** respaldo y análisis propio (anti-lock-in)

**Criterios de aceptación**:
- [ ] Generación en background (worker RQ) con descarga cuando termina
- [ ] Incluye metadata de tenant y timestamp (RN-RP-02)
- [ ] Solo rol dueño (matriz `03`)

**Reglas relacionadas**: RN-RP-02, RN-AU-02
