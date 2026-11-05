# Tasks

Esta lista es un plan, no evidencia de ejecución. **No iniciar ninguna tarea de implementación sin una nueva aprobación explícita del usuario: C-07 tiene gobernanza CRÍTICA.** Los artefactos de esta propuesta no autorizan `apply`.

En cada grupo que modifique archivos existentes: ejecutar primero sus tests actuales y registrar la baseline; detenerse ante un fallo preexistente real. Usar Python 3.12, `uv run --frozen`, PostgreSQL y Redis aislados, base literal `turnos_test` en el servidor exclusivo de pruebas. Nunca apuntar el harness al stack manual. Cada conducta sigue RED ejecutado → GREEN mínimo → TRIANGULATE con al menos dos casos → REFACTOR con tests verdes. Las escrituras de negocio, incluido el seed, pasan por el servicio de turnos; las pruebas adversariales de constraints pueden intentar SQL directamente en la base aislada para demostrar el rechazo de la DB.

## 1. Aprobación y línea base

- [x] 1.1 Recuperar la aprobación humana explícita para implementar estos artefactos y confirmar con `openspec status --change c-07-turnos-state-machine --json` e `openspec instructions apply --change c-07-turnos-state-machine --json` que se trabaja sobre los contextFiles actuales; dejar evidencia de la aprobación y no escribir código si falta.
- [x] 1.2 Ejecutar la baseline de `test_architecture.py`, `test_models_metadata.py`, `test_rn_ag_03_congelacion.py`, `test_pacientes_scope.py`, `test_pacientes_search.py`, `test_pacientes_create.py`, `test_pacientes_reuse.py`, `test_pacientes_delete_policy.py`, `test_seed.py`, `test_seed_catalogo.py`, `test_pacientes_seed.py` y `test_agenda_seed_contract.py`; registrar recuento y comando, confirmar head `0005_disponibilidad_bloqueo` y detenerse si hay un fallo de código previo. Los 409 tests de C-06 son referencia histórica, no sustituyen esta ejecución.

## 2. Modelo, código y migración (RN-TU-01, RN-TU-02)

- [x] 2.1 **RED** — Agregar `tests/test_turnos_model.py` y `tests/test_turnos_codigos.py`: importar el modelo/generador ausentes y describir tenant/audit, FKs RESTRICT, fechas aware, índices, código de 12 caracteres y 9 bytes de origen. Ejecutarlos y registrar el fallo por el código ausente, no por el entorno.
- [x] 2.2 **GREEN** — Implementar `app/db/models/turno.py`, su export, `app/domain/turnos/codigos.py` y revisión `0006_turno` sobre `0005_disponibilidad_bloqueo`, con enum, CHECKs, unique y EXCLUDE `tstzrange(...,'[)')`, extensión compartida `btree_gist`. Verificar los tests iniciales y `uv run --frozen alembic upgrade head` en la base aislada.
- [x] 2.3 **TRIANGULATE** — Extender tests con upgrade desde una base vacía y desde C-06, downgrade/upgrade sin borrar tablas anteriores, CHECK fin/flag-motivo, introspección EXCLUDE/índices, contiguos válidos y rechazo DB de solape en reservado/confirmado/atendido/ausente frente a cancelado. Incluir distintos profesionales y tenants; ejecutar los tests y `alembic check` sin diferencias.
- [x] 2.4 **REFACTOR** — Consolidar nombres de constraints/enum y documentar en KB04 el tipo `tstzrange`, el motivo de sobreturno y la duración congelada; verificar tests del grupo, Ruff y un único head `0006_turno`. No agregar SQL crudo al dominio ni referencias a Turno dentro de `app/domain/agenda`.

## 3. Creación y validación del candidato (RN-AG-01, RN-AG-02, RN-TU-03)

