# Proposal

## Why

El dueño del consultorio no tiene forma de saber si la agenda se está usando bien ni de sacar sus datos del sistema. Sin métricas no puede decidir horarios, detectar ausentismo ni evaluar si los recordatorios funcionan; sin exportación queda atado al producto (lock-in). Este change cierra el MVP con las dos piezas que faltan (US-012, US-013).

## What Changes

- **Backend — reportes de gestión** (solo roles `profesional`; recepción 403 por RN-AU-02):
  - `GET /reportes/ocupacion?desde=&hasta=&profesional_id=`: por profesional, minutos ocupados / minutos disponibles en el período, con `turnos_activos` y `minutos_disponibles` como datos de soporte (RN-RP-01).
  - `GET /reportes/ausencias?desde=&hasta=&profesional_id=`: `ausente / (atendido + ausente)` por profesional (RN-RP-01).
  - `GET /reportes/recordatorios?desde=&hasta=&profesional_id=`: métrica intermedia IN-03, `recordatorios enviados / turnos confirmados`, para distinguir falla de adopción de falla de producto.
  - Alcance: el dueño ve el consolidado del tenant; un profesional sin `es_dueno` ve solo lo propio.
- **Backend — exportación CSV asíncrona** (solo dueño):
  - `POST /export/turnos.csv?desde=&hasta=` y `POST /export/pacientes.csv`: validan, crean una `Exportacion` en estado `pendiente`, encolan el job y responden **202** con `job_id`; la API nunca genera el archivo en el request.
  - `GET /export/{id}`: estado (`pendiente` | `procesando` | `listo` | `fallido`), error y URL de descarga cuando corresponde.
  - `GET /export/{id}/archivo`: descarga el CSV solo si está `listo`.
  - `POST /export/{id}/reintentar`: reencola un export `fallido` (reintento con un clic).
  - **Modelo `Exportacion` + migración `0008_exportacion`**: tipo (`turnos` | `pacientes`), rango opcional, estado, `contenido` (CSV generado), `error`, `creado_por`, timestamps.
  - Job RQ `exportar_csv`: genera el CSV con la primera línea de metadata `tenant_id` + timestamp de generación (RN-RP-02), en `utf-8-sig` para abrir bien en Excel, y actualiza la fila a `listo` o `fallido`.
- **Frontend — `features/reportes`**:
  - Página privada `/app/reportes`: selectores de período y profesional, tabla de ocupación, tabla de ausencias, tarjeta de la métrica IN-03 y panel de exportación con estado del job, polling acotado y botón de descarga/reintento.
- **Sin dependencias nuevas**: reutiliza `rq`, `rq-scheduler` y el worker existente.

## Capabilities

### New Capabilities

- `core/reportes`: métricas de ocupación, ausencia y efectividad de recordatorios por profesional y período, más exportación CSV asíncrona y descargable con trazabilidad de tenant, acotada al dueño.

### Modified Capabilities

<!-- Ninguna. Los reportes consumen core/turnos, core/recordatorios y core/disponibilidad sin cambiar sus contratos. -->

## Impact

- **Base de datos**: migración `0008_exportacion` (tabla `exportacion` + enums `tipo_exportacion` y `estado_exportacion`), encadenada a `0007_recordatorio`. Sin cambios en tablas existentes.
- **API**: nuevo router `/reportes` y `/export` (autenticados; reportes para profesional con alcance, export solo dueño).
- **Workers**: `app/workers/jobs.py` gana `exportar_csv`; el servicio `scheduler` no cambia (el export es on-demand, no programado).
- **Frontend**: nueva feature `reportes` y ruta privada `/app/reportes`.
- **Tests**: fórmulas RN-RP-01 contra un seed conocido, RBAC y alcance, metadata RN-RP-02, job listo/fallido/reintento, aislamiento por tenant y Vitest de la página.
