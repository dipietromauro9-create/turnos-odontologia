# Tasks

Esta lista es un plan, no evidencia de ejecución. **No iniciar ninguna tarea de implementación sin una nueva aprobación explícita del usuario: C-09 tiene gobernanza ALTA.** Los artefactos de esta propuesta no autorizan `apply`.

En cada grupo que modifique archivos existentes: ejecutar primero sus tests actuales y registrar la baseline; detenerse ante un fallo preexistente real. Usar Python 3.12, `uv run --frozen`, TypeScript strict sin `any` (R2), y PostgreSQL/Redis aislados. Cada conducta sigue RED ejecutado → GREEN mínimo → TRIANGULATE con al menos dos casos → REFACTOR con tests verdes.

## 1. Aprobación y línea base

- [x] 1.1 Recuperar la aprobación humana explícita para implementar estos artefactos y confirmar con `openspec status --change c-09-turnero-publico --json` e `openspec instructions apply --change c-09-turnero-publico --json` que se trabaja sobre los contextFiles actuales; registrar evidencia.
- [x] 1.2 Ejecutar la baseline completa de tests: backend (`uv run --frozen pytest -q`) y frontend (`npm test -- --run` en `frontend/`); registrar recuento y confirmar cero fallas previas reales.
- [x] 1.3 Verificar que C-09 no requiere migración: `alembic heads` debe mostrar `0006_turno` y `alembic check` no debe detectar cambios de metadata.

## 2. Catálogo público y disponibilidad por slug (RN-AG-04, R3)

- [x] 2.1 **RED** — Agregar `backend/tests/test_turnero_publico_api.py` testeando `GET /turnero/{slug}/catalogo` y `GET /turnero/{slug}/disponibilidad`: slug existente vs. inexistente (404), filtros por profesional/prestación, respuesta sin PII de pacientes y confirmación de que no requiere header JWT; ejecutar y comprobar fallo por ruta no implementada.
- [x] 2.2 **GREEN** — Implementar `backend/app/domain/turnero/schemas.py` (con `extra='forbid'`) y `router.py` con resolución de tenant por slug y delegación en el motor de huecos de C-08; verificar que pasan los tests de 2.1.
- [x] 2.3 **TRIANGULATE** — Extender tests con profesionales inactivos (no deben listarse en catálogo), rango mayor a 31 días (422), consultorio inactivo (404) y aislamiento de datos entre dos tenants distintos; ejecutar y registrar recuento.
- [x] 2.4 **REFACTOR** — Extraer dependency reutilizable `get_tenant_por_slug` y limpiar schemas; verificar tests y Ruff.

## 3. Rate limiting y reserva pública anónima (RN-TU-01, RN-TU-02, RN-PA-01, RN-GL-01)

- [x] 3.1 **RED** — Extender `backend/tests/test_turnero_publico_api.py` con `POST /turnero/{slug}/reservas`: reserva exitosa devuelve 201 con `codigo_publico`, cálculo de `fin` automático, creación o reutilización de paciente por teléfono, detección de colisión/solape con 409 `RN-TU-01`, y rate limiting excedido respondiendo 429; ejecutar y verificar fallo.
- [x] 3.2 **GREEN** — Implementar servicio de reserva pública y dependency de rate limiting en `backend/app/domain/turnero/` usando Redis/memoria; registrar el endpoint en el router público y verificar tests de 3.1.
- [x] 3.3 **TRIANGULATE** — Cubrir reserva concurrente del mismo hueco (verificando que solo uno gana 201 y el otro recibe 409 `RN-TU-01`), advertencia de duplicado cuando el teléfono coincide pero el nombre difiere (`duplicado_advertencia: true`), y validación de teléfono/nombre mal formados (422); ejecutar y registrar.
- [x] 3.4 **REFACTOR** — Modularizar la lógica transaccional de reserva y asegurar captura de constraint `EXCLUDE`; verificar tests y Ruff.

## 4. Autogestión de turnos con código público (RN-TU-05, RN-TU-06, RN-TU-07)

