# Design

## Context

C-02 dejó `Tenant`/`Usuario`, `TenantMixin`/`AuditMixin` en `backend/app/db/models/`, `BaseRepository`/`UnitOfWork` tenant-scoped en `backend/app/domain/persistence.py` y un seed idempotente en `backend/app/db/seed.py`. C-03 dejó `AuthMiddleware`, `get_current_user`, `CurrentUserDep`, `require_dueno` y `require_role` en `backend/app/domain/auth/`, con el guard de arquitectura de `backend/tests/test_architecture.py`. La cabeza de Alembic es `0002_tenancy_usuario` (la numeración de `CHANGES.md` para C-04 dice "002" porque no contaba la migración real de C-02).

Restricciones relevantes:

- `backend/pyproject.toml` declara SQLAlchemy 2 y **no** declara `sqlmodel`; los modelos existentes usan el estilo declarativo (`Mapped`/`mapped_column`). U3 prohíbe instalar dependencias, así que este change mantiene el patrón de C-02 y **no** introduce SQLModel. La guía genérica de SQLModel no aplica a este repositorio.
- R3 obliga a que toda lectura/escritura de dominio pase por la `TenantSession`; el `BaseRepository` ya lo garantiza por construcción.
- R7 obliga a migración por cada cambio de modelo.
- La tabla `turno` todavía no existe (llega en C-07). RN-AG-03 se puede garantizar hoy en el lado del catálogo, pero el extremo a extremo (`fin` congelado) se completa cuando C-07 cree el turno.
- C-05 y C-06 se proponen en paralelo y también tocan `seed.py`, `main.py` y crean migraciones.

Ver `proposal.md` §Por qué y las specs `core/profesionales`, `core/prestaciones` y el delta de `core/tenancy` para el contrato de comportamiento.

## Goals / Non-Goals

**Goals:**

- Modelos `Profesional` y `Prestacion` listos para que C-07 los referencie por FK sin re-decidir convenciones.
- CRUD dueño-only mínimo y consistente con el contrato RBAC de C-03.
- Garantía verificable de que editar `duracion_min` no toca nada más que la fila de la prestación.
- Seed demo que no falle según el orden en que se archiven C-04/C-05/C-06.

**Non-Goals:**

- Tabla `Turno`, cálculo de huecos y validación de anti-solape (C-07/C-08).
- Disponibilidad y bloqueos: C-04 solo siembra filas demo si la tabla ya existe; el CRUD es de C-06.
- Alta/baja de usuarios, roles o login (C-03/C-12).
- Precios, obras sociales, facturación o cualquier cálculo monetario (post-MVP). `precio_ref` es solo un dato informativo.
- Borrado físico, soft delete formal o auditoría de cambios (DD-07/IN-01).

## Decisions

- **Modelos de catálogo en `backend/app/db/models/` y dominio en `backend/app/domain/agenda/`.** `profesional.py` y `prestacion.py` viven junto a `tenant.py`/`usuario.py` y se importan en `app/db/models/__init__.py` para que `Base.metadata` esté completo en Alembic (mismo criterio que C-02). El código HTTP/servicio va en `app/domain/agenda/profesionales/` y `app/domain/agenda/prestaciones/`, respetando la estructura de `08_arquitectura_propuesta.md` (`domain/agenda/` agrupa profesionales, prestaciones, disponibilidad y bloqueos) y dejando subpaquetes separados para que C-06 agregue `disponibilidad/`/`bloqueos/` sin reescribir los de C-04. Alternativa descartada: `app/domain/profesionales/` y `app/domain/prestaciones/` sueltos — se aparta de la KB y duplica la noción de "agenda".

- **`Profesional.usuario_id` nullable con unicidad global y validación de vínculo en servicio.** El `UniqueConstraint("usuario_id")` es global porque `usuario.id` es global; un usuario no puede ser dos profesionales en ningún tenant. La FK de Postgres no puede verificar que el usuario sea del mismo tenant ni que tenga `rol = profesional`, así que el servicio resuelve el `Usuario` con la `TenantSession` (que ya filtra por tenant): si no aparece, se trata como inexistente (404); si aparece pero es `recepcion`, se rechaza con 422. Fundamento: mantiene la integridad sin triggers ni constraints cruzadas, y reutiliza el aislamiento de C-02. Alternativa descartada: `UniqueConstraint("tenant_id", "usuario_id")` — permitiría el mismo usuario en dos tenants, que es precisamente el dato inválido a evitar. Alternativa descartada: trigger `BEFORE INSERT/UPDATE` en Postgres — duplica la regla y complica el seed.