- [x] 3.1 **RED** — Agregar `tests/turnos_factories.py` para datos de catálogo/plantilla y `tests/test_turnos_create.py` con el servicio ausente: alta normal futura calcula fin y nace reservada; un intervalo que termina fuera de plantilla se rechaza; sobreturno explícito fuera de plantilla nace confirmado. Ejecutar y comprobar el fallo esperado antes del servicio.
- [x] 3.2 **GREEN** — Implementar esquemas con `extra='forbid'`, repositorio tenant-scoped y creación en un solo UoW: referencias del tenant/activas, reloj inyectable, unión de franjas contiguas, cobertura completa, bloqueos globales/personales, ocupación y motivo de urgencia. Usar `motivo_sobreturno` persistido. Confirmar los tests iniciales y que no se aceptan fin/estado/código/tenant del cliente.
- [x] 3.3 **TRIANGULATE** — Cubrir todos los escenarios de creación/sobreturno: inicio pasado/igual al presente, offsets equivalentes, segmentos que cruzan medianoche, franjas contiguas y con descanso, bloqueo global/personal/de otro profesional, contención parcial, flag sin motivo, motivo sin flag, catálogo inactivo y referencias de otro tenant. Confirmar códigos/status y ausencia de escrituras en cada rechazo con los tests del grupo.
- [x] 3.4 **RED → GREEN concurrente** — Agregar y ejecutar primero un test de dos conexiones/transacciones con barrera que supere ambas consultas previas y fuerce el EXCLUDE; implementar solo la traducción del constraint nombrado a 409 `RN-TU-01`. Agregar un segundo caso con intervalos contiguos/diferente profesional y comprobar un único ganador en el conflicto, sin PII del turno ocupante.
- [x] 3.5 **TRIANGULATE / REFACTOR** — Probar colisión de código seguida de éxito y agotamiento de cinco intentos con savepoints y cero filas parciales; no tratar otras violaciones como colisión/solape. Unificar validadores y documentar en KB05/KB07 que la urgencia omite solo plantilla, no bloqueos ni ocupación. Ejecutar tests del grupo y Ruff tras cada refactor.

## 4. Máquina de estados y cancelación (RN-TU-04, RN-TU-05)

- [x] 4.1 **RED** — Agregar `tests/test_turnos_estados.py` para máquina ausente y servicio de transición: reservado→confirmado y confirmado→atendido válidos; reservado→atendido inválido; cancelar conserva fila/motivo. Ejecutar y confirmar RED antes de producción.
- [x] 4.2 **GREEN** — Implementar máquina pura y servicio que bloquea la fila con `FOR UPDATE`, evalúa alcance/estado actual y transiciona en el mismo UoW. Verificar que las transiciones iniciales pasan sin modificar horario/código/referencias y los inválidos devuelven 422 `RN-TU-04`.
- [x] 4.3 **TRIANGULATE** — Parametrizar las 25 combinaciones origen/destino: cinco válidas y veinte rechazadas, incluidas repeticiones y terminales. Cubrir motivo opcional de cancelación, cancelado libera/ausente ocupa y dos transiciones concurrentes del mismo turno que se evalúan contra el estado persistido. Confirmar por snapshot que cada rechazo deja la fila intacta.
- [x] 4.4 **REFACTOR** — Centralizar aristas/errores y documentar la acción de atención y la conservación del registro en KB02/KB05/KB06. Ejecutar tests del grupo, creación/anti-solape y Ruff después del refactor; la creación y transición continúan únicamente en el servicio.

## 5. Reprogramación con identidad y duración conservadas (RN-TU-07)

- [x] 5.1 **RED** — Agregar `tests/test_turnos_reprogramar.py` con operación ausente: mover un reservado conserva id/código/estado/duración; destino ocupado revierte todo. Ejecutar primero y registrar RED.
- [x] 5.2 **GREEN** — Implementar reprogramar bajo `FOR UPDATE` con `nuevo_fin = nuevo_inicio + (fin - inicio)`, validación común que excluye el id propio y un único UoW. Confirmar los tests iniciales sin crear/cancelar filas ni recalcular duración desde el catálogo.
- [x] 5.3 **TRIANGULATE** — Cubrir reservado/confirmado, prestación cuya duración cambió, intervalo nuevo que intersecta solo al propio, fuera de plantilla, bloqueos, sobreturno fuera de plantilla válido, los tres terminales y una carrera real reserva vs reprogramación. Verificar con snapshots que todo rechazo conserva el turno original y no deja filas nuevas.
- [x] 5.4 **REFACTOR** — Compartir validación del candidato sin convertirla en enumeración de huecos; reconciliar KB05 RN-TU-07 y KB07 Flujo3 con la decisión explícita del usuario (mismo id/código/estado/duración). Ejecutar tests del grupo, creación y estados tras el refactor, más Ruff.

## 6. Alcance asistencial del paciente (RN-AU-03)

