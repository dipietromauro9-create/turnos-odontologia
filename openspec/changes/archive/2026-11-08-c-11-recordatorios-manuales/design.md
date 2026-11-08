# Design — c-11-recordatorios-manuales

## Context

Ver `proposal.md` — Why. El estado actual relevante:

- `Turno` ya persiste `estado`, `inicio`/`fin` con `timestamptz` y `tenant_id` (migración `0006_turno`).
- El acceso a datos pasa por `TenantSession`/`UnitOfWork`, que filtran y validan `tenant_id` automáticamente (R3). La única lectura sin scope es `system_session()`, limitada por evento a la tabla `tenant`.
- `app/workers/main.py` ya conecta a Redis y levanta un `Worker` de RQ, pero no agenda nada; `app/workers/jobs.py` solo tiene el stub `ping_job`.
- `Settings.recordatorio_ventana_hs` existe como string sin parsear (`24,48`); no hay dirección de consultorio en el modelo ni en la configuración.
- El frontend tiene `features/turnero` y rutas públicas; la rama privada `/app` todavía es un placeholder (C-10).

## Goals / Non-Goals

**Goals:**
- Modelo `Recordatorio` con unicidad por turno respaldada por la base.
- Generación horaria idempotente y multi-tenant ejecutable sin contexto HTTP.
- Cola de recepción con datos denormalizados, alcance por rol/profesional y texto vigente.
- Transiciones de estado explícitas y auditables (`enviado_por`).

**Non-Goals:**
- Envío automático por WhatsApp (API oficial) — v1 es copiar/pegar manual.
- Recordatorios de otro tipo (confirmación inmediata, recall, segunda dosis) — el modelo deja la puerta abierta pero no la implementa.
- Notificaciones push, email o SMS.
- Reprogramación automática o lista de espera.

## Decisions

### 1. Una fila por turno, sin columna `tipo`

`recordatorio` lleva `UNIQUE (tenant_id, turno_id)` (no un índice parcial sobre `pendiente`). v1 tiene un único tipo de aviso; la unicidad incondicional es la defensa más fuerte contra duplicados y hace que la idempotencia no dependa del estado. Si en post-MVP aparecen varios tipos, se agrega `tipo` y la unicidad pasa a `(tenant_id, turno_id, tipo)`.

*Alternativas consideradas:*
- Índice único parcial `WHERE estado = 'pendiente'`: permitiría crear un segundo pendiente cuando el anterior quedó `fallido`, generando spam y perdiendo el historial de reintentos.
- Unicidad solo en el servicio: una carrera entre dos ejecuciones del scheduler (o worker duplicado) insertaría duplicados.

### 2. Ventana configurable + catch-up acotado

El parseo de `RECORDATORIO_VENTANA_HS` (`"24,48"`) devuelve `(min_hs, max_hs)` validando dos enteros, `0 < min < max`. La generación tiene dos pasadas en la misma transacción por tenant:

1. **Ventana**: turnos `confirmado` con `inicio ∈ [ahora+min_hs, ahora+max_hs]` sin recordatorio.
2. **Catch-up**: turnos `confirmado` con `inicio ∈ (ahora, ahora+min_hs)` sin recordatorio, para recuperar lo que el worker no procesó mientras estuvo caído (Flujo 2, caso "worker caído").

Nunca genera para `inicio <= ahora` ni para estados distintos de `confirmado`. La segunda pasada es un superset intencional de RN-CO-01: no viola "existe exactamente uno en 24–48 h", y evita perder el aviso cuando el worker vuelve tarde.

*Alternativas consideradas:*
- Solo ventana estricta: una caída de más de 24 h deja turnos próximos sin aviso para siempre.
- Generar para todo turno confirmado futuro: crea avisos de turnos a semanas vista, fuera del propósito de la cola diaria.

### 3. Job sin contexto HTTP: `system_session()` para tenants + `tenant_session()` por tenant

`generar_recordatorios` no corre dentro de una request, así que no hay `ContextVar` de tenant. El job:

1. Lee la lista de `tenant.id` con `system_session()` (permitido: solo tabla `tenant`).
2. Por cada tenant abre `tenant_session(tenant_id)`, que aplica el filtro automático y la guarda de escritura de `TenantSession`.

No se usa `UnitOfWork` (requiere `require_tenant()`); se usa la sesión tenant directa con commit por tenant, de modo que el fallo de un tenant no revierte los demás. Los repositorios siguen siendo los mismos (`BaseRepository` exige `TenantSession`).

### 4. Scheduler idempotente con `job_id` fijo

`app/workers/scheduler.py` registra el cron horario con `Scheduler(queue_name="default", connection=...)` usando `id="generar_recordatorios_hourly"`; rq-scheduler guarda el job por `id`, así que reiniciar el scheduler lo reemplaza en lugar de acumular. Corre como **proceso propio** (servicio `scheduler` en Compose) porque `rq-scheduler` instala manejadores de señales y solo funciona en el hilo principal: un hilo dentro del worker lanza `ValueError: signal only works in main thread`. El servicio `worker` queda como consumidor puro de la cola `default`.

### 5. Texto: snapshot persistido + render vigente en la cola

