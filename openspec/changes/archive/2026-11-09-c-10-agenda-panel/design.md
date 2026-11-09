# Design

## Context

Ver `proposal.md` para la motivación. El estado actual que condiciona el diseño:

- `GET /turnos` devuelve referencias por id y no incrusta nombres ni fichas (`core/turnos`); su `limit` máximo es 100.
- `GET /profesionales` y `GET /prestaciones` son exclusivos del dueño (RN-AU-02), pero la agenda necesita columnas, filtros y catálogo para recepción.
- `profesional_del_alcance` ya resuelve RN-AU-03 y `require_role` ya cubre recepción/profesional.
- El motor de huecos (`GET /disponibilidad/huecos`) exige `profesional_id` y `prestacion_id`, por lo que no sirve como fuente única de una grilla multi-profesional.
- El frontend no tiene login real: `LoginPage` es un placeholder y el cliente HTTP solo adjunta un token de `localStorage` sin refresh.
- El diseño visual aprobado está exportado en `docs/design/agenda/` (Stitch) y el proyecto no usa Tailwind (DD-10).

## Goals / Non-Goals

**Goals:**

- Una sola consulta por período que entregue todo lo que la grilla necesita para pintar día/semana, sin N+1 y sin abrir los catálogos de gestión.
- Sesión de panel real y acotada: login, refresh transparente una vez, identidad con rol y `es_dueno`, logout.
- Colores y estados consistentes con los tokens de `estados.css`, sin hardcodear hex en componentes.

**Non-Goals:**

- No se agrega disponibilidad/huecos al agregador: el alta de turno consulta el motor de huecos cuando el usuario elige prestación y horario.
- No se implementa el shell completo del mockup (sidebar/top bar de Stitch) ni la ficha clínica.
- No se mueve la lógica de creación ni de transición al frontend: el backend sigue siendo la única autoridad (R4).
- No se cambia el contrato de `/turnos`, `/profesionales` ni `/prestaciones`.

## Decisions

**1. Agregador backend en vez de composición en el cliente.**
`GET /agenda/dia` y `/agenda/semana` devuelven `rango`, `profesionales`, `prestaciones`, `turnos` y `bloqueos` en una respuesta. Alternativas descartadas: (a) componer con `/turnos` + N llamadas a pacientes/prestaciones, que además devuelve 403 para recepción en los directorios; (b) paginar `/turnos` en el cliente, que no resuelve nombres ni el límite de 100. El agregador concentra RBAC, tenant y composición en un solo lugar.

**2. Payload con nombres mínimos y sin ficha clínica.**
Cada turno viaja con `paciente: {id, nombre}` y `prestacion: {id, nombre}`; nunca documento, teléfono, fecha de nacimiento ni observaciones. Los profesionales llevan id, nombre, especialidad y activo; las prestaciones, id, nombre, duración y activo. Alternativa descartada: reutilizar `PacienteOut` completo, que expone datos que la grilla no necesita.

**3. Rango por fecha de calendario en la zona del consultorio.**
`dia?fecha=YYYY-MM-DD` y `semana?desde=YYYY-MM-DD` se resuelven con `ZoneInfo(settings.tz)` a un rango semiabierto `[inicio, fin)`; la semana empieza el lunes y se rechaza un rango mayor a 7 días. Alternativa descartada: recibir `AwareDatetime` desde/hasta como huecos, que obliga al cliente a calcular bordes con offsets y facilita inconsistencias de zona (RN-GL-03).

**4. RBAC reutilizando el alcance existente.**
El router exige `require_role(RECEPCION, PROFESIONAL)` y el servicio resuelve el profesional con `profesional_del_alcance`. Para un profesional sin flag, la consulta se filtra por su propio id y la lista de profesionales se reduce a sí mismo; pedir otro id devuelve 403 `RN-AU-03`. Alternativa descartada: filtrar solo en el frontend (inseguro) o duplicar la lógica de alcance (divergiría de `core/turnos`).

**5. El agregador es de solo lectura; escrituras siguen por los endpoints existentes.**
Crear turno, sobreturno y transicionar usan `POST /turnos`, las acciones de `core/turnos` y el motor de huecos. El agregador nunca escribe. Esto preserva la máquina RN-TU-04 y el anti-solape como única vía (R4) y evita duplicar reglas.

**6. Sesión en el cliente HTTP, no en cada feature.**
`shared/api/client.ts` adjunta el Bearer y, ante un 401 de panel, llama una vez a `/auth/refresh` con `credentials: "include"` y repite la request; si falla, limpia la sesión y redirige al login. `features/auth` implementa el formulario y llama a `/auth/me` para obtener rol y `es_dueno`. Alternativas descartadas: decodificar claims (el claim no trae `es_dueno`), o inyectar tokens a mano en dev (no es usable ni testeable).

**7. Componentes de agenda con tokens, generados con la skill.**
`features/agenda` se arma a partir de `docs/design/agenda/583dff22e2694257a60010f10a833229.html` usando `pantalla-a-componente`: HTML semántico, `className`, `estados.css` y tests Vitest. El HTML de Stitch es insumo, no se copia; no se agrega Tailwind (U3/DD-10). La tarjeta muestra siempre etiqueta textual de estado y del sobreturno, además del color.

**8. Configuración de agenda del dueño con los endpoints de C-06.**
La UI de disponibilidad/bloqueos lista, crea y elimina contra `/disponibilidad` y `/bloqueos`; los controles se renderizan solo para `es_dueno`. El backend ya responde 403 a recepción y profesional sin flag, así que la restricción no depende del cliente.

**9. Sin migración.**
No hay entidades nuevas: se leen `Turno`, `Profesional`, `Prestacion`, `Bloqueo` y `Paciente` existentes. Los índices actuales por `(tenant_id, profesional_id, inicio)` sostienen el rango.

## Risks / Trade-offs

- **Respuesta semanal grande** → rango máximo de 7 días, una sola query con joins y sin N+1; si un consultorio crece, se evalúa paginar por profesional en un change posterior.
- **Bucles de refresh/redirección** → un solo reintento por request, bandera de “refresh en curso” y limpieza de sesión ante fallo; tests explícitos de refresh inválido.
- **Bordes de zona horaria** (medianoche, cambio de día) → todo el cálculo en `settings.tz` y rango semiabierto; tests de lunes y de fin de día.
- **Duplicación de la proyección de profesionales/prestaciones** respecto de los directorios → se limita a lectura y se documenta como excepción en las specs modificadas; la gestión sigue dueño-only.
- **Fidelidad del mockup sin Tailwind** → los tokens y el CSS puro pueden diferir en detalles del HTML de Stitch; se prioriza estructura y accesibilidad sobre pixel-perfect.

## Migration Plan

1. Desplegar backend (endpoint aditivo, sin migración) y verificar `/agenda/dia|/semana` con los tests de RBAC/tenant.
2. Desplegar frontend con el login real; como el backend ya soporta `/auth/*`, no hay ventana de incompatibilidad.
3. Rollback: revertir el deploy del frontend y, si hace falta, quitar el router de agenda; no hay datos que migrar.
