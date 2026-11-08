# Tasks

Esta lista es un plan, no evidencia de ejecución. **No iniciar ninguna tarea de implementación sin una nueva aprobación explícita del usuario: C-11 tiene gobernanza ALTA.** Los artefactos de esta propuesta no autorizan `apply`.

En cada grupo que modifique archivos existentes: ejecutar primero sus tests actuales y registrar la baseline; detenerse ante un fallo preexistente real. Usar Python 3.12, `uv run --frozen`, PostgreSQL y Redis aislados de la demo manual. Cada conducta sigue RED ejecutado → GREEN mínimo → TRIANGULATE con al menos dos casos → REFACTOR con tests verdes. Toda escritura de dominio pasa por el servicio de recordatorios y por `TenantSession` (R3); la generación no crea ni modifica turnos (R4). No se agregan dependencias nuevas.

## 1. Aprobación y línea base

- [x] 1.1 Recuperar la aprobación humana explícita para implementar estos artefactos y confirmar con `openspec status --change c-11-recordatorios-manuales --json` e `openspec instructions apply --change c-11-recordatorios-manuales --json` que se trabaja sobre los contextFiles actuales; dejar evidencia de la aprobación y no escribir código si falta.
- [x] 1.2 Ejecutar la baseline de `test_architecture.py`, `test_models_metadata.py`, `test_turnos_api.py`, `test_turnos_estados.py`, `test_rn_co_*` (si ya existe), `test_workers.py` (si ya existe) y la suite de frontend; registrar comando y recuento, confirmar head único `0006_turno` con `alembic heads` y detenerse ante un fallo preexistente real.
- [x] 1.3 Confirmar que `rq` y `rq-scheduler` ya están en `backend/pyproject.toml` y que `Settings.recordatorio_ventana_hs` existe sin parsear; documentar que no se agregan dependencias.

## 2. Modelo, migración y constraints (RN-CO-01, RN-CO-03)

- [x] 2.1 **RED** — Agregar `backend/tests/test_recordatorio_model.py` (integración PostgreSQL) con el modelo ausente: insertar dos recordatorios para el mismo turno debe violar unicidad; `estado='enviado'` sin `enviado_por` debe violar el CHECK; `canal` fuera del enum debe fallar; aislamiento de `tenant_id` en lectura; ejecutar y registrar el fallo por modelo ausente, no por entorno.
- [x] 2.2 **GREEN** — Crear `backend/app/db/models/recordatorio.py` con `CanalRecordatorio` y `EstadoRecordatorio` (`StrEnum`), `Recordatorio` con `TenantMixin`/`AuditMixin`, FKs `turno` (`ON DELETE CASCADE`) y `usuario` (`ON DELETE SET NULL`), `UNIQUE (tenant_id, turno_id)`, CHECK de `enviado_por` y `Index (tenant_id, estado)`; exportarlo en `backend/app/db/models/__init__.py`; verificar 2.1.
- [x] 2.3 **GREEN** — Crear `backend/alembic/versions/0007_recordatorio.py` con `down_revision = "0006_turno"`, los dos enums, la tabla, el índice y el `downgrade`; verificar con `alembic upgrade head`, `alembic check` (sin diffs de metadata) y `alembic downgrade 0006_turno && alembic upgrade head`.
- [x] 2.4 **TRIANGULATE** — Cubrir borrado en cascada del turno, `enviado_por` de otro tenant rechazado por la guarda de escritura, dos tenants con turnos homónimos y el índice `(tenant_id, estado)` usado por la cola; ejecutar y registrar los casos nuevos.
- [x] 2.5 **REFACTOR** — Alinear nombres de constraints con la convención del proyecto (`uq_`, `ck_`, `ix_`), revisar docstrings de RN-CO-01/03 y ejecutar tests del grupo más Ruff.

## 3. Configuración y plantilla del mensaje (RN-CO-02, RN-GL-03)