- **`duracion_min` validada en dominio y en la base; el error de dominio usa `RN-AG-03`.** La migración crea `CHECK (duracion_min > 0 AND duracion_min % 5 = 0)`; el servicio valida antes de escribir y lanza `DomainError("RN-AG-03", ..., status_code=422)` para que la respuesta tenga el sobre `{code, message, details}` que exige RN-GL-01. No se usa `Field(gt=0)`/`Field(multiple_of=5)` porque FastAPI devolvería un 422 con `detail` de Pydantic sin `code`, y el criterio de aceptación pide `RN-AG-03`. La violación del CHECK (por ejemplo, un seed o SQL manual) se captura como `IntegrityError` y se traduce al mismo error. Alternativa descartada: handler global de `RequestValidationError` — afecta a toda la API y excede el alcance. Nota: la KB define `RN-AG-03` como "cambiar la duración no altera turnos"; `CHANGES.md` pide ese código también para la duración inválida, así que se usa como el código del contrato de duración (ver §Preguntas abiertas).

- **RN-AG-03 se garantiza en C-04 como invariante de catálogo y se completa en C-07 como invariante de turno.** En C-04: (a) el `PATCH` de prestación escribe únicamente esa fila; (b) la migración no declara `onupdate`/`ondelete` CASCADE en las FKs del catálogo; (c) `app/domain/agenda` no importa ni escribe `Turno` (guard de arquitectura); (d) un test toma una foto de las filas de todas las tablas de dominio antes y después del `PATCH` y verifica que solo cambió `prestacion`. El contrato hacia C-07 queda explícito: al crear un turno, `fin = inicio + duracion_min` con la duración vigente en ese instante; el turno persiste ambos extremos y nunca recalcula `fin` al leer la prestación, aunque su `duracion_min` cambie después (el `PATCH` de catálogo no toca turnos). Alternativa descartada: crear ya una tabla `turno` mínima en C-04 para probar el congelamiento — invade el alcance CRÍTICO de C-07 y duplicaría su máquina de estados.

- **`precio_ref` como `Numeric(12,2)` nullable con `CHECK >= 0`.** Se mapea a `Decimal` en el ORM y a `Decimal` en Pydantic (nunca `float`, para no arrastrar errores de redondeo). Es informativo: el servicio de turnos de C-07 no lo lee y ninguna respuesta de agenda lo usa para calcular nada. Alternativa descartada: `String` — no permite validar rango ni ordenar; `float` — impreciso para moneda.

- **Endpoints dueño-only declarados en el `APIRouter`, no en `include_router()`.** `APIRouter(prefix="/profesionales", tags=["profesionales"], dependencies=[Depends(require_dueno)])` y el equivalente para `/prestaciones`. Así el guard de `test_architecture.py` detecta `__rbac_roles__`/`__rbac_dueno__` en el árbol de dependencias y ninguna ruta queda sin protección. Los endpoints usan `CurrentUserDep` solo cuando necesitan la identidad; para el resto alcanza la dependencia del router. Alternativa descartada: `dependencies=` en `include_router()` — el guard actual no lo inspecciona y la ruta podría quedar marcada como insegura.

- **Schemas separados `Create`/`Update`/`Out`, todos con `extra='forbid'` (R1).** `Update` es todo opcional y el servicio aplica solo `model_dump(exclude_unset=True)`; un `PATCH` con `{}` es un no-op válido y no borra campos. `Out` expone `id`, `tenant_id`, `usuario_id`, `nombre`, `matricula`, `especialidad`, `activo`, `creado_en`, `actualizado_en` (y el equivalente de prestación), nunca objetos ORM crudos. `nombre` se normaliza con `strip()` y no puede quedar vacío. Alternativa descartada: un único schema para crear y editar — permite pisar campos no enviados y complica la validación de duración.

- **Listados deterministas y filtro booleano opcional.** `GET /profesionales?activo=true|false` y `GET /prestaciones?activa=true|false`, ordenados por `nombre` ascendente. Fundamento: el panel y los tests necesitan orden estable; el filtro cubre el caso "solo activos" que consumirán C-07/C-08 sin agregar endpoints. Alternativa descartada: paginación — el catálogo de un consultorio es chico y `CHANGES.md` no la pide.

- **Desactivación explícita solo para prestaciones; el profesional se desactiva por `PATCH`.** `POST /prestaciones/{id}/desactivar` es idempotente y devuelve la prestación actualizada; para profesionales el `PATCH` con `activo=false` alcanza y evita duplicar la operación. Ninguno de los dos expone `DELETE`. Fundamento: sigue literalmente el scope de `CHANGES.md` y mantiene el historial de turnos. Alternativa descartada: `DELETE` con soft delete — R9/DD-07 no lo piden y complica la semántica de FKs.

