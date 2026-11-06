# Design

## Context

Ver `proposal.md` — Why. C-04, C-05, C-06 y C-07 están archivados; el head real de Alembic es `0006_turno`. El esquema ya tiene `Disponibilidad` (franjas por día de semana), `Bloqueo` (profesional opcional; nulo = todo el consultorio), `Turno` (con EXCLUDE anti-solape y todos los estados salvo `cancelado` ocupando su intervalo), `Prestacion.duracion_min` y `Profesional.activo`.

La guarda `infracciones_turno_en_agenda` de `backend/tests/test_architecture.py` prohíbe que `app/domain/agenda` importe o mencione `Turno`. Por eso el motor no puede vivir junto a la plantilla semanal, aunque conceptualmente la consuma.

Ya existe `GET /disponibilidad` (C-06) para listar la plantilla semanal. El scope histórico de CHANGES.md propone `GET /disponibilidad?...` para los huecos, lo que colisiona con ese contrato ya implementado y probado. Este diseño resuelve la colisión sin romper C-06.

La infraestructura de pruebas usa PostgreSQL real, `TenantSession` con filtro automático de tenant, `UnitOfWork`, factories existentes y un reloj inyectable en el servicio de turnos. C-07 dejó 633 tests verdes como referencia de regresión, no como evidencia ejecutada por esta planificación.

## Goals / Non-Goals

**Goals:**

- Un cálculo determinista y de solo lectura que combine cuatro fuentes (plantilla, bloqueos, turnos ocupantes y duración de prestación) sin escribir ninguna tabla.
- Una función pura fácil de testear con reloj y datos inyectados, separada de las consultas tenant-scoped.
- Un endpoint interno que C-09 y C-10 puedan consumir sin duplicar la lógica, y que sea compatible con una futura envoltura pública sin datos de pacientes.
- Cumplir la meta de menos de 1 segundo por semana con los índices existentes, sin migración nueva.

**Non-Goals:**

- No implementar reserva, cancelación, reprogramación ni rutas públicas por slug (C-09).
- No modificar el contrato de plantilla semanal, bloqueos, turnos, prestaciones o profesionales.
- No agregar columnas, tablas, índices ni revisión Alembic `0007` en este change.
- No ofrecer sugerencias de "próximo hueco", agenda visual, recordatorios ni reportes.
- No reemplazar la validación de C-07: el motor enumera huecos; la creación de un turno sigue validando su propio intervalo en el servicio de turnos.

## Decisions

### 1. Dominio nuevo `app/domain/huecos`, separado de agenda y de la escritura de turnos

Crear `backend/app/domain/huecos/{calculo,repository,service,schemas,router}.py`. El paquete es de solo lectura: no construye ni modifica `Turno`.

- `calculo.py`: función pura, sin sesión, sin SQL y sin reloj global.
- `repository.py`: consultas tenant-scoped de lectura sobre los modelos existentes.
- `service.py`: resuelve tenant/alcance, carga datos y llama a la función pura.
- `router.py`: `GET /disponibilidad/huecos`, roles y validación de parámetros.
- `schemas.py`: entrada/salida con `extra='forbid'` (R1).

Alternativas descartadas:

- Colocarlo en `app/domain/agenda`: la guarda de arquitectura lo impide al necesitar `Turno`.
- Colocarlo dentro de `app/domain/turnos`: mezclaría el servicio único de escritura de turnos con una consulta de agenda y haría más difícil reutilizarlo desde C-09/C-10.
- Poner toda la lógica en el router: impediría testear el cálculo sin HTTP y sin base.

### 2. Ruta `GET /disponibilidad/huecos` para no romper el `GET /disponibilidad` de C-06

C-06 ya expone `GET /disponibilidad` como listado de franjas semanales. El path literal del roadmap no puede reutilizarse sin cambiar el contrato existente. El motor se publica como subruta `/disponibilidad/huecos`, con parámetros `profesional_id`, `prestacion_id`, `desde` y `hasta`.

Se documenta esta reconciliación en el proposal, el design y CHANGES durante el apply. C-09 no necesita esta ruta interna: su envoltorio público (`/turnero/:slug/disponibilidad`) llamará al mismo `service` con el tenant resuelto por slug. C-10 puede usar la ruta interna o el servicio.

Alternativas descartadas:

- Sobrecargar `GET /disponibilidad` según la presencia de `prestacion_id`: dos formatos de respuesta incompatibles en la misma operación y OpenAPI ambiguo.
- Renombrar la ruta de C-06 a `/disponibilidad/plantilla`: **BREAKING** para tests, frontend y consumidores ya archivados.
- Usar `/agenda/disponibilidad`: válido, pero agrega un prefijo que C-06 no usa y no aporta claridad frente a la subruta del recurso ya existente.