- [x] 6.1 **RED** — Agregar `tests/test_pacientes_turnos_scope.py`: un paciente de recepción con turno reservado/confirmado del profesional se lee/edita y aparece en lista/búsqueda; un paciente con solo cancelado/ausente no. Ejecutar contra el alcance actual por creador y confirmar el fallo antes de modificarlo; preservar tests existentes del creador.
- [x] 6.2 **GREEN** — Implementar un predicado SQL tenant-scoped compartido de creador OR EXISTS turno reservado/confirmado/atendido con el profesional vinculado. Adaptar lectura/edición, listado/búsqueda, duplicados y reutilización PROPIOS y sus firmas/call sites usando la misma sesión, sin modificar roles/JWT ni la rama pública TODOS/usuario_id=None. Confirmar los tests iniciales.
- [x] 6.3 **TRIANGULATE** — Cubrir cancelación de la única cita revoca, atención previa mantiene, otro turno activo mantiene, ausencia sola no, creador conserva sin turnos, profesional sin vínculo conserva solo creados, turnos de otro profesional/tenant no conceden, y advertencias/reutilización usan idéntico alcance. Verificar lectura/edición 403 y ausencia de PII en listado/búsqueda/advertencias en cada negativo.
- [x] 6.4 **REFACTOR** — Eliminar comparaciones de pertenencia divergentes y documentar el criterio aprobado en KB03/KB05 y el alcance del cambio en la ficha. Ejecutar todos los tests de pacientes previos y nuevos, guards de frontera pública y Ruff después del refactor; conservar respuestas 404/403 existentes.

## 7. API interna y edición restringida

- [x] 7.1 **RED** — Agregar `tests/test_turnos_api.py` para POST/GET/PATCH/acciones ausentes: alta 201, sin token 401, listado propio, estado por PATCH y POST con resultados equivalentes, reprogramación conserva identidad. Ejecutar y confirmar RED por rutas inexistentes antes de registrarlas.
- [x] 7.2 **GREEN** — Implementar router con roles explícitos, esquemas de salida sin ficha incrustada y acciones confirmar/atender/cancelar/registrar-ausencia/reprogramar; registrar en `app/main.py`. PATCH solo acepta estado y motivo de cancelación coherente; reprogramar solo nuevo_inicio. Confirmar los tests iniciales, sin agregar DELETE ni rutas públicas.
- [x] 7.3 **TRIANGULATE** — Cubrir recepción/dueño todos, profesional propio, profesional sin vínculo 403, profesional que intenta autoasignarse una ficha ajena 403, otro tenant 404, campos extra/fin/referencias editadas 422, PATCH vacío 422, motivo con destino no cancelado 422, acciones con campos inesperados 422 y DELETE rechazado. Ejecutar tests de API y validar que los negativos no cambian filas.
- [x] 7.4 **TRIANGULATE** — Cubrir filtros combinados, rango `[desde,hasta)`, orden estable inicio/id, limit/offset y valores inválidos; verificar que código sin JWT no autentica. Extender la guarda R4/frontera pública con casos falsos que detecten escritura de Turno fuera del servicio y una exposición pública; confirmar que la app real pasa y la guarda de catálogo no se debilita.
- [x] 7.5 **REFACTOR** — Extraer alias/serialización compartidos conservando una operación HTTP por función. Reconciliar KB02 y CHANGES C-07 con PATCH restringido, POST atender, ausencia de DELETE y revisión real 0006. Ejecutar tests de API, arquitectura/frontera pública y Ruff, y verificar OpenAPI con las rutas/esquemas previstos.

## 8. Seed e integración de duración congelada

- [x] 8.1 **RED** — Agregar `tests/test_turnos_seed.py`: primer seed crea tres ejemplos reservado/confirmado/atendido, segundo no cambia ids/códigos/fechas, y no pisa un ejemplo que el usuario canceló o reprogramó. Ejecutar contra el seed previo y confirmar fallo por ejemplos ausentes.
- [x] 8.2 **GREEN** — Ampliar seed vía servicio de turnos con identificadores deterministas internos y datos solo mock; crear ejemplos no superpuestos usando disponibilidad demo y transiciones permitidas. Confirmar tests iniciales y que ninguna ruta HTTP acepta identificadores/códigos del seed.
- [x] 8.3 **TRIANGULATE** — Cubrir aislamiento por tenant, ejemplos con catálogo ajustado/inactivo sin forzar reglas, nombres/teléfonos ficticios, tres intervalos no superpuestos e idempotencia tras una modificación manual. Completar `test_rn_ag_03_congelacion.py` con turnos reales: cambiar duración/precio no toca turnos y reprogramar mantiene duración original. Ejecutar esos tests más los seeds previos y el contrato de aislamiento del seed C-04.
- [x] 8.4 **REFACTOR** — Compartir el camino de escritura sin introducir flags de bypass en payloads públicos; actualizar KB04 seed/entidad y docstrings del seed/servicio. Ejecutar tests seed, congelación, R4 y Ruff tras el refactor; documentar omisiones controladas cuando un ejemplo nuevo no puede reservarse sin violar reglas.

## 9. Verificación integral y entrega