- **404 de dominio con `RN-GL-01` y `details.reason = "no_encontrado"`; vínculo inválido con `RN-GL-01` y razón específica.** La KB no define un código para "recurso inexistente" ni para "usuario no vinculable"; inventar `RN-AG-05/06` cambiaría la KB fuera de alcance. Se usa el sobre de RN-GL-01 con una razón distinguible (`no_encontrado`, `usuario_ya_vinculado`, `usuario_no_vinculable`) y 404/409/422 según el caso. Un recurso de otro tenant se responde 404, igual que uno inexistente, para no filtrar la existencia de datos ajenos. Alternativa descartada: devolver 500 o dejar que la excepción de unicidad de Postgres escape — viola RN-GL-01.

- **Seed condicionado a C-06 con introspección de tabla y SQL idempotente.** El seed de C-04 crea el `Profesional` demo vinculado a `dueno@demo` y las cinco prestaciones base (get-or-create por `usuario_id`/`nombre`). Para disponibilidad, `app/db/seed.py` consulta `sqlalchemy.inspect(engine).has_table("disponibilidad")`: si existe, inserta Lun–Vie 9–13 y 16–20 para el profesional demo con `INSERT ... SELECT ... WHERE NOT EXISTS` (clave lógica: profesional + día + rango); si no existe, omite el bloque y lo informa en el resultado del seed sin fallar. Se usa SQL crudo a propósito porque el modelo de C-06 puede no existir todavía y el seed debe compilar en cualquier orden de archivo; `seed.py` vive en `app/db/` y queda fuera del guard de SQL crudo, que solo escanea `app/domain`. El `tenant_id` va explícito en cada fila. Alternativa descartada: importar los modelos de C-06 — `ImportError` si C-04 se archiva primero. Alternativa descartada: crear la tabla de disponibilidad en C-04 — pisa la migración de C-06.

- **Migración `0003_c04_profesional_prestacion`, con `down_revision = "0002_tenancy_usuario"`.** El id incluye `c04` para no colisionar con los ids que generen C-05/C-06 en paralelo. `downgrade` elimina índices, constraints y tablas en orden inverso. Alternativa descartada: numerar `0003` a secas — dos agentes podrían producir ids iguales y romper Alembic con "duplicate revision". Ver §Riesgos por las múltiples cabezas.

- **Tests de integración contra Postgres real, reutilizando el harness de C-02 y `auth_helpers` de C-03.** Se agregan helpers a `backend/tests/factories.py` (`crear_profesional`, `crear_prestacion`) y se usa `app_de_prueba()`/`login()` de `tests/auth_helpers.py` para obtener tokens reales. Los tests de modelos/constraints van sin HTTP; los de router usan `TestClient`. Fundamento: `CHECK`, `NUMERIC`, índices y FKs no existen en SQLite y el aislamiento ya se prueba contra Postgres en C-02.

## Risks / Trade-offs

