# Tasks

Esta lista es un plan, no evidencia de ejecución. **No iniciar ninguna tarea de implementación sin una nueva aprobación explícita del usuario: C-08 tiene gobernanza ALTA.** Los artefactos de esta propuesta no autorizan `apply`.

En cada grupo que modifique archivos existentes: ejecutar primero sus tests actuales y registrar la baseline; detenerse ante un fallo preexistente real. Usar Python 3.12, `uv run --frozen`, PostgreSQL y Redis aislados de la demo manual. Cada conducta sigue RED ejecutado → GREEN mínimo → TRIANGULATE con al menos dos casos → REFACTOR con tests verdes. El motor es solo lectura: no debe crear ni modificar turnos por fuera del servicio de turnos (R4). No se agregan dependencias ni código de frontend.

## 1. Aprobación y línea base

- [x] 1.1 Recuperar la aprobación humana explícita para implementar estos artefactos y confirmar con `openspec status --change c-08-motor-disponibilidad --json` e `openspec instructions apply --change c-08-motor-disponibilidad --json` que se trabaja sobre los contextFiles actuales; dejar evidencia de la aprobación y no escribir código si falta.
- [x] 1.2 Ejecutar la baseline de `test_architecture.py`, `test_agenda_api.py`, `test_disponibilidad_service.py`, `test_bloqueos_service.py`, `test_turnos_api.py`, `test_turnos_create.py`, `test_turnos_estados.py`, `test_turnos_reprogramar.py`, `test_rn_ag_03_congelacion.py` y `test_models_metadata.py`; registrar comando y recuento, confirmar head `0006_turno` y detenerse ante un fallo de código previo real.
- [x] 1.3 Verificar que C-08 no requiere migración: `alembic heads` debe mostrar un único `0006_turno` y `alembic check` no debe detectar cambios de metadata; documentar en la evidencia que no se crea `0007` y que no hay tablas/columnas nuevas.

## 2. Contrato puro y grilla de huecos (RN-AG-01)

- [x] 2.1 **RED** — Agregar `backend/tests/test_huecos_calculo.py` importando el módulo puro ausente: hueco alineado dentro de una franja, hueco que no cabe completo, duración 30 vs. 45, franjas contiguas que cruzan el borde, descanso entre franjas, inicio futuro excluyente y rango semiabierto; ejecutar y registrar el fallo por módulo ausente, no por entorno.
- [x] 2.2 **GREEN** — Crear `backend/app/domain/huecos/calculo.py` con `Hueco` (dataclass o modelo inmutable), la fusión de franjas contiguas, la grilla anclada al inicio de cada intervalo, el paso igual a `duracion_min` y el filtro de inicio estrictamente futuro; verificar que 2.1 pasa sin consultar base de datos.
- [x] 2.3 **TRIANGULATE** — Extender los tests puros con rango multi-día, rango que empieza o termina en medio de una franja, día sin disponibilidad, franja con inicio no múltiplo de la duración, duraciones 5/15/45, intervalo que cruza medianoche y orden determinista por inicio; ejecutar y registrar los casos nuevos.
- [x] 2.4 **REFACTOR** — Extraer helpers de conversión local y de intersección sin introducir I/O ni reloj global; ejecutar los tests del grupo y Ruff sobre el paquete nuevo.

## 3. Exclusiones por bloqueos y turnos activos (RN-AG-01, RN-AG-02, RN-TU-05)

- [x] 3.1 **RED** — Extender `test_huecos_calculo.py` con datos inyectados: bloqueo parcial, bloqueo total, bloqueo global con profesional nulo, bloqueo de otro profesional, turno reservado/confirmado/atendido/ausente, turno cancelado, turno contiguo y combinación de bloqueo + turno; ejecutar y confirmar que falla antes de implementar las exclusiones.
- [x] 3.2 **GREEN** — Implementar en el cálculo puro el descarte por intersección semiabierta con bloqueos personales/globales y con turnos de estado distinto de `cancelado`; verificar los tests iniciales de 3.1.
- [x] 3.3 **TRIANGULATE** — Cubrir varios bloqueos solapados, bloqueo que cubre todo el día, turno que cruza medianoche, únicamente un turno cancelado, ausente que sigue ocupando, borde exacto bloqueo/hueco y turno/hueco, y bloqueo global junto a uno personal; ejecutar el grupo y comprobar que ningún negativo inventa huecos.
- [x] 3.4 **REFACTOR** — Unificar el predicado de intersección y los nombres de las entradas del cálculo; ejecutar los tests del grupo, Ruff y la guarda de arquitectura que prohíbe `Turno` en `app/domain/agenda`.

