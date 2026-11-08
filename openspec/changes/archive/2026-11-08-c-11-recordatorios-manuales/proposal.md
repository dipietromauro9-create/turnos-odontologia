# Proposal

## Why

Hoy la recepción confirma asistencia por WhatsApp de memoria, sin una lista de a quién avisar ni cuándo. Eso produce recordatorios olvidados, ausentismo y huecos que se pierden. El MVP ya tiene turnos confirmados con fecha/hora y datos del paciente (C-07), pero falta el paso que convierte esa agenda en una cola de trabajo diaria para recepción.

## What Changes

- **Backend — modelo `Recordatorio` y migración `0007_recordatorio`**:
  - Tabla `recordatorio` con `tenant_id`, `turno_id`, `canal` (`whatsapp_manual`), `texto`, `estado` (`pendiente` | `enviado` | `fallido`), `enviado_por` (FK `usuario`, nullable) y timestamps.
  - Un solo recordatorio por turno (`UNIQUE (tenant_id, turno_id)`): v1 tiene un único tipo (aviso previo), así que no se agrega columna `tipo`; el día que existan varios tipos la unicidad se relaja a `(tenant_id, turno_id, tipo)`.
  - CHECK de coherencia: `estado = 'enviado'` exige `enviado_por` no nulo (RN-CO-03); índice `(tenant_id, estado)` para la cola de recepción.
- **Backend — generación programada e idempotente**:
  - Job RQ `generar_recordatorios` en `app/workers/jobs.py`; rq-scheduler lo agenda cada hora con `job_id` fijo (reemplazo idempotente al reiniciar el worker).
  - Genera un `pendiente` por turno `confirmado` cuyo `inicio` cae en la ventana configurada `RECORDATORIO_VENTANA_HS` (CSV `24,48` → `[ahora+24h, ahora+48h]`, RN-CO-01) y **no** tiene recordatorio previo. Recorre todos los tenants con `system_session()` (solo tabla `tenant`) + `tenant_session(tenant_id)` (R3).
  - Recuperación tras caída del worker: además de la ventana, genera para turnos confirmados a menos de 24 h que no tengan recordatorio (catch-up), de modo que el próximo ciclo rellene lo perdido sin duplicar.
  - El texto se arma en el backend por plantilla: nombre del paciente, profesional, fecha/hora en `America/Argentina/Buenos_Aires` (RN-GL-03) y dirección del consultorio (RN-CO-02).
- **Backend — endpoints internos** (`recepcion` y `profesional`; el profesional sin `es_dueno` solo ve sus propios turnos):
  - `GET /recordatorios/pendientes`: cola ordenada por inicio del turno, con `pendiente` **y** `fallido` (RN-CO-03: lo fallido sigue visible para reintento), denormalizando nombre de paciente/profesional y datos del turno para evitar N+1.
  - `POST /recordatorios/{id}/enviado`: registra `enviado_por` y pasa a `enviado` (RN-CO-03).
  - `POST /recordatorios/{id}/fallido`: marca `fallido` y lo deja reintentable.
- **Frontend — `features/recordatorios`**:
  - Página privada `/app/recordatorios` con la cola, fecha/hora local, badge de estado, texto pre-generado con botón de copiar en un clic y acciones "Marcar enviado" / "Marcar fallido" (US-010, US-011).
  - Errores de dominio por código `RN-XX-NN` (RN-GL-01).
- **Configuración**: `RECORDATORIO_VENTANA_HS` pasa a parsearse (hoy es solo un string) y se agrega `CONSULTORIO_DIRECCION` (opcional) para la plantilla; `.env.example` documenta ambas.

## Capabilities

### New Capabilities

- `core/recordatorios`: generación programada e idempotente de recordatorios para turnos confirmados próximos, cola manual de recepción con texto pre-generado y marcado de envío/fallo con trazabilidad de quién lo envió.

### Modified Capabilities

<!-- Ninguna. La dirección del consultorio entra por configuración de despliegue (v1 = un tenant por deploy, TENANT_DEFAULT_SLUG), no cambia el contrato de core/tenancy. La generación consume core/turnos sin modificarlo. -->

## Impact

- **Base de datos**: migración `0007_recordatorio` (nueva tabla + enum `canal_recordatorio` y `estado_recordatorio`), encadenada a `0006_turno`. Sin cambios en tablas existentes.
- **API**: nuevo router `/recordatorios` (autenticado, RBAC recepción/profesional con alcance por profesional). No toca rutas públicas.
- **Workers**: `app/workers/jobs.py` gana `generar_recordatorios`; un nuevo proceso `app/workers/scheduler.py` (servicio `scheduler` en Compose) agenda el cron horario y encola los jobs vencidos. El `worker` sigue consumiendo la cola `default` con la imagen de `api`.
- **Frontend**: nueva feature `recordatorios` y ruta privada `/app/recordatorios`.
- **Configuración**: nueva variable `CONSULTORIO_DIRECCION`; `RECORDATORIO_VENTANA_HS` deja de ser string opaco.
- **Compose**: nuevo servicio `scheduler` (misma imagen que `api`).
- **Dependencias**: ninguna nueva (`rq` y `rq-scheduler` ya están declaradas en `backend/pyproject.toml`).
- **Tests**: generación idempotente, ventana y catch-up, aislamiento multi-tenant del job, RBAC/alcance de la cola, marcado de envío con `enviado_por`, reintento de `fallido`, y Vitest de la cola.
