# Design — c-12-reportes-export

## Context

Ver `proposal.md` — Why. Estado actual relevante:

- `Turno` persiste `inicio`/`fin` con `timestamptz`, `estado` y referencias a profesional/paciente/prestación; `Disponibilidad` es la plantilla semanal (horas locales, `dia_semana` 0–6) y `Bloqueo` un cierre puntual con `profesional_id` nulo = todo el consultorio.
- `core/huecos` ya resuelve capacidad y exclusiones, pero exige una prestación para armar la grilla; los reportes no deben depender de una prestación de referencia.
- `core/recordatorios` (C-11) persiste `estado` y `enviado_por`, y el worker ya corre con RQ (`worker` + `scheduler` en Compose).
- RBAC: `require_dueno` para rutas de dueño y `profesional_del_alcance` para el alcance por profesional. Recepción nunca accede a reportes ni exports (RN-AU-02).
- `Settings` ya expone `redis_url`; no hay infraestructura de archivos compartida entre `api` y `worker`.

## Goals / Non-Goals

**Goals:**
- Fórmulas de reporte deterministas, testeables con un seed conocido y consistentes con RN-RP-01/IN-03.
- Exportación asíncrona con estado consultable, descarga y reintento, sin bloquear la API.
- Trazabilidad mínima del export (tenant + timestamp en la primera línea, RN-RP-02).

**Non-Goals:**
- Gráficos, dashboards históricos, comparación entre períodos o export a Excel/PDF.
- Programación de exports recurrentes (el cron existente es solo de recordatorios).
- Limpieza/expiración automática de exports (se define como deuda post-MVP).
- Métricas de ingresos, obras sociales o liquidaciones (post-MVP).

## Decisions

### 1. Ocupación en minutos, no en cantidad de huecos

Ocupación = `minutos_ocupados / minutos_disponibles`, ambos dentro de `[desde, hasta)`:

- **Disponibles**: para cada día local del rango se suman los minutos de las franjas de `Disponibilidad` que caen dentro del rango (recortando en los bordes) y se restan los minutos de `Bloqueo` que intersectan (propios del profesional o globales del consultorio), con piso en cero.
- **Ocupados**: suma de `min(fin, hasta) - max(inicio, desde)` de los turnos con `inicio ∈ [desde, hasta)` y estado distinto de `cancelado`. `reservado`, `confirmado`, `atendido` y `ausente` ocupan (RN-TU-05).
- Si `minutos_disponibles = 0`, la ocupación es `0.0` (nunca `ZeroDivisionError`).

Se eligió minutos sobre conteo de slots porque un mismo profesional atiende prestaciones de 20, 30, 45 y 60 minutos: contar "huecos" obligaría a inventar una grilla y haría que una prestación larga ocupe un solo hueco.

*Alternativas consideradas:*
- Slots fijos de 30 minutos: métrica artificial y dependiente del paso elegido.
- Motor de huecos con prestación de referencia: agrega una dependencia arbitraria y costo de cómputo por cada combinación profesional/prestación.

Los sobreturnos cuentan como turnos, por lo que la ocupación puede superar 1.0; se informa el valor real sin recortarlo.

### 2. Ausencias e IN-03 como conteos separados

- `ausencias`: `ausente / (atendido + ausente)`, con `0.0` si el denominador es cero.
- `recordatorios` (IN-03): numerador = recordatorios en estado `enviado` cuyo turno tiene `inicio` en el rango; denominador = turnos `confirmado` con `inicio` en el rango; `0.0` si no hay confirmados. Se cuenta por el turno, no por la fecha de envío, para comparar la misma población.

### 3. Reportes: un endpoint por métrica y alcance reutilizado

Tres endpoints (`/reportes/ocupacion`, `/reportes/ausencias`, `/reportes/recordatorios`) con los mismos filtros `desde`, `hasta` y `profesional_id`. Todos usan `require_role(PROFESIONAL)` y `profesional_del_alcance(session, usuario, filtro)`: dueño → todos; profesional sin flag → el propio, y pedir otro devuelve 403 `RN-AU-03`.

La respuesta es una lista por profesional con `profesional_id`, `nombre` y las métricas; el dueño ve todos los profesionales activos (incluidos los que no tienen turnos, con ceros) para que el consolidado sea completo.

*Alternativas consideradas:*
- Un endpoint único con `?metrica=`: menos rutas pero contratos más pobres y difícil de cachear/testear.
- Calcular todo en el frontend: obliga a exponer datos crudos de turnos y duplica reglas.

### 4. Exportación persistida en la base, no en el filesystem

Se agrega la tabla `exportacion` con `contenido` (Text) donde el worker deja el CSV. Motivos: `api` y `worker` no comparten volumen en Compose, no hay que limpiar archivos huérfanos y el estado sobrevive a reinicios de Redis. Para un consultorio de 1–3 profesionales el CSV es chico; si crece, se migra a object storage (deuda post-MVP).