- [x] 3.1 **RED** — Agregar `backend/tests/test_recordatorio_plantilla.py` con el parser y la plantilla ausentes: `"24,48"` → `(24, 48)`, `"12,36"` válido, valores no numéricos, un solo valor, `min >= max`, `min <= 0` y string vacío deben fallar con error explícito; ejecutar y registrar RED.
- [x] 3.2 **GREEN** — Implementar en `backend/app/domain/recordatorios/plantilla.py` el parseo validado de `RECORDATORIO_VENTANA_HS` y la función de texto con nombre de paciente, profesional, fecha/hora en `America/Argentina/Buenos_Aires` y dirección; agregar `consultorio_direccion` opcional a `backend/app/core/settings.py` (`CONSULTORIO_DIRECCION`) y documentarla en `.env.example`; verificar 3.1.
- [x] 3.3 **TRIANGULATE** — Cubrir turno en UTC que cae en otro día local, dirección vacía (se omite la línea, sin placeholder), nombre con acentos y texto determinista ante el mismo turno; ejecutar y registrar los casos.
- [x] 3.4 **REFACTOR** — Unificar el formateo de fecha/hora con el helper de zona horaria existente, sin reloj global ni `datetime.now()` dentro de la plantilla; ejecutar tests del grupo y Ruff.

## 4. Generación programada multi-tenant (RN-CO-01, R3, R4)

- [x] 4.1 **RED** — Agregar `backend/tests/test_rn_co_01_generacion.py` (integración PostgreSQL) con el job ausente: turno confirmado a 36 h genera un `pendiente`; reservado/atendido/cancelado/ausente no genera; a 72 h no genera; segunda ejecución no duplica; turno a 10 h sin recordatorio se recupera; turno pasado no genera; ejecutar y registrar RED por función ausente.
- [x] 4.2 **GREEN** — Implementar `backend/app/domain/recordatorios/repository.py` (consulta de candidatos por ventana y catch-up con join a `turno`, sin leer fuera del tenant) y `backend/app/domain/recordatorios/service.py` con `generar(ahora)` usando `system_session()` solo para listar `tenant.id` y `tenant_session(tenant_id)` por tenant, commit independiente por tenant y captura de violación de unicidad por turno; verificar 4.1.
- [x] 4.3 **GREEN** — Implementar `generar_recordatorios(ahora=None)` en `backend/app/workers/jobs.py` como wrapper del servicio (reloj inyectable) y verificar que el job no requiere contexto HTTP ni `require_tenant()`.
- [x] 4.4 **TRIANGULATE** — Cubrir dos tenants con turnos en ventana (cada recordatorio en su tenant), un tenant con error que no revierte los demás, `RECORDATORIO_VENTANA_HS=12,36`, límite exacto inferior/superior, y turno reprogramado dentro de la ventana; ejecutar y registrar los casos.
- [x] 4.5 **REFACTOR** — Extraer el predicado de candidatos y el bucle por tenant a helpers testeables; verificar que el job solo hace `SELECT` sobre `tenant`, `turno`, `paciente`, `profesional` y `INSERT` sobre `recordatorio`, y ejecutar la guarda de arquitectura y Ruff.

## 5. Cola, marcado y RBAC (RN-CO-03, RN-AU-02, RN-AU-03)

- [x] 5.1 **RED** — Agregar `backend/tests/test_recordatorios_api.py` con las rutas ausentes: sin JWT → 401; recepción/dueño ven todos; profesional sin flag solo los propios; `pendiente` y `fallido` aparecen ordenados por inicio; `enviado` no aparece; turno cancelado no aparece; marcar `enviado` registra `enviado_por`; reenviar → error de dominio; marcar `fallido` mantiene en cola; recordatorio de otro tenant → 404; rol no autorizado → 403; ejecutar y registrar RED por ruta inexistente.
- [x] 5.2 **GREEN** — Crear `backend/app/domain/recordatorios/schemas.py` con `extra='forbid'`, `backend/app/domain/recordatorios/router.py` (`GET /recordatorios/pendientes`, `POST /{id}/enviado`, `POST /{id}/fallido`, roles recepción/profesional, `profesional_del_alcance`) y registrar el router en `backend/app/main.py`; verificar 5.1.
- [x] 5.3 **GREEN** — Implementar en el servicio el listado con join (texto re-renderizado con datos vigentes, sin N+1) y las transiciones `pendiente|fallido → enviado` (con `enviado_por`) y `pendiente|fallido → fallido`, devolviendo `RN-CO-03` con `reason` en reenvío y `RN-CO-01`/404 genérico en no encontrado/fuera de alcance; verificar los tests de 5.1.
- [x] 5.4 **TRIANGULATE** — Cubrir turno reprogramado (el texto de la cola muestra la fecha nueva), fallido→enviado en un reintento, enviado→fallido rechazado, recordatorio inexistente, recordatorio de otro profesional, y respuesta sin datos de otros tenants; ejecutar y registrar los casos.
- [x] 5.5 **REFACTOR** — Compartir la serialización de la cola, aplicar `Annotated` y `dependencies` a nivel de router, y ejecutar tests de API, arquitectura y Ruff.