- [x] 9.1 Ejecutar la suite completa una vez sobre el entorno correcto con `uv run --frozen pytest -q`, sin omitir integración; comprobar cero fallos y registrar recuento/advertencias. Ejecutar Ruff check y format check sobre app/tests, `alembic check` después de la suite y `alembic heads`: cero diferencias y único head `0006_turno`.
- [x] 9.2 Ejecutar un E2E HTTP en base aislada recién creada y migrada 0001→0006: seed idempotente, login de tres roles, reserva, sobreturno, 409 concurrente, transiciones válidas/inválidas, reprogramación con rollback y alcance de ficha revocado al cancelar. Comprobar códigos, estados y contenido final de DB; conservar intacta la demo manual y sus volúmenes.
- [x] 9.3 Ejecutar `openspec validate c-07-turnos-state-machine --strict` y `git diff --check`; revisar trazabilidad de cada escenario a un test real y completar tabla TDD (Safety Net/RED/GREEN/TRIANGULATE/REFACTOR) con evidencia ejecutada, sin marcar conductas diferidas como completas.
- [x] 9.4 Presentar el resultado para revisión, sincronizar deltas y archivar C-07 mediante el flujo de cierre autorizado solo si todas las reglas críticas están verdes; actualizar CHANGES y verificar main specs estrictas/OpenSpec list. No hacer commit ni push sin pedido explícito y no actualizar el stack manual sin coordinar con el usuario.

## Evidencia ejecutada (apply)

- Aprobación crítica: usuario «continua con el apply» después de revisar la propuesta; CLI ready 0/36, cuatro artefactos completos.
- Runtime: Python 3.12, `uv run --frozen`, PostgreSQL y Redis exclusivos c06-tests reutilizados; DATABASE_URL principal turnos, harness turnos_test. Demo 18000/15173 intacta.
- 1.2 baseline requerida: 88 passed, 2 deprecaciones, 65.06s (architecture/models_metadata/congelacion/pacientes scope-search-create-reuse-delete/seed/catalogo/pacientes_seed/agenda_seed_contract).
- 2.1 RED: ImportError Turno y ModuleNotFoundError turnos.codigos. 2.2 GREEN: 4 passed, incluye tabla/EXCLUDE real PostgreSQL.
- 2.3 triangulación: 22 passed; constraints, cinco estados ocupantes/cancelado, contiguos, distintos profesionales/tenants, FKs RESTRICT y upgrade vacío/C06/downgrade preservando catálogo.
- 2.4 refactor: 22 passed; Ruff check/format correctos; Alembic check sin operaciones, único head 0006_turno. Warning previo de comparación del índice trigram de pacientes permanece sin ampliar scope.
- 3.1 RED: ModuleNotFoundError turnos.schemas antes de implementar creación.

- 3.2 GREEN: 3 passed (normal/fin fuera plantilla/urgencia). 3.3 triangulación: 35 passed (tiempo/offsets/franjas/bloqueos/referencias/validación).
- 3.4 RED real: dos conexiones con barrera superan ambas consultas, falla con error DB no traducido. PostgreSQL además reproduce DeadlockDetected 40P01 al comprobar EXCLUDE; retry del UoW completo limitado a 3, solo ese SQLSTATE. GREEN con carrera real y contiguos: 2 passed.
- 3.5 RED colisión: UniqueViolation uq_turno_codigo_publico; GREEN con savepoints y cinco intentos. Refactor+triangulación de otras excepciones/limites: 42 passed, Ruff check/format verdes. Ningún OperationalError genérico se convierte en conflicto.

- 4.1 RED: ModuleNotFoundError turnos.estados antes de máquina/transición. 4.2 GREEN: 28 passed (25 pares puros + integración).
- 4.3 triangulación: 59 passed; 25 pares persistidos con snapshots intactos en rechazo, motivos opcionales, cancelado libera/ausente ocupa, dos conexiones con FOR UPDATE y estado persistido observado.
- 4.4 refactor: 101 passed (estados+creación+concurrencia), Ruff correcto; KB02/05/06 alineadas con atención, no DELETE y conservación de fila.
- 5.1 RED: ImportError reprogramar ausente antes de implementar operación.

- 5.2 GREEN: 2 passed (identidad/duración y rollback destino ocupado). 5.3 triangulación: 14 passed; estados reservados/confirmados, catálogo modificado, intersección propia, plantilla/bloqueos/pasado, terminales, sobreturno y carrera real reserva→EXCLUDE con snapshot original íntegro.

- 5.4 refactor + baseline previa de pacientes: 167 passed, 2 deprecaciones, 96.69s; candidato compartido, Ruff correcto, KB05/07 reconciliadas. La suite incluyó reprogramar/crear/estados y pacientes scope/search/create/reuse/delete/public_boundary actuales, sin fallos preexistentes.

