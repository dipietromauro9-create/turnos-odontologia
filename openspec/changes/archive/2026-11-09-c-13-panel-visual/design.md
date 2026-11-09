# Design

## Context

Ver `proposal.md`. El panel ya cumple el contrato funcional de C-10 y el diseño de referencia está exportado en `docs/design/agenda/`. El proyecto no usa Tailwind (DD-10) y el turnero público comparte el mismo bundle, así que los estilos nuevos no deben filtrarse a sus pantallas.

## Goals / Non-Goals

**Goals:**

- Dar al panel la jerarquía visual del design system exportado: superficies slate, acento teal, tipografía clara y densidad de agenda.
- Mantener el cambio acotado a CSS y clases de presentación.

**Non-Goals:**

- No se agrega una librería de estilos ni fuentes externas obligatorias.
- No se rediseña el turnero público ni la ficha clínica.
- No se cambian componentes, hooks ni contratos de API.

## Decisions

**1. Un stylesheet global scopeado, no estilos por componente.**
`shared/styles/panel.css` se importa una vez en `main.tsx`; las reglas viven bajo `.panel-shell` y `.login-page`. Alternativa descartada: CSS modules por componente (más archivos y sin beneficio para un shell compartido).

**2. Tokens del design system como variables CSS locales.**
Se reutilizan los valores de `docs/design/agenda/DESIGN.md` (teal `#0D9488`, slate, radios de 4/8 px) en variables dentro de `.panel-shell, .login-page`. Alternativa descartada: hardcodear hex en cada regla, que ya está prohibido por la skill `pantalla-a-componente`.

**3. Tipografías con fallback, sin request externo.**
Se declara `"Plus Jakarta Sans"` para títulos e `"Inter"` para cuerpo, con `system-ui` de fallback; no se importa Google Fonts para no agregar una dependencia de red al arranque. Alternativa descartada: `@import` remoto, que degrada la app offline.

**4. El turnero público queda fuera del scope.**
Ninguna regla nueva apunta a sus clases; solo se normaliza `body` (margin 0, tipografía base), lo que mejora también esa pantalla sin cambiar su estructura.

**5. Modal con overlay propio.**
El `section[role="dialog"]` pasa a ser overlay y el contenido se envuelve en `.modal__caja`; se mantiene el foco y las etiquetas accesibles existentes.

## Risks / Trade-offs

- **El contenedor `web` sirve la imagen, no el código** → documentar y ejecutar `docker compose up -d --build web` después de cambios de estilo.
- **Fuente no instalada** → fallback a `system-ui`; la jerarquía se mantiene con pesos y tamaños.
- **Especificidad entre `panel.css` y `estados.css`** → `panel.css` no define reglas `.turno`; las tarjetas siguen siendo dueñas de su capa.
- **Regresiones visuales no cubiertas por tests** → verificación manual en navegador de login, agenda y modal; los tests funcionales siguen corriendo.
