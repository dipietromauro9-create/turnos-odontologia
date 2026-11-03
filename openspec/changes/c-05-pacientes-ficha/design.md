# Diseño

## Contexto

C-02 dejó `TenantMixin`/`AuditMixin`, `TenantSession` con filtro automático, `BaseRepository`/`UnitOfWork` y la migración `0002_tenancy_usuario`. C-03 dejó `AuthMiddleware` (falla cerrado salvo allowlist), `CurrentUserDep`, `require_role(...)`, `es_dueno(usuario)`, `alcance_agenda(usuario)` y `require_acceso_profesional(...)`. C-05 es el primer dominio de negocio sobre esa base y corre en paralelo con C-04 (`Profesional`/`Prestacion`) y C-06 (`Disponibilidad`/`Bloqueo`); por lo tanto **no puede depender de tablas de C-04 ni de C-07**.

Restricciones que moldean el diseño:

- `Paciente` del modelo de datos no tiene vínculo directo con `Profesional`; el vínculo real llega con `Turno` en C-07. RN-AU-03 ("sus pacientes") no tiene todavía una fuente de verdad en la base.
- El turnero público (C-09) reserva con nombre + teléfono y debe reutilizar pacientes por teléfono (RN-PA-01) sin ver la ficha (RN-PA-02).
- La KB exige duplicados advertidos y no bloqueados, índices `(tenant_id, telefono)` y trigram sobre nombre, y borrado físico sin auditoría (RN-PA-03, DD-07, IN-01).
- El harness de tests ya distingue unitarios de `integration` (Postgres real) y `factories.py` ya crea tenants/usuarios.

Ver `proposal.md` para la motivación y `specs/core/pacientes/spec.md` para el contrato de comportamiento.

## Objetivos / No objetivos

**Objetivos:**

- Un directorio de pacientes tenant-scoped, con ficha básica y búsqueda útil para recepción, que C-07 pueda referenciar como FK.
- Un contrato de duplicado y de reutilización por teléfono estable y consumible por C-09 sin filtrar PII.
- Enforced de RN-AU-03 con la información disponible en C-05, dejando explícito qué completa C-07.
- Migración única y reversible que no rompa `alembic check` ni el guard de arquitectura de rutas.

**No objetivos:**

- Vínculo definitivo profesional↔paciente vía turnos: C-07.
- Endpoint HTTP de borrado, exportación, odontograma, soft delete o audit trail: post-MVP / C-12 (IN-01).
- Búsqueda accent-insensitive o fuzzy por documento: post-MVP.
- Paginación con cursor o conteo total: se usa `limit`/`offset` simple.
- Cambios en `core/auth`, `core/rbac`, `core/tenancy` o `core/persistence`.

## Decisiones

- **`Paciente` con `creado_por_usuario_id` nullable como alcance provisional de RN-AU-03.** El modelo del KB no vincula paciente con profesional, y C-05 no puede referenciar `Profesional` (C-04) ni `Turno` (C-07). Se agrega `creado_por_usuario_id` (FK nullable a `usuario.id`, `ON DELETE SET NULL`, índice `(tenant_id, creado_por_usuario_id)`): recepción y dueño ven todo; el profesional sin flag ve los pacientes que él creó. Fundamento: usa una tabla que ya existe (C-03), permite entregar US-009 al profesional sin inventar una FK a una tabla inexistente y es forward-compatible (C-07 puede ampliar el alcance a "creados por mí o con turno mío"). Alternativas descartadas: `profesional_id` FK a `profesional` (rompe la independencia de C-04 y el orden de migraciones), no implementar el alcance hasta C-07 (deja al actor principal de US-009 sin acceso), y `tenant_id` único como alcance (viola RN-AU-03).
  - Consecuencia aceptada: un paciente creado por recepción no aparece en el listado del profesional sin flag hasta que C-07 lo vincule por turno. Queda registrado como riesgo y como tarea de integración en C-07.

- **Teléfono normalizado a dígitos en la propia columna `telefono`.** El servicio acepta formatos humanos (`+54 9 11 4555-0001`, `11 4555-0001`), valida 6–15 dígitos y persiste solo los dígitos. Fundamento: hace útil el índice `(tenant_id, telefono)` que exige la KB, da una clave estable para duplicados y reutilización (RN-PA-01), y evita una segunda columna de búsqueda. Alternativa descartada: guardar el texto crudo y normalizar en cada query (`regexp_replace`), que inutiliza el índice y duplica la lógica de normalización. El frontend formatea para mostrar; la API expone dígitos.