- 6.1 RED: el creador previo rechazó con RN-AU-03 403 la ficha con turno asignado; 6.2 GREEN: 4 passed.
- 6.3 triangulación: 18 passed; revocación al cancelar/ausencia, atención previa/otra cita activa, creador con/sin vínculo, otros profesionales/tenant y coincidencias/reuso coherentes, negativos sin PII ni edición.
- 6.4 refactor: 121 passed (TODOS tests de pacientes existentes y nuevos, incluida frontera pública), Ruff correcto. Cuatro call sites de exigir_acceso_paciente usan la misma sesión; búsqueda/duplicados/reuso comparten un predicado SQL explícito por tenant. KB03/05 actualizadas. Auth/core sin cambios.

- 7.1 RED: 7 architecture tests previos PASS, alta HTTP falló 404 antes de router. 7.2 GREEN: 6 passed; rutas internas, lecturas, PATCH/acciones y reprogramación, roles explícitos y schemas forbid incluidos vacíos.

- 7.3 triangulación HTTP: 33 passed (roles, autoasignación de ficha rechazada, agenda ajena, sin vínculo, tenant, PATCH/acciones extra, DELETE/código y snapshots).
- 7.4 RED guardas: ModuleNotFoundError tests.turnos_boundary; GREEN ampliado: 60 passed API/filtros/guardas/arquitectura. Casos falsos de constructor/asignación fuera del servicio y exposición pública detectados; app real y catálogo pasan.
- 7.5 refactor de serialización/alias/formato + OpenAPI: 82 passed (61 API/guardas/arquitectura y 21 baseline seed existentes), Ruff check/format correctos, nueve operaciones y esquemas restringidos comprobados. KB02 y CHANGES alineados al contrato/revisión 0006.

- 8.1 RED: seed anterior crea 0 turnos frente a 3 esperados. 8.2 GREEN: 3 passed (tres estados, idempotencia y cambios manuales conservados). Entrada crear_ejemplo interna usa el MISMO _crear/UoW y máquina, no bypass HTTP.
- 8.3 triangulación + semillas previas/congelación/R4: 46 passed. Catálogo inactivo, duración fuera de plantilla y bloqueos omiten controladamente; otro tenant y datos ficticios comprobados. PATCH duración/precio conserva Turno real y su reprogramación mantiene duración original.
- Revisión independiente detectó P2 nuevo: Consulta no es unique por nombre; RED reproduce MultipleResultsFound. Fix selecciona candidata determinista preferentemente activa (creado_en/id), sin modificar catálogo. GREEN 2 passed (existentes/faltantes), más selección activa frente a inactiva.
- 8.4 refactor/regresión: 50 passed, 4 deprecaciones, Ruff correcto. Se aísla el test de revisión C06 en 0005 y se restaura head en finally sin debilitar constraints; nuevas revisiones no invalidan el contrato C06. KB04/docstrings/CHANGES actualizados.

- 9.1 FULL final recuperada de /tmp/c07-full-final.log: **633 passed**, 28 deprecaciones, 383.76s, cero fallos/omisiones. No se repitió la suite tras la interrupción. Ruff check PASS, format136 archivos PASS, Alembic check sin operaciones nuevas y head único0006_turno; solo warning trigram conocido.

## Trazabilidad escenario → prueba ejecutada

Todos los nodos siguientes forman parte de la suite final de 633 casos; las parametrizaciones cubren los estados, roles y bordes indicados. La correspondencia se comprobó contra funciones reales por AST; no es sustituto de ejecutar tests.

### core/turnos

