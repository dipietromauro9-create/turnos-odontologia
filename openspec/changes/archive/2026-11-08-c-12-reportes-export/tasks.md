# Tasks

Esta lista es un plan, no evidencia de ejecución. **No iniciar ninguna tarea de implementación sin una nueva aprobación explícita del usuario: C-12 cierra el MVP y toca reportes, exports y worker.** Los artefactos de esta propuesta no autorizan `apply`.

En cada grupo que modifique archivos existentes: ejecutar primero sus tests actuales y registrar la baseline; detenerse ante un fallo preexistente real. Usar Python 3.12, `uv run --frozen`, PostgreSQL y Redis aislados de la demo manual. Cada conducta sigue RED ejecutado → GREEN mínimo → TRIANGULATE con al menos dos casos → REFACTOR con tests verdes. Toda lectura/escritura de dominio pasa por `TenantSession` (R3); los reportes son de solo lectura y no crean ni modifican turnos (R4). No se agregan dependencias nuevas.

## 1. Aprobación y línea base

- [x] 1.1 Recuperar la aprobación humana explícita para implementar estos artefactos y confirmar con `openspec status --change c-12-reportes-export --json` e `openspec instructions apply --change c-12-reportes-export --json` que se trabaja sobre los contextFiles actuales; dejar evidencia de la aprobación y no escribir código si falta.
- [x] 1.2 Ejecutar la baseline de `test_architecture.py`, `test_models_metadata.py`, `test_recordatorios_api.py`, `test_worker_scheduler.py` y la suite de frontend; registrar comando y recuento, confirmar head único `0007_recordatorio` con `alembic heads` y detenerse ante un fallo preexistente real.
- [x] 1.3 Confirmar que `rq`/`rq-scheduler` ya están declarados y que `Settings.redis_url` existe; documentar que no se agregan dependencias ni servicios de Compose (el `worker` ya consume la cola `default`).

## 2. Modelo `Exportacion` y migración `0008_exportacion` (RN-RP-02)

- [x] 2.1 **RED** — Agregar `backend/tests/test_exportacion_model.py` (integración PostgreSQL) con el modelo ausente: metadatos de frontera y FKs; `tipo`/`estado` fuera de enum rechazados; índice `(tenant_id, estado)`; aislamiento de lectura por tenant; `creado_por` nullable con `ON DELETE SET NULL`; ejecutar y registrar el fallo por modelo ausente.
- [x] 2.2 **GREEN** — Crear `backend/app/db/models/exportacion.py` con `TipoExportacion`/`EstadoExportacion` (`StrEnum`), `Exportacion` con `TenantMixin`/`AuditMixin`, `contenido`/`error`/`desde`/`hasta` nullable, FKs `tenant` y `usuario`, índices `(tenant_id, estado)` y `(tenant_id, creado_en)`; exportarlo en `backend/app/db/models/__init__.py`; verificar 2.1.
- [x] 2.3 **GREEN** — Crear `backend/alembic/versions/0008_exportacion.py` con `down_revision = "0007_recordatorio"`, enums, tabla, índices y `downgrade`; verificar con `alembic upgrade head`, `alembic check` y `alembic downgrade 0007_recordatorio && alembic upgrade head`.
- [x] 2.4 **TRIANGULATE** — Cubrir dos tenants con exports homónimos, borrado de usuario (`creado_por` → NULL), persistencia de `contenido` grande y estado por defecto `pendiente`; ejecutar y registrar los casos.
- [x] 2.5 **REFACTOR** — Alinear nombres de constraints/índices con la convención y ejecutar tests del grupo más Ruff.

## 3. Cálculo puro de métricas (RN-RP-01, IN-03)