*Alternativas consideradas:*
- Volumen compartido + `FileResponse`: requiere cambiar Compose, permisos y limpieza.
- Guardar solo el `job_id` de RQ y leer el resultado: el TTL de RQ borra el resultado y no sirve para descargas diferidas.

Estados: `pendiente → procesando → listo | fallido`; `fallido → pendiente` solo por reintento. `listo` es terminal.

### 5. Encolado desde la API y job idempotente por estado

`POST /export/...` crea la fila `pendiente`, encola `app.workers.jobs.exportar_csv(<id>)` en la cola `default` y responde 202. Si Redis no responde, la fila queda `fallido` con el error y la API responde 503 (falla limpia, sin 500). El job abre `tenant_session(tenant_id)`, relee la fila, pasa a `procesando`, genera el CSV y guarda `contenido` + `listo`; cualquier excepción deja `fallido` + mensaje. Reintentar reutiliza la misma fila (no crea otra), lo que mantiene un historial simple y evita duplicados.

### 6. Formato del CSV (RN-RP-02)

- Primera línea: `# tenant_id=<uuid>; generado_en=<ISO-8601>; tipo=<turnos|pacientes>; desde=<...>; hasta=<...>`.
- Segunda línea: encabezados. Luego una fila por registro.
- Codificación `utf-8-sig` (BOM) para Excel; delimitador `,` y `csv.writer` para el quoting.
- `turnos.csv`: `id, inicio, fin, estado, profesional, prestacion, paciente, telefono, es_sobreturno, codigo_publico, creado_en`.
- `pacientes.csv`: `id, nombre, telefono, documento, fecha_nac, creado_en`.
- Turnos filtra por `inicio ∈ [desde, hasta)`; pacientes exporta todo el tenant (los filtros de fecha se ignoran para pacientes).
- Rango máximo: 366 días para turnos; `hasta > desde` obligatorio cuando se envían ambos.

### 7. Descarga y reintento con códigos de dominio

- `GET /export/{id}/archivo`: `listo` → `Response` con `text/csv` y `Content-Disposition: attachment; filename="turnos-<tenant>-<desde>-<hasta>.csv"`; `pendiente`/`procesando`/`fallido` → 409 `RN-RP-02` con `reason` (`no_listo` / `fallido`).
- `POST /export/{id}/reintentar`: solo `fallido` → 202 y vuelve a `pendiente`; `listo` o `pendiente` → 409 `RN-RP-02`.
- Export de otro tenant o inexistente → 404 `RN-RP-02` genérico.

### 8. Frontend con polling acotado

`features/reportes` pide los tres reportes al cambiar período/profesional, muestra tablas y la tarjeta IN-03. Para exportar, hace POST, guarda el `job_id` y consulta `GET /export/{id}` cada 2 s hasta `listo`/`fallido`, con un máximo de intentos (~60) para no pollear indefinidamente. Cuando está `listo`, muestra el enlace de descarga; si `fallido`, muestra el error y el botón de reintento.

## Risks / Trade-offs

- **[CSV grande en la columna `contenido`]** → Trade-off aceptado para 1–3 profesionales; si crece, mover a object storage (post-MVP).
- **[Ocupación > 1 por sobreturnos]** → Se informa el valor real; el frontend lo muestra tal cual (no se recorta).
- **[Bloqueos globales restados a todos]** → Es la semántica de RN-AG-02 (profesional nulo = consultorio completo); se documenta en la respuesta como capacidad neta.
- **[Reportes costosos con rangos largos]** → Rango máximo de 366 días y agregados en SQL por profesional/estado; la plantilla se recorre en memoria (≤ 366 días).
- **[Redis caído al solicitar un export]** → La fila queda `fallido` con el error y la API responde 503; el reintento funciona cuando Redis vuelve.
- **[Dos reintentos simultáneos]** → El job toma la fila y verifica el estado; el segundo reintento encuentra `pendiente` y responde 409 (o el job no vuelve a procesar si ya está `listo`).

## Migration Plan

- Migración `0008_exportacion` con `down_revision = "0007_recordatorio"`:
  - enums `tipo_exportacion` (`turnos`, `pacientes`) y `estado_exportacion` (`pendiente`, `procesando`, `listo`, `fallido`);
  - tabla `exportacion` con FKs `tenant` (RESTRICT), `usuario` (`creado_por`, SET NULL), `contenido` Text nullable, `error` Text nullable, `desde`/`hasta` timestamptz nullable, timestamps;
  - índice `(tenant_id, estado)` y `(tenant_id, creado_en)`;
  - `downgrade` elimina tabla y enums.
- Rollback: `alembic downgrade 0007_recordatorio` (tabla nueva, sin datos previos que preservar).
- Despliegue: `docker compose up` aplica la migración; el `worker` ya consume la cola `default`, no requiere cambios de Compose.
- Seed: no crea exportaciones; los tests las crean explícitamente.

## Open Questions

Ninguna que cambie specs, enfoque o desglose. La expiración/limpieza de exports y el pasaje a object storage quedan como deuda post-MVP documentada en `11`.
