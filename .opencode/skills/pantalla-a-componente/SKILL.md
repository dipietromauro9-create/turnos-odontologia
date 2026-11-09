---
name: pantalla-a-componente
description: Convierte una pantalla ya diseñada en componentes React + TypeScript tipados para este repo, con tokens de color por estado y tests Vitest. La pantalla viene de Stitch (projectId + screenId) o de un HTML/PNG exportado en docs/design/. Usá esta skill siempre que haya que implementar una pantalla del panel (agenda día/semana, turnero, recordatorios, reportes), pasar un diseño a componentes, mencionar Stitch, screenId, projectId o un HTML de diseño, o cuando el usuario hable de colores/tokens por estado de turno — incluso si no dice explícitamente "componentes".
license: Uso interno del proyecto turnos-odontologia
---

# Pantalla a componente

Convertís una pantalla aprobada visualmente en código del proyecto: componentes React + TypeScript, tokens de color por estado y tests. El objetivo es que la decisión visual quede **congelada antes** de mezclarla con lógica de negocio, para que un change de UI no tenga que inventar colores, estados de carga ni nombres de props sobre la marcha.

## Límites (leelos antes de escribir código)

- El proyecto **no usa Tailwind ni librería de componentes**. El HTML que devuelve Stitch trae estilos embebidos: es **insumo de diseño, no código final**. Reescribí la estructura como componentes del repo (HTML semántico + `className` + CSS puro).
- **R9**: nunca uses datos reales de pacientes. En prompts, fixtures, capturas y tests usá nombres ficticios (`Paciente Ficticio`, `Dra. Martina`) y fechas futuras o irreales.
- **R2**: cero `any`, props `readonly`, componentes y archivos en PascalCase. El `tsconfig` ya está en `strict`.
- **No inventes pantallas, campos ni endpoints.** Si la pantalla muestra un dato que no existe en el contrato del backend, detenete y preguntá. Si el `screenId` no existe o no hay artefacto en `docs/design/`, pedilo; no generes una pantalla "parecida" para poder avanzar.

## Entradas válidas

1. **Stitch en vivo**: `projectId` + `screenId` (o el nombre de la pantalla). Usá el MCP `stitch`:
   - `list_screens` / `get_screen` para confirmar que la pantalla existe.
   - `download_file` con el `name` del archivo de la pantalla para bajar el **HTML** y la **captura PNG**.
   - Guardá ambos en `docs/design/<feature>/<screenId>.html` y `.png` (convención en `docs/design/README.md`).
2. **Artefactos locales**: `docs/design/<feature>/<screenId>.html` + `.png`, opcionalmente `DESIGN.md` del design system.

Si tenés que generar o editar la pantalla en Stitch (`generate_screen_from_text`, `edit_screens`, `generate_variants`) o borrar un proyecto (`delete_project`), **pedí confirmación explícita primero**: son acciones lentas y cambian la fuente de diseño. Si `generate_variants` da timeout, no reintentes.

## Flujo

### 1. Confirmá la fuente y el destino

- Registrá la fuente exacta en el encabezado de cada archivo generado:
  `// Fuente de diseño: Stitch <projectId>/<screenId> — docs/design/<feature>/<screenId>.html`
  Esto permite auditar después si el componente corresponde a una pantalla real.
- Destino por defecto: `frontend/src/features/<feature>/`. Para C-10 es `agenda`; para el turnero público ya existe `features/turnero` (no la pises sin avisar).
- Si el usuario no dijo la feature, deducila del nombre de la pantalla y confirmala en una línea. No crees una carpeta nueva por cada componente.

### 2. Extraé el inventario de la pantalla

Antes de escribir JSX, listá en el chat o en un comentario breve:

- **Regiones**: toolbar, selector de día/semana, grilla/columnas, panel lateral, modales.
- **Datos visibles por tarjeta/fila**: hora de inicio y fin, paciente, profesional, prestación, estado, sobreturno.
- **Acciones**: qué botones aparecen y en qué estado (ver RN-TU-04 abajo).
- **Estados de UI**: con datos, vacío, cargando y error.
- **RBAC**: qué ve cada rol (matriz de `knowledge-base/03_actores_y_roles.md`). El filtro por profesional es de vista, no un permiso nuevo: recepción y dueño ven todo; el profesional solo lo propio (RN-AU-03).

Si un dato o una acción no está en el contrato (`knowledge-base/05_reglas_de_negocio.md` o los tipos de `shared/api/`), preguntá antes de codear.

### 3. Fijá los tokens (una sola vez por feature)

