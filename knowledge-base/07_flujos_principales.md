# Flujos Principales

Cada flujo se documenta extremo a extremo, mostrando interacciones entre componentes.

## Flujo 1: Reserva pública online
**Disparador**: paciente abre `/turnero/:slug`
**Actor**: paciente (sin cuenta)

**Pasos**:
1. Frontend pide `GET /disponibilidad?desde=&hasta=` → API calcula huecos (disponibilidad − bloqueos − turnos activos).
2. Paciente elige hueco y completa nombre + teléfono → `POST /turnero/:slug/reservas`.
3. API (transacción): busca/crea paciente por teléfono, crea turno en `reservado` con `fin` calculado y `codigo_publico`.
4. API devuelve código de gestión; frontend lo muestra + sugiere guardarlo.

**Diagrama de secuencia**:
```
Paciente → Frontend → API → DB
  ver huecos:  GET /disponibilidad → calcula (RN-AG-01)
  reservar:    POST /reservas → BEGIN → paciente + turno → COMMIT
                          ← 201 + codigo_publico
```

**Casos de error**:
- Hueco ocupado entre consulta y reserva → 409 `RN-TU-01` ("ese horario se acaba de ocupar, elegí otro").
- Teléfono con paciente homónimo distinto → 201 + advertencia de posible duplicado (RN-PA-01), la recepción valida.

## Flujo 2: Generación y envío de recordatorios (WA manual)
**Disparador**: job programado (rq-scheduler, cada hora) + acción de recepción
**Actor**: sistema (genera) → recepción (envía)

**Pasos**:
1. Scheduler encola `generar_recordatorios` → worker crea un `Recordatorio` pendiente por turno confirmado en ventana 24–48 h (idempotente: RN-CO-01).
2. Recepción abre cola (`GET /recordatorios/pendientes`), copia el texto generado.
3. Envía por WhatsApp desde el celular del consultorio y marca `enviado` (o `fallido`).
4. Si el paciente confirma por WA, la recepción transiciona el turno a `confirmado` (si estaba `reservado`).

**Diagrama de secuencia**:
```
Scheduler → Worker RQ → DB (crea pendientes, sin duplicados)
Recepción → Panel → API → DB (marca enviado + enviado_por)
```

**Casos de error**:
- Worker caído → la cola se vacía visualmente pero los turnos siguen; al recuperarse, el job regenera (idempotencia por RN-CO-01).
- `fallido` → el pendiente sigue visible hasta reintento exitoso (RN-CO-03).

## Flujo 3: Reprogramación atómica por el paciente
**Disparador**: paciente con código usa "reprogramar"
**Actor**: paciente

**Pasos**:
1. Frontend valida código (`GET /turnero/mis-turnos?codigo=`) y muestra disponibilidad.
2. `POST /turnero/mis-turnos/reprogramar` {codigo, nuevo_inicio} → API en transacción: bloquea fila del turno, valida hueco destino, actualiza `inicio/fin`, mantiene `estado`.
3. Responde nuevo horario; el código sigue siendo el mismo.

**Diagrama de secuencia**:
```
Paciente → Frontend → API → DB
  BEGIN → SELECT turno FOR UPDATE → valida destino (RN-AG-01, RN-TU-01)
  → UPDATE inicio/fin → COMMIT ← 200
```

**Casos de error**:
- Sin hueco destino → 409 `RN-TU-01`, turno original intacto (RN-TU-07).
- Código inválido → 404 sin distinguir si el turno existe (no enumerar).

## Flujo 4: Sobreturno de urgencia en recepción
**Disparador**: paciente presencial con urgencia
**Actor**: recepción

**Pasos**:
1. Recepción crea turno con flag `es_sobreturno=true` + motivo.
2. API valida: hueco libre (aunque fuera de disponibilidad estándar) y anti-solape (RN-TU-03 no excepciona RN-TU-01).
3. Turno nace en `confirmado` (paciente presente).

**Casos de error**:
- Solape real → 409 `RN-TU-01`; se ofrece el siguiente hueco libre sugerido.

## Flujo 5: Export CSV en background
**Disparador**: dueño pide exportación
**Actor**: profesional dueño

**Pasos**:
1. `POST /export/turnos.csv?desde=&hasta=` → API encola job y devuelve `job_id` (202 Accepted).
2. Worker genera el CSV con metadata (RN-RP-02) y lo deja descargable.
3. Frontend consulta estado y descarga.

**Casos de error**:
- Job fallido → estado `failed` con mensaje; reintento con un clic. Nunca bloquea la API.