### 3. Núcleo puro con datos inyectados

`calcular_huecos(profesional, prestacion, desde, hasta, *, disponibilidad, bloqueos, turnos, ahora)` recibe entidades o dataclasses ya cargadas y devuelve una lista de `Hueco` ordenada. No abre sesión, no consulta y no escribe.

El servicio `enumerar_huecos(...)` es el único que abre un `UnitOfWork` de lectura y:

1. Resuelve el profesional y la prestación con filtro de tenant; exige que existan y estén activos.
2. Carga todas las franjas del profesional para los días que cubre el rango (una consulta).
3. Carga los bloqueos que intersectan el rango y pertenecen al profesional o son globales (una consulta).
4. Carga los turnos no cancelados del profesional que intersectan el rango (una consulta).
5. Invoca el cálculo puro con un `ahora` inyectable.

Ventajas: los casos borde temporales se prueban sin base; las consultas se prueban con PostgreSQL real; no se hace una consulta por hueco candidato.

### 4. Algoritmo de enumeración

Para cada día local del rango:

1. Convertir `desde`/`hasta` a `ZoneInfo(settings.tz)` y trabajar con intervalos semiabiertos.
2. Agrupar las franjas del día ordenadas por `hora_desde`; unir las que comparten borde exacto (`anterior.hora_hasta == siguiente.hora_desde`) para que un hueco pueda cruzar 12:00 sin inventar un descanso.
3. Para cada intervalo unido, anclar un cursor en su inicio y avanzar exactamente `duracion_min` mientras `cursor + duracion_min <= fin_del_intervalo`.
4. Descartar el candidato si `inicio <= ahora` (solo inicio futuro), si intersecta algún bloqueo (`bloqueo.desde < fin and inicio < bloqueo.hasta`) o si intersecta algún turno ocupante con la misma comparación semiabierta.
5. Recortar el resultado al rango solicitado `[desde, hasta)`.
6. Ordenar por `inicio`, `profesional_id`, `prestacion_id` para una respuesta determinista.

La grilla se ancla al inicio de cada intervalo de disponibilidad, no a la medianoche ni a cada minuto. Esto define una enumeración predecible y barata. Un turno creado fuera de la grilla (por ejemplo, 11:45 con paso de 30 minutos) sigue siendo válido para C-07, pero el motor no lo enumera como opción. Es un trade-off aceptado: el turnero ofrece un subconjunto consistente de horarios, no todas las combinaciones matemáticamente posibles.

Los cálculos de fecha/hora usan `datetime.combine(..., tzinfo)` con la zona del consultorio. Argentina no aplica horario de verano; si en el futuro cambia la zona, los horarios locales inexistentes o ambiguos se documentarán en el change que los introduzca.

### 5. Respuesta sin datos de pacientes y con contrato estable

Cada hueco expone únicamente `inicio`, `fin`, `profesional_id` y `prestacion_id`. No se incluye `paciente_id`, nombre, teléfono, documento, observaciones ni el turno ocupante. `Hueco` y la respuesta usan `ConfigDict(extra='forbid')`; las fechas son `AwareDatetime`.

Si el profesional existe pero no tiene disponibilidad en el rango, la respuesta es `200` con lista vacía. Las referencias inexistentes devuelven `404`; las inactivas, `422` con código de agenda. Esto mantiene el cálculo como una consulta, no como una operación de escritura.

### 6. Tenant, autenticación y alcance

El router declara `prefix="/disponibilidad"`, `tags=["agenda"]` y `dependencies=[Depends(require_role(RolUsuario.RECEPCION, RolUsuario.PROFESIONAL))]`. La ruta no está en `RUTAS_PUBLICAS` ni en `PREFIJOS_PUBLICOS`; sin JWT responde `401`.

El alcance reutiliza `profesional_del_alcance(session, usuario, profesional_id)`:

- recepción y dueño: cualquier profesional del tenant;
- profesional sin flag: solo su propio `Profesional` vinculado; otro id devuelve `403 RN-AU-03`.

Todas las consultas del repositorio incluyen `tenant_id == self.tenant_id` de forma explícita, además del filtro automático de `TenantSession` (R3). Las subconsultas de bloqueos y turnos también lo incluyen.

### 7. Performance, índices y ausencia de migración

El cálculo semanal se resuelve con tres consultas de rango y trabajo en memoria. Los índices existentes cubren el acceso:

- turnos: `ix_turno_tenant_profesional_inicio` para `(tenant_id, profesional_id, inicio)`; el filtro `estado <> 'cancelado'` se aplica sobre esas filas;
- bloqueos: `ix_bloqueo_tenant_profesional_desde`;
- disponibilidad: `ix_disponibilidad_tenant_profesional_dia`.