Leé `references/tokens-estado.md` y copiá `assets/estados.css` a `frontend/src/features/<feature>/estados.css` si todavía no existe. Importalo una vez en el componente raíz de la feature.

Reglas de uso:

- Los colores **solo** salen de las variables CSS (`--turno-reservado-bg`, etc.). No escribas hex en los componentes.
- El estado **nunca** se comunica solo por color: siempre hay una etiqueta textual visible y un `aria-label`. Es requisito de accesibilidad, y además la agenda se imprime y se mira en pantallas malas.
- El sobreturno no es un estado más: es un flag (`es_sobreturno`) que se muestra como etiqueta explícita, nunca como solape silencioso.
- Si `docs/design/DESIGN.md` o el design system de Stitch define otra paleta, adaptá **solo los valores hex** de `estados.css` y dejá los nombres de las variables iguales. Así los componentes no cambian.

### 4. Generá los componentes

Usá `assets/plantilla-componente.tsx` como esqueleto. Adaptá nombres y props al dominio; no lo copies literal con datos mock adentro.

- Un archivo por componente, `PascalCase`, retorno `React.JSX.Element`, props `readonly`.
- Separá **presentación** de **datos**: el componente de tarjeta/grilla recibe datos y callbacks; la página hace el fetch. Eso hace testeable la vista sin mockear toda la API.
- Modelá los 4 estados de UI de forma explícita (cargando, error, vacío, con datos). El orden de prioridad es error → cargando → vacío → datos, para que un error no quede tapado por un spinner.
- Mensajes de error: mostrá el código de regla cuando venga en la respuesta (`RN-TU-04`, `RN-TU-01`, etc.). No traduzcas el código a un texto genérico: es el mecanismo de diagnóstico del proyecto (RN-GL-01).
- Acciones de transición según RN-TU-04:
  - `reservado` → confirmar, cancelar
  - `confirmado` → atender, registrar ausencia, cancelar
  - `atendido` / `cancelado` / `ausente` → sin acciones (terminales)

  La UI solo ofrece las acciones válidas, pero igual manejá el 422 de regla: el backend es la fuente de verdad y otro usuario pudo cambiar el estado antes.
- Nada de `<div onClick>`: botones reales con `type="button"`, foco visible y texto accesible.

### 5. Escribí los tests

Usá `assets/plantilla-test.tsx`. Cubrí, como mínimo:

1. Render con datos: muestra paciente/profesional/hora y la **etiqueta textual** del estado.
2. Vacío: muestra el mensaje de "sin turnos" con `role="status"`.
3. Error: muestra el mensaje y el código `RN-XX-NN`; no muestra datos viejos.
4. Cargando: no muestra el vacío como si ya hubiera terminado.
5. Sobreturno: se distingue explícitamente.
6. Transiciones: cada estado ofrece solo sus acciones y dispara el callback correcto.

Usá datos ficticios (R9) y `@testing-library/react` como el resto del repo. No testees clases CSS internas; testeá lo que el usuario ve.

### 6. Verificá antes de decir que terminaste

Desde `frontend/`:

```bash
npm run typecheck
npm run lint
npm test
```

Y confirmá que no quedó ningún `any` en la feature:

```bash
grep -rnE ":\s*any\b|as any|<any>" src/features/<feature>
```

Si alguno de estos falla, no está terminado. Reportá qué comando falló y el error, en lugar de resumir "listo".

## Checklist de salida

- [ ] Cada archivo cita `projectId/screenId` o el artefacto local usado.
- [ ] Existe `estados.css` con los tokens y el componente no hardcodea colores.
- [ ] Los 4 estados de UI están implementados y testeados.
- [ ] Las transiciones visibles coinciden con RN-TU-04.
- [ ] Ningún dato real de paciente en código, fixtures ni tests (R9).
- [ ] `npm run typecheck`, `npm run lint` y `npm test` en verde.
- [ ] Cero `any`.

## Referencias

- `references/tokens-estado.md` — mapeo estado→variable→color y reglas de contraste.
- `assets/estados.css` — hoja de tokens lista para copiar a la feature.
- `assets/plantilla-componente.tsx` — esqueleto de tarjeta de turno con acciones por estado.
- `assets/plantilla-test.tsx` — casos Vitest base (datos, vacío, error, sobreturno, transiciones).
- `docs/design/README.md` — convención de nombres de los artefactos exportados de Stitch.
- `knowledge-base/05_reglas_de_negocio.md` §Turnos — RN-TU-01, RN-TU-04, RN-TU-05.
- `knowledge-base/03_actores_y_roles.md` — matriz RBAC y RN-AU-03.