- **Duplicado por teléfono normalizado O nombre normalizado, advertido con `RN-PA-01`.** La detección compara `telefono` normalizado y `lower(trim(nombre))` dentro del tenant y del alcance visible del llamador. El alta siempre persiste (201) y devuelve `advertencia: {codigo: "RN-PA-01", mensaje, duplicados: [PacienteResumen]}`. Fundamento: la KB dice "duplicados por (nombre, teléfono) advertidos, no bloqueados"; el teléfono es la señal fuerte para reservas y el nombre ayuda a la recepción. La advertencia se acota al alcance para no filtrar pacientes ajenos a un profesional sin flag. Alternativas descartadas: bloquear con 409 (contradice RN-PA-01 y el scope), advertir solo por el par exacto (pierde el caso típico de mismo teléfono con nombre mal escrito).

- **Contrato de respuesta del alta separado del contrato de lectura.** `POST /pacientes` devuelve `201` con `PacienteCreadoOut { paciente: PacienteOut, advertencia: AdvertenciaDuplicado | null }`; `GET` y `PATCH` devuelven `PacienteOut` sin advertencia. Fundamento: mantiene `PacienteOut` reutilizable y sin campos opcionales de contexto, y hace explícito para el frontend cuándo hubo duplicado. Alternativa descartada: aplanar `advertencia` dentro de `PacienteOut` (contamina las lecturas y confunde el contrato de C-09).

- **Operación de dominio `crear_o_reutilizar_paciente(...) -> ResultadoReutilizacion` para C-09.** Devuelve `identidad: PacienteIdentidadMinima` (`id`, `nombre`, `telefono`), `creado: bool` y `advertencia`, nunca la ficha completa. Acepta `usuario_id: UUID | None`: el panel pasa el usuario autenticado; el turnero público pasa `None` y el paciente creado queda con `creado_por_usuario_id = NULL` (visible para recepción y dueño). En la ruta pública la advertencia de duplicado viaja sin `duplicados` (solo código/mensaje) para no filtrar PII. C-09 la invoca desde la reserva (nunca desde HTTP `/pacientes`, que exige JWT). Fundamento: RN-PA-01 pide "crear o reutilizar" por teléfono y RN-PA-02 prohíbe exponer la ficha en público; separar el contrato de servicio del contrato HTTP permite ambas cosas. Alternativa descartada: que C-09 llame `POST /pacientes` (exigiría JWT y expondría la ficha).

- **Alcance RBAC en una política de dominio + guard de router.** El router declara `dependencies=[Depends(require_role(RolUsuario.RECEPCION, RolUsuario.PROFESIONAL))]`, lo que además satisface el guard de arquitectura (`__rbac_roles__`). La política `alcance_pacientes(usuario)` devuelve `TODOS` (recepción o dueño) o `PROPIOS` (profesional sin flag), y `exigir_acceso_paciente(usuario, paciente)` responde 403 `RN-AU-03` con `details.reason = "fuera_de_alcance"` si no corresponde. Fundamento: reutiliza la semántica de C-03 (`es_dueno`, `alcance_agenda`) sin acoplar pacientes a la agenda, y deja el 401 antes del 403 porque `require_role` depende de `get_current_user`. Alternativa descartada: un `require_role(PROFESIONAL)` por endpoint (recepción quedaría afuera y se repetiría la lógica de alcance en cada ruta).

- **Búsqueda: trigram sobre `lower(nombre)` + `ILIKE` de respaldo; teléfono por `LIKE` de dígitos.** `GET /pacientes?q=` usa `similarity(lower(nombre), lower(:q)) >= 0.3 OR lower(nombre) LIKE '%' || lower(:q) || '%'` para nombres, y `telefono LIKE '%' || :digits || '%'` cuando `q` contiene dígitos. Para `len(q) < 3` se usa solo `ILIKE` (el trigram no discrimina). Orden: similitud descendente y luego nombre. Todas las consultas de dominio agregan explícitamente `Paciente.tenant_id == session.tenant_id` además del filtro automático de `TenantSession` (R3: defensa en profundidad, no confianza en un solo mecanismo). Fundamento: cubre errores de tipeo (trigram) y búsquedas parciales cortas, y mantiene el índice GIN útil. Alternativa descartada: `to_tsvector`/full-text (no maneja bien nombres propios ni typos).