## 6. Scheduler del worker (Flujo 2)

- [x] 6.1 **RED** — Agregar `backend/tests/test_worker_scheduler.py` con el cableado ausente: el arranque registra un único job `generar_recordatorios_hourly` con `job_id` fijo y reemplazo idempotente al reiniciar; ejecutar y registrar RED.
- [x] 6.2 **GREEN** — Crear `backend/app/workers/scheduler.py` (proceso propio) para agendar el cron horario con rq-scheduler usando `id` fijo; el `worker` queda como consumidor puro. Verificar 6.1 sin depender de un Redis real (doble o scheduler inyectable).
- [x] 6.3 **TRIANGULATE** — Cubrir reinicio del worker (no acumula jobs), fallo de conexión a Redis al arrancar (falla rápido, no arranca el `Worker`) y arranque limpio con la cola `default`; ejecutar y registrar los casos.

## 7. Frontend de la cola (US-010, US-011)

- [x] 7.1 **RED** — Agregar `frontend/src/features/recordatorios/Recordatorios.test.tsx` con la feature ausente: renderiza la cola con paciente, profesional, fecha/hora y badge; el botón copiar escribe el texto en el portapapeles; "Marcar enviado" llama al endpoint y saca el ítem; "Marcar fallido" lo deja con badge; un error `RN-CO-03` se muestra al usuario; ejecutar Vitest y registrar RED.
- [x] 7.2 **GREEN** — Crear `frontend/src/features/recordatorios/RecordatoriosPage.tsx` y su cliente tipado (sin `any`, R2) usando el `apiFetch` existente; agregar la ruta privada `/app/recordatorios` en `frontend/src/routes.tsx`; verificar 7.1.
- [x] 7.3 **TRIANGULATE** — Cubrir cola vacía (estado vacío explícito), lista con varios estados, fallo de red genérico y copia bloqueada por el navegador (fallback sin romper la vista); ejecutar Vitest y registrar los casos.
- [x] 7.4 **REFACTOR** — Extraer subcomponentes de tarjeta/badge, reutilizar el manejo de errores de `ApiError` y ejecutar `vitest run` completo más `tsc --noEmit`.

## 8. Verificación integral y cierre

- [x] 8.1 Ejecutar la suite backend completa (`pytest`), Ruff, `alembic check` y `openspec validate c-11-recordatorios-manuales --strict`; registrar recuentos y confirmar un único head `0007_recordatorio`.
- [x] 8.2 Ejecutar el E2E manual del flujo 2 en base aislada: sembrar un turno confirmado a 36 h, correr `generar_recordatorios`, verlo en `GET /recordatorios/pendientes`, marcarlo `enviado` y confirmar que sale de la cola; registrar evidencia (comando y respuesta).
- [x] 8.3 Verificar que `.env.example` documenta `RECORDATORIO_VENTANA_HS` (ya parseada) y `CONSULTORIO_DIRECCION`, y que `docker-compose.yml` incorpora el servicio `scheduler` (misma imagen que `api`) sin romper `docker compose config`.
- [x] 8.4 Actualizar el estado de `CHANGES.md` para C-11 (marcar `[x]` y anotar el resultado) solo después de archivar el change, y guardar la observación de cierre en Engram.