La columna `texto` guarda el mensaje generado al crear el recordatorio (auditoría/export futuro). La cola **re-renderiza** el texto con los datos vigentes del turno, paciente y profesional usando la misma función de plantilla. Motivo: un turno reprogramado después de generar el aviso no debe mostrarle a recepción una fecha/hora vieja.

*Alternativas consideradas:*
- Actualizar `texto` desde el servicio de turnos al reprogramar: acopla C-07 a recordatorios y obliga a tocar la máquina de estados.
- No persistir `texto` y derivarlo siempre: contradice el modelo de datos de la KB (`04_modelo_de_datos.md`).

### 6. Dirección del consultorio por configuración de despliegue

Se agrega `CONSULTORIO_DIRECCION` (opcional, default vacío) a `Settings`. En v1 cada deploy sirve un tenant (`TENANT_DEFAULT_SLUG`), así que la dirección es configuración del despliegue y no requiere migrar `tenant`. Si la dirección está vacía, la plantilla omite esa línea en lugar de mostrar un placeholder.

*Alternativas consideradas:*
- Columna `direccion` en `tenant`: correcta a largo plazo, pero cambia el contrato de `core/tenancy` y agrega una migración de tabla existente fuera del alcance de C-11.

### 7. Transiciones del recordatorio

Estados: `pendiente → enviado | fallido`, `fallido → enviado | fallido`. `enviado` es terminal (reenviarlo es un error de dominio). Marcar `fallido` no escribe `enviado_por`. La base refuerza `(estado = 'enviado') ⇒ enviado_por IS NOT NULL` con un CHECK, además de la validación en servicio (defensa en profundidad, R7).

### 8. Cola con join al turno y alcance por profesional

`GET /recordatorios/pendientes` hace un `select` con join a `turno`, `paciente` y `profesional`, filtrando `recordatorio.estado IN ('pendiente','fallido')` y `turno.estado = 'confirmado'`, ordenado por `turno.inicio`. El filtro por `turno.estado` evita mostrar avisos de turnos cancelados sin borrar filas ni acoplar la cancelación a recordatorios.

El alcance se resuelve con el helper existente `profesional_del_alcance(session, usuario, None)` (mismo criterio que turnos): dueño/recepción → todos; profesional sin `es_dueno` → solo su `profesional_id`. El marcado valida pertenencia al alcance antes de escribir; fuera de alcance o de otro tenant → 404 genérico.

### 9. Frontend dentro de la rama privada existente

`features/recordatorios` con una página `/app/recordatorios` colgada de `PrivateRoute` (sin esperar el shell de C-10). El estado del fetch es local (`useEffect` + `useState`), los tipos son `readonly` y no se usa `any` (R2). El botón de copiar usa `navigator.clipboard.writeText` con fallback silencioso a selección manual si el navegador lo bloquea. Los errores se muestran por `ApiError.code` (RN-GL-01).

## Risks / Trade-offs

- **[Worker caído más de la ventana]** → Mitigación: catch-up de turnos confirmados a menos de `min_hs` sin recordatorio; la idempotencia por unicidad evita duplicar al recuperarse.
- **[Dos workers ejecutando el job a la vez]** → Mitigación: `UNIQUE (tenant_id, turno_id)` hace que la segunda inserción falle; el job captura la violación por turno y continúa con el resto.
- **[Recordatorio huérfano tras cancelar el turno]** → Mitigación: la cola filtra por `turno.estado = 'confirmado'`; la fila queda como historial (no se borra).
- **[Texto desactualizado tras reprogramar]** → Mitigación: la cola re-renderiza con los datos vigentes (decisión 5).
- **[Dirección por env var y multi-tenant futuro]** → Trade-off aceptado para v1 (un tenant por deploy); migrar a `tenant.direccion` en post-MVP.
- **[Zona horaria y DST]** → Mitigación: la plantilla formatea con `ZoneInfo("America/Argentina/Buenos_Aires")`; la comparación de ventana se hace en UTC (`timestamptz`), sin aritmética local.

## Migration Plan

- Migración `0007_recordatorio` con `down_revision = "0006_turno"`:
  - enums `canal_recordatorio` (`whatsapp_manual`) y `estado_recordatorio` (`pendiente`, `enviado`, `fallido`);
  - tabla `recordatorio` con FKs `tenant`, `turno` (`ON DELETE CASCADE`), `usuario` (`ON DELETE SET NULL`), CHECK de coherencia de `enviado_por`, `UNIQUE (tenant_id, turno_id)` e índice `(tenant_id, estado)`;
  - `downgrade` elimina tabla y enums.
- Rollback: `alembic downgrade 0006_turno` (la tabla es nueva, no hay datos previos que preservar).
- Despliegue: `docker compose up` aplica la migración en `api`; el `worker` toma el nuevo `jobs.py` y agenda el cron al reiniciar. Sin downtime especial.
- Seed: no crea recordatorios (los genera el job); los tests los crean explícitamente.

## Open Questions

Ninguna que cambie specs, enfoque o desglose de tareas. La conveniencia de regenerar avisos ante reprogramaciones dentro de la ventana ya queda cubierta por la decisión 5.
