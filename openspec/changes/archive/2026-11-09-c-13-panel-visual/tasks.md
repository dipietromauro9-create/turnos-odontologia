# Tasks

## 1. Estilos base del panel

- [x] 1.1 Crear `frontend/src/shared/styles/panel.css` con variables del design system e importarlo en `main.tsx`; verificar `npm run typecheck`
- [x] 1.2 Estilar el shell (`AppShell`) y el login (`LoginPage`): barra sticky, navegación en pills y card centrada; verificar en navegador

## 2. Agenda

- [x] 2.1 Estilar toolbar, grilla, columnas y tarjetas (`AgendaPage`, `estados.css`): segmentación, cards y composición interna; verificar la vista semanal con datos del seed
- [x] 2.2 Estilar el modal de alta (`NuevoTurnoModal`) y la configuración del dueño (`ConfiguracionAgenda`); verificar alta normal, sobreturno y gestión de franjas/bloqueos

## 3. Accesibilidad y cierre

- [x] 3.1 Agregar responsive (una columna en móvil), foco visible teal y `prefers-reduced-motion`; verificar a 720 px y navegación por teclado
- [x] 3.2 Rebuild de `web` y verificación final: login, agenda y modal en el navegador, con `npm run typecheck`, `npm run lint` y `npm test` en verde