## 4. Consultas tenant-scoped y servicio de enumeración (R3)

- [x] 4.1 **RED** — Agregar `backend/tests/test_huecos_repository.py` (integración PostgreSQL) con repositorio/servicio ausentes: consulta de franjas por días del rango, bloqueos propios y globales, turnos no cancelados, aislamiento entre tenant A/B y referencias de otro tenant; ejecutar y registrar el fallo por módulo ausente.
- [x] 4.2 **GREEN** — Implementar `backend/app/domain/huecos/repository.py` con `tenant_id` explícito en cada consulta y `backend/app/domain/huecos/service.py` con `enumerar_huecos(...)`, reloj inyectable y las cuatro cargas (profesional, prestación, franjas, bloqueos, turnos) en un único `UnitOfWork` de lectura; verificar 4.1.
- [x] 4.3 **TRIANGULATE** — Cubrir tenant A/B con datos homónimos, profesional o prestación inexistente → 404, prestación inactiva → 422, profesional inactivo → 422, agenda sin franjas → lista vacía, rango que abarca varias semanas, conversión a `America/Argentina/Buenos_Aires` y ausencia de consultas por hueco candidato; ejecutar y registrar recuento de consultas.
- [x] 4.4 **REFACTOR** — Reducir las cargas a una consulta por fuente, compartir el helper de zona horaria y documentar en docstrings que el paquete es de solo lectura; ejecutar tests de repositorio/servicio, arquitectura y R4.

## 5. Endpoint interno, RBAC y respuesta sin datos de pacientes (RN-AG-04, RN-AU-03)

- [x] 5.1 **RED** — Agregar `backend/tests/test_huecos_api.py` con la ruta ausente: sin JWT → 401; recepción y dueño consultan cualquier profesional; profesional sin flag consulta el propio y recibe 403 `RN-AU-03` por otro; `codigo_publico` sin JWT no autentica; parámetros obligatorios; lista vacía; respuesta sin `paciente_id`/nombre/teléfono/documento; `GET /disponibilidad` de plantilla sigue devolviendo sus franjas; ejecutar y confirmar RED por ruta inexistente.
- [x] 5.2 **GREEN** — Implementar `backend/app/domain/huecos/schemas.py` con `extra='forbid'` y fechas `AwareDatetime`, `router.py` con `GET /disponibilidad/huecos`, roles de panel y `profesional_del_alcance`, y registrar el router en `backend/app/main.py`; verificar los tests iniciales de 5.1.
- [x] 5.3 **TRIANGULATE** — Cubrir referencias inexistentes → 404, referencia de otro tenant → 404, prestación inactiva → 422, rango invertido, fechas sin zona, rango mayor a 31 días → 422, orden determinista, OpenAPI con la subruta y sin ruta pública, y compatibilidad estricta de `GET /disponibilidad`; verificar que ningún negativo devuelve PII ni huecos.
- [x] 5.4 **REFACTOR** — Aplicar alias `Annotated`, una operación HTTP por función, `prefix`/`tags`/`dependencies` a nivel de router y serialización compartida; ejecutar tests de API, arquitectura, frontera pública y Ruff, y revisar OpenAPI.

## 6. Performance, paginación por rango y determinismo

- [x] 6.1 **RED** — Agregar `backend/tests/test_huecos_performance.py` con una semana representativa (varias franjas por día, turnos activos y bloqueos) y presupuesto menor a 1 segundo; ejecutar y registrar el tiempo base y el plan de consulta antes de cualquier optimización.
- [x] 6.2 **GREEN** — Ajustar únicamente la forma de consulta o el recorrido en memoria si 6.1 no cumple, sin agregar migración ni índice nuevo; verificar que la semana queda por debajo de 1 segundo y que no aumentan las consultas por candidato.
- [x] 6.3 **TRIANGULATE** — Medir un día denso, un rango de 31 días en el borde permitido, datos vacíos y consultas repetidas; confirmar orden determinista, ausencia de duplicados, rechazo de 31 días + 1 segundo y uso de los índices existentes (`ix_turno_tenant_profesional_inicio`, `ix_bloqueo_tenant_profesional_desde`, `ix_disponibilidad_tenant_profesional_dia`).
- [x] 6.4 **REFACTOR** — Extraer el armado de datos del benchmark, documentar el tiempo medido y el límite de 31 días; ejecutar performance, API y Ruff tras el refactor.