| Escenario | Pruebas reales |
|---|---|
| El backend calcula el fin | `tests/test_turnos_create.py::test_alta_calcula_fin_y_nace_reservado` |
| Cambiar el catálogo no cambia el turno | `tests/test_rn_ag_03_congelacion.py::test_catalogo_real_no_modifica_turno_y_reprogramacion_congela_duracion` |
| No se aceptan campos calculados o referencias editadas | `tests/test_turnos_api.py::test_post_http_rechaza_campos_que_calcula_el_backend`; `tests/test_turnos_api.py::test_patch_extra_no_cambia_fila` |
| Una referencia ajena al tenant no se utiliza | `tests/test_turnos_api.py::test_referencias_ajenas_y_lectura_id_otro_tenant_son404` |
| No se reserva un catálogo desactivado | `tests/test_turnos_create.py::test_catalogo_inactivo_no_se_reserva` |
| Reserva normal dentro de la plantilla | `tests/test_turnos_create.py::test_alta_calcula_fin_y_nace_reservado` |
| El intervalo completo debe caber | `tests/test_turnos_create.py::test_fin_fuera_de_plantilla_rechaza_aunque_inicio_cabe` |
| La frontera contigua no genera un cierre ficticio | `tests/test_turnos_create.py::test_franjas_contiguas_cubren_turno_pero_descanso_no` |
| El inicio pasado o igual al presente se rechaza | `tests/test_turnos_create.py::test_pasado_y_presente_no_crean_filas` |
| El cierre de todo el consultorio impide reservar | `tests/test_turnos_create.py::test_bloqueos_personales_globales_y_bordes` |
| Los bloqueos personales no cierran otra agenda | `tests/test_turnos_create.py::test_bloqueos_personales_globales_y_bordes` |
| Los turnos contiguos se permiten | `tests/test_turnos_model.py::test_exclude_permite_adyacencia_y_agendas_independientes`; `tests/test_turnos_concurrencia.py::test_dos_transacciones_no_confian_solo_en_la_consulta_previa` |
| La carrera entre dos reservas tiene un único ganador | `tests/test_turnos_concurrencia.py::test_dos_transacciones_no_confian_solo_en_la_consulta_previa` |
| El sobreturno también respeta el conflicto | `tests/test_turnos_create.py::test_consulta_previa_rechaza_ocupacion_y_sobreturno` |
| Cancelar libera y ausente conserva la ocupación | `tests/test_turnos_estados.py::test_cancelado_libera_ausente_sigue_ocupando` |
| Distintos profesionales no comparten la restricción | `tests/test_turnos_model.py::test_exclude_permite_adyacencia_y_agendas_independientes` |
| Urgencia fuera de horario semanal | `tests/test_turnos_create.py::test_urgencia_fuera_de_plantilla_nace_confirmada` |
| El flag sin motivo no basta | `tests/test_turnos_create.py::test_flag_y_motivo_siempre_explicitos` |
| El motivo no activa el flag implícitamente | `tests/test_turnos_create.py::test_flag_y_motivo_siempre_explicitos` |
| Un bloqueo conserva su efecto ante una urgencia | `tests/test_turnos_create.py::test_bloqueos_personales_globales_y_bordes` |
| Se recorren todas las transiciones permitidas | `tests/test_turnos_estados.py::test_los_25_pares_persistidos_y_snapshot_de_rechazo` |
| Todas las demás combinaciones se rechazan | `tests/test_turnos_estados.py::test_los_25_pares_persistidos_y_snapshot_de_rechazo` |
| Cancelar conserva el motivo opcional | `tests/test_turnos_estados.py::test_motivo_cancelacion_opcional_no_exige_texto` |
| Dos transiciones concurrentes no usan un estado obsoleto | `tests/test_turnos_estados.py::test_cancelacion_concurrente_impide_confirmacion_obsoleta` |
| Se conserva identidad y estado al mover | `tests/test_turnos_reprogramar.py::test_mover_conserva_identidad_estado_codigo_y_duracion` |
| Cambiar la prestación no cambia la duración congelada | `tests/test_turnos_reprogramar.py::test_reprogramar_conserva_estado_y_duracion_aunque_cambie_catalogo` |
| El destino ocupado deja el original intacto | `tests/test_turnos_reprogramar.py::test_destino_ocupado_no_cancela_ni_mueve_original` |
| El destino bloqueado o fuera de plantilla también revierte | `tests/test_turnos_reprogramar.py::test_destino_invalido_restaura_snapshot_completo` |
| Reprogramar a un intervalo que intersecta al propio turno es posible | `tests/test_turnos_reprogramar.py::test_interseccion_con_el_propio_intervalo_no_es_ocupacion` |
| Un terminal no se mueve | `tests/test_turnos_reprogramar.py::test_terminales_no_se_reprograman` |
| La carrera por el destino no deja una cancelación parcial | `tests/test_turnos_reprogramar.py::test_carrera_reserva_ganadora_revierte_reprogramacion` |
| Sin login ninguna operación accede a turnos | `tests/test_turnos_api.py::test_operaciones_sin_jwt_rechazadas`; `tests/test_architecture.py::test_toda_ruta_no_publica_declara_autenticacion_y_roles` |
| Recepción y dueño operan todas las agendas del tenant | `tests/test_turnos_api.py::test_recepcion_y_dueno_operan_todas_las_agendas` |
| El profesional solo opera su propia agenda | `tests/test_turnos_api.py::test_profesional_rechaza_otra_agenda_sin_mutaciones`; `tests/test_turnos_api.py::test_listado_profesional_es_propio` |
| Sin profesional vinculado no se abre la agenda | `tests/test_turnos_api.py::test_profesional_sin_vinculo_no_abre_agenda` |
| Crear una cita no permite apropiarse de una ficha ajena | `tests/test_turnos_api.py::test_profesional_no_puede_autoasignarse_ficha_ajena` |
| La lectura y la escritura no cruzan tenant | `tests/test_turnos_api.py::test_referencias_ajenas_y_lectura_id_otro_tenant_son404` |
| La edición no permite cambiar referencias o horario indirectamente | `tests/test_turnos_api.py::test_patch_extra_no_cambia_fila` |
| Cambiar estado usa el mismo contrato por ambas rutas | `tests/test_turnos_api.py::test_patch_y_accion_post_comparten_maquina` |
| Los filtros y la paginación son deterministas | `tests/test_turnos_api.py::test_filtros_combinados_rango_semiabierto_y_orden_estable`; `tests/test_turnos_api.py::test_filtros_invalidos_son422` |
| No se borra el historial por HTTP | `tests/test_turnos_api.py::test_delete_no_borra_y_codigo_no_autentica` |
| Los códigos tienen el formato y entropía previstos | `tests/test_turnos_codigos.py::test_generar_codigo_pide_nueve_bytes_a_secrets`; `tests/test_turnos_codigos.py::test_codigos_reales_tienen_formato_y_no_se_reutilizan` |
| La colisión no deja una reserva duplicada | `tests/test_turnos_create.py::test_colision_codigo_reintenta_sin_fila_parcial`; `tests/test_turnos_create.py::test_codigo_agotado_limita_intentos_y_no_crea_nada` |
| Un código válido no autentica una ruta de panel | `tests/test_turnos_api.py::test_delete_no_borra_y_codigo_no_autentica` |
| El primer seed crea los tres ejemplos | `tests/test_turnos_seed.py::test_primer_seed_crea_tres_turnos_por_servicio` |
| Repetir no modifica los ejemplos | `tests/test_turnos_seed.py::test_segundo_seed_no_duplica_ni_cambia_fechas_codigos_estados`; `tests/test_turnos_seed.py::test_seed_respeta_cancelacion_y_reprogramacion_manuales` |