- [Riesgo] **Múltiples cabezas Alembic por el paralelismo de C-04/C-05/C-06**: C-04 propone `0003_c04_profesional_prestacion` y C-05 propone `0003_paciente`, ambas con `down_revision = "0002_tenancy_usuario"`; C-06 espera encadenar sobre `0004_*`, que con esos dos ids no existirá. Resultado: tres heads y un salto de numeración. → Mitigación: ids con prefijo del change, verificación `alembic heads` en el bloque final y, en GATE 4, `alembic merge -m "merge catalogo/pacientes/disponibilidad" heads` (o reencadenar `down_revision`) antes de C-07. El orden es indiferente entre C-04 y C-05 porque son aditivas; la de C-06 debe quedar después de C-04 por su FK a `profesional`.
- [Riesgo] **C-06 declara el seed de disponibilidad como responsabilidad de C-04 y no lo duplica**: si C-04 se implementa y ejecuta el seed antes de que exista la tabla `disponibilidad`, las filas demo no quedan sembradas en esa corrida. → Mitigación: el seed de C-04 es idempotente y condicional; al reejecutarlo después de aplicar C-06 inserta las filas (la verificación de C-06 las exige). Se documenta que la corrida de seed posterior a las migraciones de GATE 4 es obligatoria.
- [Riesgo] **Colisión de helpers de test**: C-04 agrega `crear_profesional`/`crear_prestacion` a `backend/tests/factories.py`, mientras C-06 planea `backend/tests/agenda_factories.py` con su propio `crear_profesional`. → Mitigación: al integrar, una sola definición debe sobrevivir (se propone que `factories.py` sea la fuente y `agenda_factories.py` importe de ahí); se detecta porque la suite falla por import duplicado o divergencia de firma.
- [Riesgo] **C-06 necesita la tabla `profesional` de C-04**: si C-06 se aplica antes que C-04, su FK a `profesional` falla. → Mitigación: C-06 ya declara en `CHANGES.md` que usa el contrato de `04_modelo_de_datos.md` si C-04 no está archivado; el merge de GATE 4 debe ordenar `0003_c04` antes de la migración de disponibilidad (o declarar `depends_on`). Se documenta como paso obligatorio del gate.
- [Riesgo] **Conflictos de merge en `seed.py`, `main.py` y el delta de `core/tenancy`** con C-05/C-06. → Mitigación: funciones de seed separadas por entidad (`_sembrar_catalogo`), registro de routers en líneas independientes, y un delta de `core/tenancy` redactado de forma extensible (no enumera taxativamente las entidades sembradas) para que C-05/C-06 puedan sumar sus filas sin reescribir el requisito.
- [Riesgo] **La FK `usuario_id` no impide cruzar tenants ni vincular recepción** a nivel DB. → Mitigación: validación en servicio con la `TenantSession` (un usuario de otro tenant no se ve y responde 404; recepción responde 422) y test dedicado para ambos casos. Se acepta la ventana de un seed/SQL manual que esquive el servicio.
- [Riesgo] **`duracion_min` cambia mientras C-07 está en vuelo** y el turno aún no existe. → Mitigación: C-04 no expone ninguna operación que toque turnos, no declara cascadas y deja el contrato escrito para C-07 (`fin` calculado al crear y nunca derivado al leer). El test de congelamiento end-to-end se suma en C-07.
- [Riesgo] **Una prestación desactivada sigue referenciada por turnos históricos**. → Mitigación: `activa=false` no borra la fila y el `Out` la sigue devolviendo; C-07/C-08 deben ofrecer solo prestaciones activas para turnos nuevos (contrato anotado en design y en tasks).
- [Riesgo] **El seed de disponibilidad con SQL crudo esquiva el filtro automático de tenant**. → Mitigación: `tenant_id` explícito en cada fila, `WHERE NOT EXISTS` por clave lógica, y ejecución acotada al seed de infraestructura (`app/db/seed.py`), nunca al dominio.
- [Riesgo] **`RN-AG-03` se usa para dos conceptos** (duración inválida y congelamiento). → Mitigación: se documenta en §Preguntas abiertas y se mantiene el `details.reason` distinguible (`duracion_invalida` vs. el contrato de turno); si el equipo quiere separar códigos, se puede agregar `RN-AG-05` sin romper el contrato HTTP.
- [Riesgo] **Cambiar el catálogo mientras un turno se está reservando** (C-07) podría leer una duración distinta a la usada para validar el hueco. → Mitigación: C-07 debe resolver la prestación dentro de la misma transacción de reserva (`UnitOfWork`); C-04 no agrega estado intermedio y RN-GL-02 se mantiene.

## Plan de migración

1. `alembic upgrade head` aplica `0003_c04_profesional_prestacion` (tablas `profesional` y `prestacion`, FKs, CHECK de duración, unicidad de `usuario_id`, índices `(tenant_id, activo)` y `(tenant_id, activa)`).
2. `python -m app.db.seed` crea el profesional demo y las cinco prestaciones; si la tabla `disponibilidad` existe, siembra la plantilla Lun–Vie 9–13/16–20. Es idempotente y seguro de repetir.
3. Verificación: `alembic check` sin diferencias, `alembic heads` con una sola cabeza (o merge documentado en GATE 4), y smoke con `GET /prestaciones` como `dueno@demo` → 200 con las cinco prestaciones.
4. Rollback: `alembic downgrade 0002_tenancy_usuario` elimina índices, constraints y tablas `prestacion`/`profesional`. Es destructivo y aceptable porque v1 no tiene datos productivos; el seed se puede recrear. Si C-06 ya creó `disponibilidad` con FK a `profesional`, el downgrade debe hacerse en orden inverso (primero C-06) o con el merge de GATE 4.

## Preguntas abiertas

- **Códigos de error dedicados.** La KB solo define `RN-AG-01..04`. Se propone evaluar `RN-AG-05` (recurso de catálogo no encontrado) y `RN-AG-06` (vínculo usuario-profesional inválido) para no reutilizar `RN-GL-01`; mientras no se apruebe, se mantiene `RN-GL-01` + `details.reason`.
- **Unicidad de nombre en prestaciones.** La KB no exige `nombre` único por tenant; el seed usa el nombre como clave lógica. Si el piloto pide evitar duplicados ("Consulta" dos veces), se puede agregar `UniqueConstraint(tenant_id, nombre)` en un change posterior.
- **Dueño del seed de disponibilidad.** C-04 siembra filas de disponibilidad si la tabla existe y C-06 podría sembrarlas también. La clave lógica (profesional + día + rango) hace que ambas ejecuciones sean idempotentes; se recomienda que C-06 sea la dueña final del seed y que C-04 solo lo cubra cuando C-06 todavía no exista.