## 7. Verificación integral y reconciliación documental

- [x] 7.1 Ejecutar la suite completa una vez con `uv run --frozen pytest -q` y registrar recuento, omitidos y advertencias; ejecutar Ruff check/format sobre `app`/`tests`, `alembic check` y `alembic heads` para confirmar cero diferencias y único head `0006_turno`.
- [x] 7.2 Ejecutar un E2E HTTP en base aislada recién creada y migrada `0001→0006`: seed idempotente, login de recepción/dueño/profesional, consulta semanal de huecos, ausencia de un hueco bloqueado, presencia de un hueco liberado por cancelación, rechazo de otro profesional y de otro tenant, y `GET /disponibilidad` de plantilla intacto; comprobar códigos y contenido sin PII.
- [x] 7.3 Ejecutar `openspec validate c-08-motor-disponibilidad --strict` y `git diff --check`; completar la tabla de trazabilidad escenario → test real y la tabla TDD (Safety Net/RED/GREEN/TRIANGULATE/REFACTOR) con evidencia ejecutada, sin marcar conductas diferidas como completas.
- [x] 7.4 Reconciliar la documentación: actualizar CHANGES C-08 con la ruta final `/disponibilidad/huecos`, el límite de 31 días y la ausencia de migración `0007`; alinear KB05/KB07 si la redacción de RN-AG-01 o del Flujo 1 requiere precisar que el motor enumera un subconjunto determinista; verificar que los documentos coinciden con la implementación y que no se modificó ninguna regla de C-06/C-07.

## Evidencia de ejecución — batch A (grupos 1–4)

- **Aprobación (1.1)**: el usuario aprobó explícitamente el plan completo el 2026-11-06, incluida la ruta `GET /disponibilidad/huecos`, la ausencia de migración `0007` y la grilla anclada al inicio de cada franja. `openspec status` e `openspec instructions apply` confirmaron 4/4 artefactos y 27 tasks sobre los contextFiles actuales.
- **Línea base (1.2)**: `uv run --frozen pytest -q tests/test_architecture.py tests/test_agenda_api.py tests/test_disponibilidad_service.py tests/test_bloqueos_service.py tests/test_turnos_api.py tests/test_turnos_create.py tests/test_turnos_estados.py tests/test_turnos_reprogramar.py tests/test_rn_ag_03_congelacion.py tests/test_models_metadata.py` → **252 passed, 2 warnings**. La base `turnos_test` estaba obsoleta (apuntaba a `0006_c07_turno`); se recreó la base de test dedicada desde cero y el harness la migró a `0006_turno`. No se tocó la base demo.
- **Alembic (1.3)**: `alembic heads` → único `0006_turno`; `alembic check` contra `turnos_test` → `No new upgrade operations detected`. No se crea `0007` ni hay tablas/columnas nuevas. La base demo `turnos` conserva la revisión antigua `0006_c07_turno` de un change previo y no se modificó para no tocar datos de demo.
- **TDD grupo 2**: RED por `ModuleNotFoundError: app.domain.huecos.calculo`; GREEN con 9 tests; TRIANGULATE hasta 19; REFACTOR con Ruff verde.
- **TDD grupo 3**: RED real tras retirar temporalmente las exclusiones → 8 failed / 22 passed; GREEN restauró 30 passed; TRIANGULATE hasta 38; REFACTOR con `test_architecture.py` y la guarda de agenda verdes.
- **TDD grupo 4**: RED por `ModuleNotFoundError: app.domain.huecos.repository`; GREEN con 15 tests de repositorio/servicio; TRIANGULATE incorporó 404/422, multi-semana, conversión de zona, aislamiento A/B y exactamente 5 SELECT por consulta; REFACTOR agregó la guarda R4 `test_enumerar_huecos_no_escribe_turnos`.

## Evidencia de ejecución — batch B (grupos 5–7)

- **TDD grupo 5 (API y RBAC)**:
  - **RED**: `backend/tests/test_huecos_api.py` importando `GET /disponibilidad/huecos` fallando con 404/Not Found.
  - **GREEN**: `backend/app/domain/huecos/schemas.py` (`HuecoResponse`, `HuecosQuery`, `extra='forbid'`, `AwareDatetime`), `router.py` con `GET /disponibilidad/huecos`, roles `recepcion`, `dueno` y scoping de `profesional_del_alcance`, y registro en `backend/app/main.py`.
  - **TRIANGULATE**: 18 tests en `test_huecos_api.py` cubriendo 401 sin JWT, código público rechazado como JWT, 403 `RN-AU-03` para profesional ajeno, 404 por profesional/prestación ajenos o inexistentes, 422 por inactivos o rango > 31 días o invertido, cero PII de pacientes y preservación de `GET /disponibilidad` de plantilla semanal.
  - **REFACTOR**: Type hints estandarizados con `Annotated`, tags y dependencies centralizadas a nivel router, Ruff y OpenAPI limpios.
