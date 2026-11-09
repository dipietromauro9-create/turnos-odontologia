# Proposal

## Why

Las features de frontend que no eran la agenda quedaron funcionales pero sin diseño: el turnero público, "Mis turnos", recordatorios y reportes mostraban HTML sin jerarquía visual. Además, al verificar el refresh apareció un bug real: el 401 del middleware de auth salía sin cabeceras CORS, el navegador lo trataba como error de red y nunca se intentaba renovar el access token.

## What Changes

- Pantallas de Stitch generadas con el design system **OdontoGrid Clinical OS** y exportadas a `docs/design/`:
  - `turnero/`: reserva pública y "Mis turnos".
  - `recordatorios/`: cola de WhatsApp manual.
  - `reportes/`: dashboard del dueño.
- Nuevo `frontend/src/shared/styles/publico.css` para el turnero público, "Mis turnos", sus modales y la portada.
- Extensión de `frontend/src/shared/styles/panel.css` para recordatorios y reportes (tarjetas, badges de estado, tablas y formularios).
- Clases de presentación y ajustes mínimos de markup en `TurneroPublicoPage`, `HuecosGrid`, `ReservaModal`, `CancelarModal`, `ReprogramarModal`, `MisTurnosPage`, `CodigoTurnoCard`, `RecordatoriosPage`, `RecordatorioCard`, `ReportesPage` y `HomePage`.
- **Fix de infraestructura**: `CORSMiddleware` pasa a ser el middleware más externo para que los 401 de auth lleven `Access-Control-Allow-Origin` y el cliente pueda disparar `/auth/refresh`. Se conserva el orden Tenant → Auth.
- Test de regresión del 401 con cabeceras CORS.
- **Sin cambios de contrato, datos ni dependencias**; no se agrega Tailwind. El turnero mantiene su flujo y sus reglas (RN-AU-01, RN-TU-04/05/06/07).

## Capabilities

### New Capabilities

Ninguna: es presentación y un fix de borde cubierto por los requisitos existentes. Se declara `skip_specs: true` en `.openspec.yaml`.

### Modified Capabilities

Ninguna: `core/agenda`, `core/auth`, `fundation/frontend-shell` y `publico/turnero` conservan sus requisitos; el cambio hace que el comportamiento ya especificado (refresh transparente, pantallas utilizables) funcione en el navegador.

## Impact

- **Frontend**: `main.tsx` importa `publico.css`; nuevos estilos y clases en las features mencionadas.
- **Backend**: `main.py` reordena middlewares; `tests/test_auth_middleware.py` suma el caso de CORS en 401.
- **Diseño**: 4 pantallas nuevas en `docs/design/` con prompts y capturas.
- **Operación**: requiere rebuild de `web` y `api` en Compose (los contenedores no montan el código).
- **Tests**: 58 frontend y 875 backend en verde.