- [x] 3.1 **RED** — Agregar `backend/tests/test_reportes_calculo.py` con el módulo puro ausente: ocupación por minutos con turnos activos, `ausente` que ocupa, `cancelado` que libera, bloqueo que reduce capacidad, sin disponibilidad → 0; ausencias con denominador cero; IN-03 con pendientes que no cuentan y sin confirmados → 0; ejecutar y registrar RED.
- [x] 3.2 **GREEN** — Implementar `backend/app/domain/reportes/calculo.py` con funciones puras (sin I/O ni reloj global): minutos disponibles por día/franja menos bloqueos, minutos ocupados recortados al rango, tasa de ausencia y ratio IN-03; verificar 3.1.
- [x] 3.3 **TRIANGULATE** — Cubrir rango de un solo día, borde semiabierto del rango, turno que empieza antes de `desde` (excluido), bloqueo parcial/global, DST en `America/Argentina/Buenos_Aires`, sobreturno que lleva la ocupación por encima de 1 y profesional sin franjas; ejecutar y registrar los casos.
- [x] 3.4 **REFACTOR** — Reutilizar los helpers de intersección de `core/huecos` donde aplique, mantener el módulo determinista y ejecutar tests del grupo más Ruff.

## 4. Reportes: repositorio, servicio y endpoints (RN-RP-01, RN-AU-02, RN-AU-03)

- [x] 4.1 **RED** — Agregar `backend/tests/test_reportes_api.py` con las rutas ausentes: dueño ve consolidado; profesional sin flag solo lo propio; pedir otro profesional → 403 `RN-AU-03`; recepción → 403 `RN-AU-02`; sin JWT → 401; rango invertido → 422; período sin datos → ceros; aislamiento por tenant; ejecutar y registrar RED.
- [x] 4.2 **GREEN** — Implementar `backend/app/domain/reportes/repository.py` (turnos agregados por profesional/estado, franjas, bloqueos y profesionales del tenant) y `backend/app/domain/reportes/service.py` con `ocupacion`, `ausencias` y `recordatorios` usando `UnitOfWork` + `profesional_del_alcance`; verificar 4.1.
- [x] 4.3 **GREEN** — Crear `backend/app/domain/reportes/schemas.py` con `extra='forbid'`, `backend/app/domain/reportes/router.py` (`GET /reportes/ocupacion|/ausencias|/recordatorios`, `require_role(PROFESIONAL)`) y registrar el router en `backend/app/main.py`; verificar los tests de 4.1.
- [x] 4.4 **TRIANGULATE** — Cubrir fechas sin zona → 422, `profesional_id` de otro tenant → 404/403, profesional inactivo con ceros, dos profesionales con datos distintos y consulta del dueño filtrando por un profesional; ejecutar y registrar los casos.
- [x] 4.5 **REFACTOR** — Compartir el parseo de filtros y la serialización de filas, aplicar `Annotated` y `dependencies` a nivel de router, y ejecutar tests de API, arquitectura y Ruff.

## 5. Exportación: creación, estado, descarga y reintento (RN-RP-02)

- [x] 5.1 **RED** — Agregar `backend/tests/test_export_api.py` con las rutas ausentes: POST turnos/pacientes → 202 con `job_id` y estado `pendiente`; rango inválido → 422 sin fila; profesional sin dueño y recepción → 403; export de otro tenant → 404; descarga `listo` → `text/csv` con adjunto; `pendiente`/`procesando`/`fallido` → 409 `RN-RP-02`; reintento de `fallido` → 202 y vuelve a `pendiente`; reintento de `listo` → 409; ejecutar y registrar RED.
- [x] 5.2 **GREEN** — Crear `backend/app/domain/exportacion/schemas.py` (`extra='forbid'`), `service.py` (crear + encolar, consultar, descargar, reintentar; `require_dueno` en router) y `router.py` con las rutas `/export/...`; registrar en `backend/app/main.py`; verificar 5.1.
- [x] 5.3 **GREEN** — Implementar el encolado con `Queue("default", connection=Redis.from_url(settings.redis_url))` y el manejo de Redis caído: la fila queda `fallido` con error y la API responde 503 sin 500; verificar con un doble de la cola.
- [x] 5.4 **TRIANGULATE** — Cubrir export de turnos con y sin rango, export de pacientes sin rango, nombre de archivo por tipo/fechas, dos exports simultáneos y reintento tras fallo simulado; ejecutar y registrar los casos.
- [x] 5.5 **REFACTOR** — Extraer el armado de respuestas y el nombre de archivo a helpers testeables; ejecutar tests de API, arquitectura y Ruff.