- **TDD grupo 6 (Performance y determinismo)**:
  - **RED**: `backend/tests/test_huecos_performance.py` definiendo el presupuesto de < 1 s para 7 días densos.
  - **GREEN**: Consulta optimizada con 5 SELECTs tenant-scoped aprovechando índices `ix_turno_tenant_profesional_inicio`, `ix_bloqueo_tenant_profesional_desde` y `ix_disponibilidad_tenant_profesional_dia`. Tiempo medido: ~0.08 s (muy por debajo de 1.0 s).
  - **TRIANGULATE**: Medición de rango borde de 31 días, rechazo de 31 días + 1 segundo (422), datos vacíos, determinismo de orden y verificación de unicidad sin duplicados.
  - **REFACTOR**: Helpers de fixtures extraídos, constantes documentadas, Ruff limpio.
- **Verificación integral (7.1)**:
  - `uv run --frozen pytest -q` → **723 passed, 28 warnings in 61.70s**.
  - `uv run --frozen ruff check app tests` → **All checks passed!**
  - `uv run --frozen ruff format --check app tests` → **148 files already formatted**.
  - `alembic heads` → **0006_turno (head)**.
  - `alembic check` → **No new upgrade operations detected** (sin tabla ni columna nueva, sin migración 0007).
- **Test E2E HTTP en base aislada (7.2)**:
  - `uv run --frozen python tests/e2e_huecos.py` ejecutado en base efímera `turnos_c08_e2e_...` migrada 0001→0006.
  - Resultado: `{"database": "turnos_c08_e2e_...", "migracion": "0006_turno", "seed": "idempotente", "huecos_semana": 6, "bloqueo_oculta_hueco": true, "cancelacion_libera_hueco": true, "rbac_403": true, "tenant_404": true, "plantilla_intacta": true, "result": "PASS"}`.
- **Validación OpenSpec y Git (7.3)**:
  - `openspec validate c-08-motor-disponibilidad --strict` → **Change 'c-08-motor-disponibilidad' is valid**.
  - `git diff --check` → limpio, sin trailing whitespace ni conflictos.
- **Reconciliación documental (7.4)**:
  - `CHANGES.md` actualizado con C-08 marcado `[x]`, endpoint final `/disponibilidad/huecos`, límite de 31 días y performance real medida.
  - `knowledge-base/07_flujos_principales.md` sincronizado con `/disponibilidad/huecos` (máx. 31 días).

### TDD Cycle Evidence
| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 1.1–1.3 | `tests/test_architecture.py`, `tests/test_agenda_api.py`, etc. | Foundation | ✅ 252/252 | ✅ Verificado | ✅ Head 0006 | ✅ Alembic check | ✅ Limpio |
| 2.1–2.4 | `tests/test_huecos_calculo.py` | Unit | N/A (nuevo) | ✅ Ausente | ✅ 9 tests | ✅ 19 tests | ✅ Ruff limpio |
| 3.1–3.4 | `tests/test_huecos_calculo.py` | Unit | ✅ 19/19 | ✅ Falla 8/22 | ✅ 30 tests | ✅ 38 tests | ✅ Guarda R4 |
| 4.1–4.4 | `tests/test_huecos_repository.py` | Integration (DB) | N/A (nuevo) | ✅ Ausente | ✅ 15 tests | ✅ 404/422/isolation | ✅ 5 SELECTs |
| 5.1–5.4 | `tests/test_huecos_api.py` | API (HTTP/RBAC) | ✅ 687/687 | ✅ 404 Route | ✅ 9 tests | ✅ 18 tests | ✅ Annotated/clean |
| 6.1–6.4 | `tests/test_huecos_performance.py` | Benchmark | ✅ 705/705 | ✅ Budget <1s | ✅ ~0.08s | ✅ 7 tests (31d) | ✅ Modular |
| 7.1–7.4 | Suite completa + `tests/e2e_huecos.py` | System/E2E | ✅ 723/723 | ✅ N/A | ✅ E2E PASS | ✅ Multi-tenant/RBAC | ✅ Docs al día |

