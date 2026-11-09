# Proposal

## Why

C-10 dejó el panel funcional pero visualmente crudo: solo las tarjetas de turno usaban los tokens de estado; el shell, la toolbar, la grilla, el modal, el login y la configuración no tenían layout. Eso no refleja el diseño aprobado de Stitch y hace que el MVP se vea inacabado. Este change registra el pulido visual ya aplicado, como mantenimiento posterior al cierre del roadmap.

## What Changes

- Nuevo stylesheet global del panel (`frontend/src/shared/styles/panel.css`): shell, barra superior, navegación, toolbar, grilla, columnas, modal, login y configuración.
- Refinamiento de las tarjetas de turno en `features/agenda/estados.css`: composición interna, tipografía tabular, hover y acciones compactas.
- Clases de presentación en `AppShell`, `LoginPage`, `AgendaPage`, `NuevoTurnoModal` y `ConfiguracionAgenda`.
- Responsive (una columna en móvil), foco visible y respeto a `prefers-reduced-motion`.
- **Sin cambios de comportamiento, API, datos ni dependencias.** No se agrega Tailwind. El turnero público queda intacto.
- **Nota de proceso**: el cambio ya está implementado y verificado; este registro formaliza la trazabilidad solicitada.

## Capabilities

### New Capabilities

Ninguna: es un cambio puramente de presentación, sin comportamiento observable nuevo. Se declara `skip_specs: true` en `.openspec.yaml`.

### Modified Capabilities

Ninguna: los requisitos de `core/agenda` y `foundation/frontend-shell` no cambian; la UI ya cumplía el contrato y solo se ajustó su aspecto.

## Impact

- **Frontend**: `main.tsx` importa el stylesheet global; `shared/styles/panel.css` (nuevo); `features/agenda/estados.css`; clases en los cinco componentes mencionados.
- **Backend / DB**: sin impacto. Sin migraciones.
- **Tests**: sin cambios; la suite frontend existente (58 tests) sigue en verde y `tsc`/ESLint no se ven afectados.
- **Operación**: como el servicio `web` de Compose no monta el código, el cambio requiere rebuild del contenedor para verse.
