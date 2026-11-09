# Design

## Context

Ver `proposal.md`. El design system aprobado está en Stitch (`assets/0813ac9037e544cc80665af1bbfe9f7f`) y exportado en `docs/design/agenda/DESIGN.md`. El panel ya tiene `shared/styles/panel.css`; el turnero público comparte bundle pero debe tener una identidad más cálida y mobile-first. El proyecto no usa Tailwind (DD-10).

## Goals / Non-Goals

**Goals:**

- Unificar tipografía, superficies, acento teal, radios y densidad en todas las pantallas.
- Mantener el cambio en CSS + clases, sin reescribir lógica ni contratos.

**Non-Goals:**

- No se copia el HTML de Stitch (tiene shell, campos y contenidos que el MVP no implementa).
- No se agregan fuentes externas obligatorias ni librerías de UI.
- No se rediseña el panel ya cubierto por C-13.

## Decisions

**1. Dos capas de estilos: panel y público.**
`panel.css` sigue scopeado a `.panel-shell`/`.login-page`; `publico.css` se scopea a `.turnero-publico`/`.home-page`. Evita que las tablas y tarjetas del panel contaminen el turnero, y viceversa. Alternativa descartada: un único archivo global con selectores por página, más frágil.

**2. El diseño de Stitch es referencia, no código.**
Se toman jerarquía, paleta, estados y composición de tarjetas; se implementa con el markup existente (formularios, listas, tablas) y clases nuevas. Alternativa descartada: portar el HTML exportado con Tailwind embebido, que rompe DD-10 y agrega campos inexistentes.

**3. Turnero público mobile-first.**
La grilla de horarios usa `auto-fit` con chips de hora, la navegación semanal se apila en mobile y los modales pasan a una card centrada. El panel mantiene su densidad de escritorio.

**4. CORS como middleware externo.**
En Starlette el último `add_middleware` queda más afuera. Se registra Auth, luego Tenant y por último CORS: CORS cubre también los 401 de auth, y Tenant sigue resolviéndose antes que Auth (se conserva el 503 por tenant inexistente). Alternativa descartada: agregar cabeceras CORS a mano en `_respuesta_401`, que duplicaría configuración.

**5. Verificación manual + tests.**
Los tests funcionales no cubren CSS; se verifica login, agenda, turnero, mis turnos, recordatorios y reportes en el navegador, y se agrega un test backend específico para el 401 con CORS.

## Risks / Trade-offs

- **Contenedores sin bind mount** → rebuild de `web` y `api` después de cada cambio.
- **Capturas del navegador no siempre disponibles** (ventana no visible) → se valida por snapshot de accesibilidad y por las capturas de Stitch exportadas.
- **Fuentes no instaladas** → fallback a `system-ui`; la jerarquía se sostiene.
- **Especificidad entre capas** → `publico.css` no define reglas `.panel-shell` y `panel.css` no define `.turnero-publico`.
