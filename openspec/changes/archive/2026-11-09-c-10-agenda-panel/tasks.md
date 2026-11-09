# Tasks

## 1. Backend: agregador de agenda

- [x] 1.1 Crear `backend/app/domain/agenda/panel/` (`__init__.py`, `schemas.py`, `service.py`, `router.py`) y montar el router en `main.py`; verificar que la app importa y que `/agenda/dia` y `/agenda/semana` aparecen en OpenAPI
- [x] 1.2 Implementar `GET /agenda/dia?fecha=` y `GET /agenda/semana?desde=` con rango semiabierto, semana desde lunes, máximo 7 días y cálculo en `settings.tz`; tests de borde de día, lunes y rango inválido (422)
- [x] 1.3 Componer la respuesta con `rango`, `profesionales` activos, `prestaciones` activas, `turnos` con `paciente{id,nombre}` y `prestacion{id,nombre}`, y `bloqueos` del rango (incluidos los globales); test de payload con nombres y bloqueo global
- [x] 1.4 Aplicar alcance con `require_role(RECEPCION, PROFESIONAL)` y `profesional_del_alcance`: recepción/dueño ven todo, profesional sin flag solo lo propio, otro `profesional_id` → 403 `RN-AU-03`, sin token → 401; tests por rol
- [x] 1.5 Garantizar aislamiento por tenant y minimización de datos: test de que no aparecen datos de otro tenant ni `documento`, `telefono`, `fecha_nac` u `observaciones`

## 2. Frontend: sesión real del panel

- [x] 2.1 Implementar `features/auth` con formulario de login (`POST /auth/login`), guardado versionado del access y bootstrap de `GET /auth/me` para `rol` y `es_dueno`; test de login exitoso y de identidad cargada
- [x] 2.2 Extender `shared/api/client.ts` para adjuntar el Bearer y reintentar una sola vez con `POST /auth/refresh` (`credentials: "include"`) ante 401 de panel; tests de refresh transparente, refresh fallido → limpiar sesión y login 401 sin refresh
- [x] 2.3 Reemplazar el login provisorio en `routes.tsx`/`LoginPage`: guard de rutas privadas, navegación según rol y logout con `POST /auth/logout`; tests de anónimo → login, recepción sin secciones de dueño y logout
- [x] 2.4 Exportar `logout`/`me` en `shared/api/auth.ts` y cubrir el contrato con `MeOut` (`rol`, `es_dueno`) sin `any`; test de tipos y de respuesta con campos extra rechazados

## 3. Frontend: agenda día/semana

- [x] 3.1 Crear `shared/api/agendaClient.ts` tipado para `/agenda/dia` y `/agenda/semana` y sus esquemas; test de mapeo de respuesta completa y de error de dominio
- [x] 3.2 Copiar `estados.css` a `features/agenda` e implementar `TurnoCard` con la skill `pantalla-a-componente` (etiqueta textual de estado, badge de sobreturno, acciones por estado); test de tarjeta con datos y sobreturno
- [x] 3.3 Implementar la vista día/semana con navegación, columnas por profesional, filtro y los cuatro estados de UI (cargando, vacío, error, datos); tests de render semanal, vacío y error con `RN-XX-NN`
- [x] 3.4 Ocultar el selector de otros profesionales al profesional sin flag y mostrar solo su columna; test de RBAC de vista con `/auth/me` de rol profesional sin dueño
- [x] 3.5 Implementar el alta de turno interno (búsqueda de paciente, prestación, profesional, fecha/hora y sobreturno con motivo) contra `POST /turnos` y el motor de huecos; tests de alta normal, sobreturno sin motivo y error `RN-TU-01`
- [x] 3.6 Implementar las acciones de transición por estado contra los endpoints de `core/turnos`, con refresco ante 422 `RN-TU-04`; tests de acciones por estado, terminal sin acciones y conflicto concurrente
- [x] 3.7 Implementar la configuración de disponibilidad/bloqueos solo para dueño contra `/disponibilidad` y `/bloqueos`; tests de alta/eliminación y de controles ocultos para recepción

## 4. Integración y cierre

- [x] 4.1 Test de integración de frontend con API mockeada: login → agenda → alta de turno → confirmación, verificando el flujo completo sin datos reales (R9)
- [x] 4.2 Verificar el sistema completo: `pytest` backend, `npm run typecheck`, `npm run lint` y `npm test` en verde, sin `any` en `features/agenda` ni `features/auth`
- [x] 4.3 Actualizar `docs/design/agenda/README.md` con el alcance finalmente implementado (shell mínimo, agregador y configuración) y dejar el change listo para archive
