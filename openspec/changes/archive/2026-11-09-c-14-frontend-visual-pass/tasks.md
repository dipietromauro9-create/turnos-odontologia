# Tasks

## 1. Diseño en Stitch

- [x] 1.1 Generar en Stitch las pantallas de reserva pública y "Mis turnos" con el design system OdontoGrid y exportarlas a `docs/design/turnero/` (HTML, PNG y prompt)
- [x] 1.2 Generar y exportar las pantallas de recordatorios y reportes a `docs/design/recordatorios/` y `docs/design/reportes/`; verificar que cada carpeta tiene su README y artefactos

## 2. Estilos públicos

- [x] 2.1 Crear `shared/styles/publico.css` e importarlo en `main.tsx`; estilar hero, filtros, navegación semanal, grilla de horarios y confirmación; verificar `npm run typecheck`
- [x] 2.2 Estilar "Mis turnos" y los modales de reserva/cancelación/reprogramación con overlay y card; verificar que los tests de turnero siguen en verde
- [x] 2.3 Estilar la portada pública (`HomePage`) con accesos a panel y turnero; verificar el test del router

## 3. Estilos del panel

- [x] 3.1 Estilar recordatorios (tarjeta, badge de estado, texto copiable y acciones) sin romper los tests de la cola
- [x] 3.2 Estilar reportes (filtros, tablas, listas y exportación) sin cambiar el comportamiento de descarga

## 4. Fix de borde y cierre

- [x] 4.1 Reordenar middlewares para que CORS sea el más externo y los 401 de auth lleven cabeceras; agregar test de regresión
- [x] 4.2 Verificar el refresh real en navegador (access vencido → `/auth/refresh` → reintento) y el estado de las pantallas
- [x] 4.3 Rebuild de `web`/`api` y verificación final: `npm run typecheck`, `npm run lint`, `npm test` (58) y `pytest` (875) en verde