- **Índices: GIN compuesto `(tenant_id, lower(nombre) gin_trgm_ops)` con `btree_gin`, más btree `(tenant_id, telefono)` y `(tenant_id, creado_por_usuario_id)`.** Fundamento: respeta la KB (`(tenant_id, nombre)` trigram) y mantiene el prefijo de tenant en el índice (R3). Si la versión de Postgres o la combinación de opclasses falla, el plan B es un GIN `(lower(nombre) gin_trgm_ops)` separado más un btree `(tenant_id)`; el test de índices se ajusta a esa variante sin cambiar la spec. Se requieren `CREATE EXTENSION IF NOT EXISTS pg_trgm` y `btree_gin`.

- **Migración `0004_paciente` con `down_revision = "0003_c04_profesional_prestacion"`.** Crea extensiones, tabla, FKs, CHECKs de longitud y los tres índices; el `downgrade` los elimina y borra las extensiones solo si no las usa otro objeto (mismo patrón que `citext` en `0002`). Fundamento: R7 exige migración para todo cambio de modelo. C-04 ya se archivó con `0003_c04_profesional_prestacion`; por eso C-05 reencadena su `down_revision` a esa revisión y la migración se numera `0004` para mantener un único head (verificado con `alembic heads` y `alembic check`). Si C-06 archiva antes con su propia revisión, se aplica el mismo reencadenamiento.

- **Sin ruta HTTP de borrado en C-05; borrado físico como operación de dominio.** El scope lista `GET/POST/PATCH`. Se implementa `eliminar_paciente(session, paciente, alcance)` que borra la fila físicamente y se prueba a nivel de servicio; el código lleva una nota de deuda `RN-PA-03 / DD-07 / IN-01`. Fundamento: cumple RN-PA-03 sin ampliar la superficie HTTP ni inventar códigos de error para conflictos con turnos (que recién existen en C-07). Alternativa descartada: `DELETE /pacientes/{id}` (fuera del scope explícito y obligaría a definir qué pasa con turnos futuros).

- **Códigos de error: `RN-PA-01` para advertencia de duplicado, `RN-PA-02` para ficha no disponible, `RN-AU-03` para alcance.** Un id inexistente o de otro tenant responde `404 RN-PA-02` con `details.reason = "no_encontrado"`; un paciente existente pero ajeno responde `403 RN-AU-03`. Fundamento: RN-GL-01 exige código de regla y no se inventan códigos nuevos; la distinción 404/403 evita confirmar la existencia de un paciente ajeno. Se deja como pregunta abierta si conviene un `RN-PA-04` específico.

- **Schemas Pydantic con `extra='forbid'` y `PacienteUpdate` todo-opcional.** `PacienteCreate` exige `nombre` y `telefono`; `documento`, `fecha_nac` y `observaciones` son nullables. `fecha_nac` se valida como fecha entre 1900 y hoy. `PATCH` aplica `model_dump(exclude_unset=True)`; un body vacío devuelve el paciente sin cambios (no-op) en lugar de error. Fundamento: R1 y el patrón de actualización parcial ya usado en el proyecto.

- **Seed idempotente por teléfono normalizado.** Se agregan dos pacientes ficticios (`Paciente Demo Uno` / `1145550001`, `Paciente Demo Dos` / `1145550002`) con `creado_por_usuario_id` del dueño demo. La idempotencia se resuelve buscando por teléfono dentro del tenant, no por nombre. Fundamento: R9 y el contrato de seed idempotente de C-02.

## Riesgos / Compromisos