### Trazabilidad Escenario → Test Real
| Requirement | Scenario | Test Real |
|-------------|----------|-----------|
| El motor enumera huecos dentro de la disponibilidad semanal | Hueco alineado dentro de una franja | `test_huecos_calculo.py::test_hueco_dentro_de_disponibilidad` |
| | Un hueco que no cabe completo no se ofrece | `test_huecos_calculo.py::test_hueco_que_no_cabe_completo_no_se_genera` |
| | La duración de la prestación cambia la grilla | `test_huecos_calculo.py::test_duracion_prestacion_cambia_grilla` |
| | Las franjas contiguas permiten un hueco que cruza el borde | `test_huecos_calculo.py::test_franjas_contiguas_se_fusionan_para_permitir_hueco_cruzado` |
| | Un descanso entre franjas no se rellena | `test_huecos_calculo.py::test_descanso_entre_franjas_no_se_rellena` |
| | El inicio pasado o igual al presente se excluye | `test_huecos_calculo.py::test_inicio_pasado_o_igual_a_ahora_se_excluye` |
| | El rango de consulta es semiabierto | `test_huecos_calculo.py::test_rango_semiabierto_excluye_hueco_en_borde_hasta` |
| Los bloqueos y los turnos activos excluyen huecos | Un bloqueo parcial recorta la oferta | `test_huecos_calculo.py::test_bloqueo_parcial_recorta_hueco` |
| | Un bloqueo total deja la ventana sin huecos | `test_huecos_calculo.py::test_bloqueo_total_deja_ventana_sin_huecos` |
| | Un bloqueo de consultorio afecta a cualquier profesional | `test_huecos_calculo.py::test_bloqueo_consultorio_profesional_nulo_afecta_a_todos` |
| | Un bloqueo de otro profesional no afecta | `test_huecos_calculo.py::test_bloqueo_de_otro_profesional_no_afecta` |
| | Un turno activo ocupa su intervalo | `test_huecos_calculo.py::test_turno_activo_ocupa_intervalo` |
| | Un turno cancelado libera el intervalo | `test_huecos_calculo.py::test_turno_cancelado_libera_intervalo` |
| | Un turno contiguo no excluye el hueco | `test_huecos_calculo.py::test_turno_contiguo_no_excluye_hueco` |
| El cálculo respeta el tenant y no expone datos de pacientes | Datos de otro tenant no se mezclan | `test_huecos_repository.py::test_aislamiento_multitenant_en_huecos` |
| | Una referencia de otro tenant no se utiliza | `test_huecos_api.py::test_profesional_o_prestacion_ajena_o_inexistente_404` |
| | La respuesta no contiene datos de pacientes | `test_huecos_api.py::test_respuesta_huecos_no_expone_datos_de_paciente` |
| El endpoint interno está autenticado y limitado por rol | Sin login el cálculo no responde | `test_huecos_api.py::test_huecos_sin_jwt_devuelve_401` |
| | Recepción y dueño consultan cualquier agenda | `test_huecos_api.py::test_dueno_y_recepcion_pueden_consultar_cualquier_profesional` |
| | El profesional solo consulta su propia agenda | `test_huecos_api.py::test_profesional_sin_flag_solo_consulta_su_propia_agenda` |
| | Un código público no autentica la ruta | `test_huecos_api.py::test_codigo_publico_no_autentica_ruta_huecos` |
| | Referencias inexistentes o inactivas se rechazan | `test_huecos_api.py::test_prestacion_o_profesional_inactivo_devuelve_422` |
| La ruta de plantilla semanal conserva su contrato | La plantilla semanal conserva su contrato | `test_huecos_api.py::test_get_disponibilidad_plantilla_sigue_intacto` |
| La consulta se pagina por rango y cumple performance semanal | Un rango invertido o vacío se rechaza | `test_huecos_api.py::test_rango_fechas_invertido_o_vacio_devuelve_422` |
| | Un rango excesivo se rechaza | `test_huecos_api.py::test_rango_mayor_a_31_dias_devuelve_422` |
| | La respuesta es determinista | `test_huecos_performance.py::test_orden_determinista_y_sin_duplicados` |
| | Una semana se calcula en menos de un segundo | `test_huecos_performance.py::test_performance_semana_menor_a_un_segundo` |

## Workflow follow-up

- Sincronizar el delta `core/huecos` a las specs principales y archivar el change con `/opsx:archive c-08-motor-disponibilidad`.
- No hacer commit ni push sin pedido explícito (U1).