- [x] 4.1 **RED** — Agregar tests en `backend/tests/test_turnero_autogestion_api.py` para `GET /turnero/mis-turnos?codigo=`, `POST /turnero/mis-turnos/cancelar` y `POST /turnero/mis-turnos/reprogramar`: código válido devuelve turno sin PII de terceros, código inválido responde 404 sin enumerar, cancelación libera el hueco guardando motivo opcional, y reprogramación actualiza horario atómicamente; ejecutar y comprobar fallo.
- [x] 4.2 **GREEN** — Implementar endpoints de autogestión en `backend/app/domain/turnero/` validando `codigo_publico`, aplicando la máquina de estados para cancelación y `SELECT FOR UPDATE` para reprogramación; verificar tests de 4.1.
- [x] 4.3 **TRIANGULATE** — Cubrir reprogramación con nuevo horario ocupado (debe fallar con 409 `RN-TU-01` manteniendo el turno original intacto), cancelación de turno ya cancelado o atendido (422 `RN-TU-04`), y código público con formato inválido; ejecutar y registrar.
- [x] 4.4 **REFACTOR** — Unificar respuestas de turno público y asegurar cumplimiento de R1 (`extra='forbid'`) y R6 (cálculo de fin); ejecutar suite backend y Ruff.

## 5. Frontend: Cliente de API y vistas de turnero público

- [x] 5.1 **RED** — Agregar tests en `frontend/src/features/turnero/TurneroPublico.test.tsx` (Vitest) para el flujo de selección de semana, renderizado de huecos libres, apertura del modal de reserva y envío del formulario; ejecutar y verificar que falla por componentes ausentes.
- [x] 5.2 **GREEN** — Implementar `frontend/src/shared/api/turneroClient.ts`, `TurneroPublicoPage.tsx`, `SemanaSelector.tsx`, `HuecosGrid.tsx` y `ReservaModal.tsx` con TypeScript estricto (R2); verificar que 5.1 pasa.
- [x] 5.3 **TRIANGULATE** — Agregar tests de estados de carga, manejo de error de horario ocupado (409) con mensaje amigable al paciente, y pantalla de confirmación exitosa con botón para copiar el código generado; ejecutar tests en Vitest.
- [x] 5.4 **REFACTOR** — Mejorar accesibilidad de formularios y selectores, extraer constantes y tipos compartidos; ejecutar linter y Vitest.

## 6. Frontend: Vistas de autogestión Mis Turnos

- [x] 6.1 **RED** — Agregar tests en `frontend/src/features/turnero/MisTurnos.test.tsx` probando la búsqueda por código, visualización del turno, modal de cancelación con motivo y modal de reprogramación de fecha; ejecutar y registrar fallo.
- [x] 6.2 **GREEN** — Implementar `frontend/src/pages/turnero/MisTurnosPage.tsx` y componentes asociados en `frontend/src/features/turnero/`; registrar las rutas `/turnero/:slug` y `/turnero/mis-turnos` en `frontend/src/routes.tsx` bajo `PublicRoute`; verificar tests de 6.1.
- [x] 6.3 **TRIANGULATE** — Cubrir casos de código inválido (mensaje de turno no encontrado), cancelación exitosa que actualiza la vista a estado cancelado, y reprogramación con error por horario no disponible; verificar tests en Vitest.
- [x] 6.4 **REFACTOR** — Revisar tipado estricto (sin `any`), navegación fluida y estilos; ejecutar tests de frontend y verificar build de producción (`npm run build`).

## 7. Verificación integral E2E y reconciliación documental

- [x] 7.1 Ejecutar suite completa backend (`uv run --frozen pytest -q`) y frontend (`npm test -- --run` y `npm run build`), verificando que todas las pruebas pasen sin advertencias ni regresiones.
- [x] 7.2 Ejecutar un test E2E HTTP de integración real (Python/httpx) en base de datos aislada migrada que recorra: consulta de disponibilidad pública por slug -> reserva anónima -> verificación de paciente creado/reutilizado y código emitido -> consulta por código en mis-turnos -> reprogramación atómica -> cancelación liberando el hueco.
- [x] 7.3 Ejecutar `openspec validate c-09-turnero-publico --strict` y `git diff --check`.
- [x] 7.4 Reconciliar documentación: actualizar `CHANGES.md` (marcar C-09 completado), actualizar specs principales con la nueva capability `publico/turnero` y sincronizar la base de conocimiento.

## Workflow follow-up

- Sincronizar la capability `publico/turnero` a las specs principales y archivar el change con `/opsx:archive c-09-turnero-publico`.
- No hacer commit ni push sin pedido explícito (U1).