## 6. Job del worker y generación del CSV (RN-RP-02)

- [x] 6.1 **RED** — Agregar `backend/tests/test_export_job.py` con el job ausente: metadata con `tenant_id` + `generado_en` en la primera línea, encabezados en la segunda, filas exactas, `utf-8-sig`, solo datos del tenant, `procesando` → `listo` con contenido y error → `fallido` con mensaje; ejecutar y registrar RED.
- [x] 6.2 **GREEN** — Implementar `exportar_csv(exportacion_id)` en `backend/app/workers/jobs.py` (o módulo de exportación) con `tenant_session`, transiciones de estado y armado del CSV por tipo; verificar 6.1.
- [x] 6.3 **TRIANGULATE** — Cubrir export de turnos con rango vacío (solo metadata + encabezados), pacientes con documento/fecha nulos, nombres con comas/comillas/saltos y reejecución sobre una fila `listo` que no debe reescribirse; ejecutar y registrar los casos.
- [x] 6.4 **REFACTOR** — Unificar el writer CSV y el formateo de fechas en un helper; verificar que el job no requiere contexto HTTP ni `require_tenant()` y ejecutar Ruff.

## 7. Frontend de reportes y exportación (US-012, US-013)

- [x] 7.1 **RED** — Agregar `frontend/src/features/reportes/Reportes.test.tsx` con la feature ausente: renderiza tablas de ocupación/ausencias y la tarjeta IN-03; cambia período y vuelve a pedir; el botón exportar hace POST, muestra "procesando" y al quedar `listo` muestra el enlace de descarga; un export `fallido` muestra el error y el botón de reintento; ejecutar Vitest y registrar RED.
- [x] 7.2 **GREEN** — Crear `frontend/src/shared/api/reportesClient.ts` (tipos estrictos, sin `any`) y `frontend/src/features/reportes/ReportesPage.tsx` con selectores, tablas, polling acotado y descarga/reintento; agregar la ruta privada `/app/reportes` en `frontend/src/routes.tsx`; verificar 7.1.
- [x] 7.3 **TRIANGULATE** — Cubrir período sin datos (tablas en cero), error de red al pedir reportes, export que sigue `procesando` tras el máximo de intentos y reintento exitoso; ejecutar Vitest y registrar los casos.
- [x] 7.4 **REFACTOR** — Extraer subcomponentes de tabla/tarjeta y el polling a un helper; ejecutar `vitest run` completo más `tsc --noEmit` y `eslint`.

## 8. Verificación integral y cierre

- [x] 8.1 Ejecutar la suite backend completa (`pytest`), Ruff, `alembic check` y `openspec validate c-12-reportes-export --strict`; registrar recuentos y confirmar un único head `0008_exportacion`.
- [x] 8.2 Ejecutar el E2E manual del flujo 5 en base aislada: sembrar turnos/pacientes/recordatorios, pedir reportes, solicitar un export, correr el job, consultar estado, descargar el CSV y verificar metadata + filas; registrar evidencia (comando y salida).
- [x] 8.3 Verificar que `.env.example` y `docker-compose.yml` no requieren variables ni servicios nuevos, y que el `worker` toma el job sin cambios de despliegue.
- [x] 8.4 Actualizar el estado de `CHANGES.md` para C-12 (marcar `[x]` y anotar el resultado) solo después de archivar el change, y guardar la observación de cierre en Engram.