No se agrega migración `0007` porque no hay cambio de esquema. La prueba de performance se ejecutará con una semana representativa y un presupuesto de 1 segundo; si el plan real no lo cumple, se propondrá un change separado (posible índice parcial `(tenant_id, profesional_id, inicio) WHERE estado <> 'cancelado'` o equivalente) con su propia migración, en lugar de inflar C-08.

El rango de una consulta se acota a **31 días** mediante validación de parámetros. Es un límite de seguridad y de coste, no una regla de negocio: el cliente pagina por semanas o por el tramo que necesite. El valor queda como constante documentada y puede ajustarse sin cambiar el contrato de cálculo.

### 8. Errores y validación

| Situación | Resultado |
|---|---|
| Sin JWT | `401` |
| Profesional sin flag pide otro profesional | `403 RN-AU-03`, `reason=fuera_de_alcance` |
| Profesional o prestación inexistente en el tenant | `404 RN-AG-01`, `reason=no_encontrado` |
| Prestación inactiva | `422 RN-AG-01`, `reason=referencia_inactiva` |
| `hasta <= desde`, fechas sin zona o rango > 31 días | `422` de validación de esquema o `RN-AG-01`, `reason=rango_invalido` |

Los parámetros de query se modelan con un schema Pydantic (`extra='forbid'` no aplica a query strings, pero sí la validación de tipos, `AwareDatetime` y el validador de rango). El router usa `Annotated[..., Query(...)]` y una operación HTTP por función, según los estándares del proyecto.

### 9. Estrategia TDD y verificación

- **Unit**: función pura con datos en memoria para grilla, bordes, contiguos, bloqueos y turnos; sin PostgreSQL.
- **Integración**: repositorio y servicio con PostgreSQL real, tenant A/B, referencias ajenas y reloj inyectado.
- **HTTP**: 401/403/404/422, lista vacía, orden, contrato sin PII y compatibilidad de `GET /disponibilidad`.
- **Performance**: semana con datos representativos, medición repetible; se registra el plan o el tiempo, no solo un umbral.
- **Guardas**: la suite de arquitectura sigue verde; `app/domain/agenda` no referencia `Turno`; `app/domain/huecos` no escribe turnos (R4).
- No se toca el frontend ni se agregan dependencias.

## Risks / Trade-offs

- **[La ruta difiere del path literal del roadmap]** → se documenta la reconciliación; C-09 usará el servicio o la subruta, y la ruta pública por slug es distinta. Se actualizará CHANGES al cerrar.
- **[La grilla anclada no enumera todos los inicios válidos para C-07]** → decisión explícita: el motor ofrece un conjunto determinista y barato; C-07 sigue aceptando otros horarios si el cliente los envía. No se promete exhaustividad matemática.
- **[El filtro de bloqueos con `profesional_id IS NULL OR =` puede no usar el índice en tablas grandes]** → el volumen de bloqueos de un consultorio es bajo; se medirá con la prueba semanal. Si hiciera falta, se agrega un índice parcial en un change posterior.
- **[El límite de 31 días puede quedar corto para una vista mensual]** → es una constante ajustable; el cliente pagina. Cambiarlo no altera el algoritmo.
- **[Cambios concurrentes de plantilla, bloqueo o turno durante el cálculo]** → la consulta es de solo lectura y ofrece una foto consistente de lo leído; C-07/C-09 revalidan al reservar. No se bloquean filas ni se promete reserva atómica desde el motor.
- **[Datos de pacientes filtrados por error en la serialización]** → schema de salida mínimo y prueba explícita de ausencia de PII; la guarda de frontera pública se extiende si C-09 expone el resultado.
- **[Entorno de pruebas incorrecto]** → PostgreSQL/Redis aislados, Python 3.12 y `uv run --frozen`; no apuntar al stack manual ni borrar volúmenes de la demo.

## Migration Plan

1. Tras aprobación explícita de implementación, registrar baseline de los tests de agenda, turnos, arquitectura y salud, y confirmar head `0006_turno`.
2. Implementar con ciclos RED → GREEN → TRIANGULATE → REFACTOR; no hay migración ni cambio de datos.
3. Registrar el router nuevo en `create_app()` y verificar OpenAPI, roles y ausencia de rutas públicas.
4. Ejecutar suite completa, guardas de arquitectura/frontera, benchmark semanal, Ruff y `openspec validate --strict`.
5. Rollback de despliegue: quitar el router y el paquete `domain/huecos`; no hay downgrade de base ni datos que revertir. La demo manual no se actualiza sin coordinación.

No hay Open Questions que puedan diferirse sin cambiar el alcance: la ruta, el límite de rango, la grilla y la ausencia de migración quedan resueltos en este documento.