### core/pacientes

| Escenario | Pruebas reales |
|---|---|
| La recepción gestiona el directorio completo | `tests/test_pacientes_scope.py::test_recepcion_y_dueno_leen_y_editan_cualquier_paciente` |
| El dueño gestiona el directorio completo | `tests/test_pacientes_scope.py::test_recepcion_y_dueno_leen_y_editan_cualquier_paciente` |
| El profesional sin flag solo lista los suyos | `tests/test_pacientes_scope.py::test_el_profesional_sin_flag_lista_solo_los_suyos`; `tests/test_pacientes_turnos_scope.py::test_asignacion_pendiente_habilita_ficha_edicion_y_busqueda` |
| El profesional sin flag no edita un paciente ajeno | `tests/test_pacientes_scope.py::test_el_profesional_sin_flag_no_toca_un_paciente_ajeno` |
| Un paciente creado por el profesional queda bajo su alcance | `tests/test_pacientes_scope.py::test_un_paciente_creado_por_el_profesional_aparece_en_su_listado` |
| Un turno pendiente permite preparar la atención | `tests/test_pacientes_turnos_scope.py::test_asignacion_pendiente_habilita_ficha_edicion_y_busqueda` |
| Una atención previa conserva el vínculo | `tests/test_pacientes_turnos_scope.py::test_otro_turno_permitido_o_atencion_previa_conservan_ficha` |
| Cancelar la única cita no atendida quita el acceso | `tests/test_pacientes_turnos_scope.py::test_ultima_cita_pendiente_revoca_todas_las_vias`; `tests/test_pacientes_turnos_scope.py::test_duplicados_y_reutilizacion_no_filtran_ficha_sin_vinculo` |
| Otro turno pendiente mantiene el acceso | `tests/test_pacientes_turnos_scope.py::test_otro_turno_permitido_o_atencion_previa_conservan_ficha` |
| Una ausencia sola no habilita la ficha | `tests/test_pacientes_turnos_scope.py::test_terminal_sin_atencion_no_habilita_ficha`; `tests/test_pacientes_turnos_scope.py::test_ultima_cita_pendiente_revoca_todas_las_vias` |
| Las coincidencias y la reutilización aplican el mismo alcance | `tests/test_pacientes_turnos_scope.py::test_duplicados_y_reutilizacion_incluyen_el_mismo_vinculo` |
| Otro profesional o tenant no concede el vínculo | `tests/test_pacientes_turnos_scope.py::test_turnos_de_otro_profesional_no_otorgan_ficha`; `tests/test_pacientes_turnos_scope.py::test_predicado_no_confia_en_una_referencia_uuid_de_otro_tenant` |
| El profesional sin vínculo conserva únicamente lo que creó | `tests/test_pacientes_turnos_scope.py::test_creador_conserva_su_ficha_sin_turnos_activos`; `tests/test_pacientes_turnos_scope.py::test_profesional_sin_vinculo_no_hereda_la_agenda_de_otro` |

## TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|---|---|---|---|---|---|---|---|
| 1–2 | test_turnos_model.py / test_turnos_codigos.py | Metadata + PostgreSQL | 88 passed | Imports/tabla ausentes | 4 passed | 22 casos | 22 passed + Ruff/Alembic |
| 3 | test_turnos_create.py / test_turnos_concurrencia.py | Servicio + concurrencia PG | 88 passed | Servicio ausente / excepción DB real | 3 iniciales | 35 + carrera/códigos | 42 passed |
| 4 | test_turnos_estados.py | Unit + PG con FOR UPDATE | Creación42 verde | Máquina ausente | 28 passed | 59 casos, 25 pares DB y pure | 101 passed combinados |
| 5 | test_turnos_reprogramar.py | Servicio + carrera PG | Estados59 verde | Operación ausente | 2 passed | 14 casos | 167 passed con baseline pacientes |
| 6 | test_pacientes_turnos_scope.py | Servicio/consultas PG | Pacientes previos en167 verdes | Ficha asignada rechazada403 | 4 passed | 18 casos | 121 passed pacientes/frontera |
| 7 | test_turnos_api.py / test_turnos_boundary.py | HTTP + arquitectura | 7 arquitectura | POST404 / helper guard ausente | 6 passed | 33 HTTP;60 con filtros/guardas | 82 passed incluyendo21 seedbaseline |
| 8 | test_turnos_seed.py / test_rn_ag_03_congelacion.py | Seed + PG + catálogo HTTP | 21 seed en82 verdes | 0 ejemplos, se esperan3 | 3 passed | 46 passed + duplicados | 50 passed, Ruff |
| P2 revisión seed | test_turnos_seed.py::test_consultas_duplicadas_validas_no_rompen_seed | PostgreSQL/seed | Seed3 verde | MultipleResultsFound | 2 passed | Activa preferida/inactiva | Incluido50 y633 finales |
| 9.1 | Suite completa app/tests | Unit + integración | Bloques1–8 verdes | N/A verificación | 633 passed/0 skipped | 28 deprecaciones | Ruff136 archivos/Alembic sin diferencias |
| 9.2 | tests/e2e_turnos.py | HTTP real + PostgreSQL/Redis nuevos | Suite633 verde | N/A verificación | PASS | Tres roles, carrera201/409, rollback, revocación ficha | Ruff solo script |

- 9.2 E2E ejecutado con `uv run --frozen python -m tests.e2e_turnos` en DB recién creada `c07_e2e_9d6936be74`, migraciones0001→0006 y Redis DB1. Login/me tres roles, seed idempotente, reserva/sobreturno/bloqueo, estados válidos e inválidos, HTTP concurrente[201,409], reprogramación preserva identidad y rollback íntegro, cancelación revoca ficha. PASS exit0. Subproceso Uvicorn interno terminado en finally.
- El primer intento E2E se detuvo por variables requeridas faltantes del script antes de HTTP, no por código de producto. Se completó el ENV ficticio del test y se repitió solo E2E; suite633 no repetida.

- 9.3 Strict C07 PASS; trazabilidad59escenarios/72referencias reales y tablaTDD arriba; Ruff final app/tests PASS y **137 archivos** formatted (incluido E2E), git diff --check correcto (solo aviso CRLF no error). Sin pruebas funcionales repetidas tras añadir script E2E.

- 9.4 Cierre autorizado por el usuario al pedir terminar las cuatro tareas finales. Sync síncrono previo: core/turnos9 requisitos46escenarios nuevos; core/pacientes1 requisito modificado13escenarios, seis requisitos restantes y Purpose intactos (total7/39). Comparación textual completa de todos los bloques y Purpose antes de mover; strictmain12PASS/0failed. Archivo porCLI a continuación, sin commit/push ni actualización demo.

- Archivo confirmado por `openspec archive c-07-turnos-state-machine --yes --skip-specs --json` (exit0): `2026-11-05-c-07-turnos-state-machine`. La sincronización se realizó antes; --skip-specs evita aplicarla dos veces. CLI36/36 antes de archivar, metadata `.openspec.yaml` idéntica por SHA256; CHANGES actualizado al cerrar.