- [Riesgo] `creado_por_usuario_id` es una interpretación provisional de "sus pacientes": un paciente cargado por recepción no aparece en el listado del profesional sin flag hasta que C-07 lo vincule por turno → Mitigación: documentado en design/spec, el dueño y la recepción no se ven afectados, y C-07 debe ampliar el alcance a "creado por mí o con turno mío"; se deja una tarea de integración explícita en C-07.
- [Riesgo] El borrado físico chocará con la FK de `Turno.paciente_id` cuando exista C-07 → Mitigación: C-05 no expone ruta de borrado; C-07 define `ON DELETE RESTRICT` o una política de desvinculación; la deuda queda registrada (IN-01).
- [Riesgo] El índice GIN compuesto con `btree_gin` puede no estar disponible o no aceptar la combinación de opclasses en algún entorno → Mitigación: plan B documentado (GIN separado + btree de tenant); el test de índices verifica la variante efectiva.
- [Riesgo] La normalización de teléfono solo quita no-dígitos: `011 4555-0001` y `11 4555-0001` se consideran distintos → Mitigación: se documenta como límite v1; la UI debe enviar un formato consistente; canonicalización nacional queda como pregunta abierta.
- [Riesgo] La búsqueda por nombre no es accent-insensitive ("Gonzalez" no matchea "González" por trigram) → Mitigación: `ILIKE` cubre el caso sin tilde solo si el texto coincide; se registra `unaccent` como mejora post-MVP.
- [Riesgo] Colisión de numeración de migración con C-04/C-06 en paralelo → Mitigación: `alembic heads` debe devolver un solo head; al archivar se reencadena/renumera la revisión y se corre `alembic check`.
- [Riesgo] La advertencia de duplicado devuelve nombre y teléfono de coincidencias; para recepción es todo el consultorio → Mitigación: es personal autenticado y la spec acota la advertencia al alcance visible; nunca se expone en rutas públicas.
- [Riesgo] `limit`/`offset` sin conteo total puede generar listados incompletos en el panel → Mitigación: `limit` por defecto 20 y máximo 100; el frontend pagina hasta recibir menos de `limit`.
- [Riesgo] Un `PATCH` vacío devuelve 200 sin cambios y podría ocultar un error de UI → Mitigación: se documenta el no-op y el frontend deshabilita el guardado sin cambios.
- [Riesgo] `fecha_nac` se persiste como `date` sin zona; el resto del sistema usa `timestamptz` → Mitigación: `fecha_nac` es una fecha calendario, no un instante; se documenta la excepción y no se usa para cálculos de agenda.

## Plan de migración

1. `alembic upgrade head` aplica `0004_paciente`: `CREATE EXTENSION IF NOT EXISTS pg_trgm`, `CREATE EXTENSION IF NOT EXISTS btree_gin`, tabla `paciente`, FKs, CHECKs e índices. `alembic check` debe reportar cero diferencias de metadata.
2. Ejecutar `python -m app.db.seed`: crea tenant/usuarios si faltan y agrega los dos pacientes demo sin duplicar.
3. Verificación de humo: login `recepcion@demo` → `POST /pacientes` (201, advertencia nula), repetir con el mismo teléfono (201 + `RN-PA-01`), `GET /pacientes?q=...` por nombre y teléfono, `PATCH` parcial; `GET /pacientes` sin token → 401; `GET /pacientes` con profesional sin flag y paciente ajeno → 403 `RN-AU-03`.
4. Rollback: `alembic downgrade 0003_c04_profesional_prestacion` elimina tabla e índices y las extensiones solo si no las usa otro objeto. El seed no se revierte automáticamente; los pacientes demo se pueden borrar con la operación de dominio.

## Preguntas abiertas

- **Código para "paciente no encontrado".** La KB define solo `RN-PA-01..03`. Se propone `RN-PA-04` (paciente no encontrado / no disponible) para que el frontend distinga 404 de 403 sin parsear `details.reason`. Mientras no se apruebe, se usa `RN-PA-02` con `details.reason = "no_encontrado"`. Confirmar si se actualiza `knowledge-base/05_reglas_de_negocio.md`.
- **Superficie HTTP de borrado.** ¿El panel necesita `DELETE /pacientes/{id}` en v1 o alcanza con la operación de dominio hasta C-10/C-12? C-05 no la expone por scope; si se aprueba, hay que definir el comportamiento con turnos existentes (C-07).
- **Definición definitiva de "sus pacientes".** C-07 debe decidir si el alcance del profesional es "creados por mí" (provisional de C-05), "con turno mío", o la unión; el contrato de C-05 se mantiene si se amplía la consulta.
- **Canonicalización de teléfonos argentinos.** ¿Se normaliza el prefijo nacional (`0`, `15`, `+54 9`) en v1 o se exige un formato consistente desde la UI? Afecta duplicados y reutilización entre canales (panel vs. turnero).
- **Búsqueda accent-insensitive.** ¿Se agrega `unaccent` en una migración futura o se resuelve en el frontend? No cambia el contrato actual.
