# core/pacientes Specification

## Purpose

Define el directorio y la ficha básica del paciente: alta con advertencia de duplicado, búsqueda por nombre y teléfono, reutilización de un paciente existente por teléfono para reservar, alcance de recepción/profesional/dueño y la garantía de que la ficha nunca se expone en una ruta pública.

## Requirements

### Requirement: La ficha básica vive dentro del tenant y nunca en una ruta pública (RN-PA-02)

El sistema DEBE (SHALL) exponer la ficha básica del paciente (`nombre`, `telefono`, `documento`, `fecha_nac`, `observaciones`) únicamente en rutas de panel autenticadas y dentro del tenant resuelto. Ninguna ruta pública, incluido el turnero, DEBE (SHALL) devolver datos de `Paciente`. Toda request sin access token válido DEBE (SHALL) recibir HTTP 401 antes de consultar pacientes, y toda lectura o escritura DEBE (SHALL) quedar acotada al `tenant_id` de la sesión.

#### Scenario: Sin token la ficha responde 401

- **WHEN** un cliente sin cabecera `Authorization` llama a `GET /pacientes`, `POST /pacientes` o `PATCH /pacientes/{id}`
- **THEN** la respuesta es HTTP 401 con el sobre de error de dominio y no se devuelve ni se modifica ningún dato de paciente

#### Scenario: La recepción autenticada accede a la ficha

- **WHEN** un usuario con `rol = recepcion` y token válido llama a `GET /pacientes`
- **THEN** la respuesta es HTTP 200 y contiene únicamente pacientes del tenant resuelto

#### Scenario: Ninguna ruta pública coincide con pacientes

- **WHEN** se inspecciona la allowlist de rutas exentas de JWT y las rutas públicas del turnero
- **THEN** ninguna ruta coincide con el prefijo `/pacientes` ni devuelve campos de la ficha del paciente

#### Scenario: Un paciente de otro tenant no se puede leer

- **WHEN** un usuario del tenant A solicita por id un paciente que solo existe en el tenant B
- **THEN** la respuesta es HTTP 404 y no se devuelve ningún dato del paciente ajeno

### Requirement: La búsqueda encuentra pacientes por nombre con trigram y por teléfono (RN-PA-01)

El sistema DEBE (SHALL) permitir `GET /pacientes?q=` y encontrar pacientes del tenant por coincidencia parcial de `nombre` usando similitud trigram, y por `telefono` comparando los dígitos normalizados. Sin `q`, DEBE (SHALL) listar los pacientes del tenant ordenados por nombre. La búsqueda DEBE (SHALL) aceptar `limit` y `offset`, y NUNCA DEBE (SHALL) devolver pacientes de otro tenant. El esquema DEBE (SHALL) declarar un índice trigram sobre el nombre y un índice compuesto por `(tenant_id, telefono)`.

#### Scenario: Un nombre parcial con error de tipeo encuentra al paciente

- **WHEN** existe el paciente "María González" y la recepción busca `q=maria gonzales`
- **THEN** el resultado incluye a "María González" porque la similitud trigram supera el umbral

#### Scenario: El teléfono se encuentra con o sin formato

- **WHEN** existe un paciente con teléfono normalizado `1145550001` y la recepción busca `q=11 4555-0001` o `q=1145550001`
- **THEN** el resultado incluye a ese paciente porque la comparación usa solo los dígitos

#### Scenario: Sin término de búsqueda se lista el directorio

- **WHEN** la recepción llama a `GET /pacientes` sin `q`
- **THEN** la respuesta es HTTP 200 con los pacientes del tenant ordenados por nombre, respetando `limit` y `offset`

#### Scenario: Un término muy corto no depende del trigram

- **WHEN** la recepción busca `q=ma` (menos de tres caracteres)
- **THEN** la búsqueda usa coincidencia parcial de texto y devuelve los pacientes cuyo nombre contiene ese fragmento

#### Scenario: La búsqueda no cruza el tenant

- **WHEN** existen pacientes con el mismo nombre en dos tenants y se busca desde el tenant A
- **THEN** el resultado contiene únicamente pacientes del tenant A

#### Scenario: El esquema declara los índices de búsqueda

- **WHEN** se inspeccionan los índices de la tabla `paciente`
- **THEN** existen un índice trigram sobre `lower(nombre)` y un índice compuesto que empieza por `(tenant_id, telefono)`

### Requirement: El alta de un posible duplicado responde 201 con advertencia y no se bloquea (RN-PA-01)

El sistema DEBE (SHALL) permitir crear un paciente aunque exista otro con el mismo teléfono normalizado o el mismo nombre normalizado. En ese caso DEBE (SHALL) responder HTTP 201 con el paciente creado y una advertencia con código `RN-PA-01` que liste las coincidencias, sin impedir la persistencia. La advertencia NUNCA DEBE (SHALL) incluir pacientes que el llamador no puede ver según su alcance. Si no hay coincidencias, la advertencia DEBE (SHALL) ser nula.

#### Scenario: Alta sin coincidencias no advierte

- **WHEN** la recepción crea un paciente con un nombre y un teléfono que no existen en el tenant
- **THEN** la respuesta es HTTP 201 con el paciente y `advertencia = null`

#### Scenario: Mismo teléfono produce advertencia y crea igual

- **WHEN** la recepción crea un paciente con el mismo teléfono normalizado que otro ya existente
- **THEN** la respuesta es HTTP 201, el nuevo paciente queda persistido y la advertencia tiene código `RN-PA-01` con la coincidencia

#### Scenario: Mismo nombre con otro teléfono también advierte

- **WHEN** la recepción crea un paciente con el mismo nombre normalizado que otro existente pero distinto teléfono
- **THEN** la respuesta es HTTP 201 con la advertencia `RN-PA-01` y el nuevo paciente queda persistido

#### Scenario: Un duplicado de otro tenant no advierte

- **WHEN** existe un paciente con el mismo teléfono en otro tenant y se crea uno en el tenant actual
- **THEN** la respuesta es HTTP 201 sin advertencia, porque la comparación no cruza el tenant

#### Scenario: La advertencia respeta el alcance del llamador

- **WHEN** un profesional sin flag crea un paciente que coincide con un paciente de otro profesional
- **THEN** la advertencia no incluye la coincidencia ajena, porque el llamador no puede verla

### Requirement: La reutilización por teléfono es el contrato de reserva (RN-PA-01)

El sistema DEBE (SHALL) ofrecer una operación de dominio que, dado un nombre y un teléfono, reutilice el paciente existente del tenant cuyo teléfono normalizado coincide y, si no existe, cree uno nuevo. La operación DEBE (SHALL) informar si reutilizó o creó (`creado`), y DEBE (SHALL) devolver la misma advertencia de duplicado cuando corresponda. El resultado DEBE (SHALL) exponer solo la identidad mínima del paciente (`id`, `nombre`, `telefono`) y NUNCA DEBE (SHALL) incluir `observaciones` ni la ficha completa. Este contrato es el que consume el turnero público en C-09.

#### Scenario: Un teléfono existente reutiliza el paciente

- **WHEN** se invoca la reutilización con un teléfono ya registrado en el tenant
- **THEN** el resultado devuelve la identidad mínima del paciente existente, `creado = false` y el mismo `id`

#### Scenario: Un teléfono nuevo crea el paciente

- **WHEN** se invoca la reutilización con un teléfono que no existe en el tenant
- **THEN** el resultado devuelve un paciente nuevo persistido con `creado = true`

#### Scenario: El formato del teléfono no impide reutilizar

- **WHEN** el paciente existente tiene teléfono `1145550001` y la reserva envía `11 4555-0001`
- **THEN** la operación reutiliza el paciente existente y `creado = false`

#### Scenario: La reutilización no expone la ficha pública

- **WHEN** el turnero público consume el resultado de la reutilización para una reserva
- **THEN** solo recibe la identidad mínima del paciente y nunca `observaciones` ni datos de otros pacientes

#### Scenario: Un teléfono de otro tenant no se reutiliza

- **WHEN** el teléfono existe solo en otro tenant y se invoca la reutilización en el tenant actual
- **THEN** la operación crea un paciente nuevo en el tenant actual

### Requirement: Recepción gestiona todos los pacientes y el profesional solo los suyos salvo que sea dueño (RN-AU-03)

El sistema DEBE (SHALL) permitir a `rol = recepcion` listar, buscar, crear y editar pacientes de todo el consultorio. El profesional dueño (`rol = profesional` y `es_dueno = true`) DEBE (SHALL) tener el mismo alcance. El profesional sin flag DEBE (SHALL) listar y editar únicamente los pacientes que le pertenecen y DEBE (SHALL) recibir HTTP 403 con código `RN-AU-03` al intentar leer o modificar un paciente ajeno. La pertenencia DEBE (SHALL) cumplirse si el usuario creó la ficha, o si su profesional vinculado tiene con ese paciente al menos un turno `atendido`, `reservado` o `confirmado` dentro del mismo tenant. Un turno `cancelado` o `ausente` por sí solo NO DEBE (SHALL) habilitar acceso; cancelar o marcar ausente el único turno pendiente DEBE (SHALL) quitar el acceso si el usuario no creó la ficha ni atendió al paciente ni conserva otro turno reservado/confirmado con él. La misma regla DEBE (SHALL) regir lectura, edición, listado, búsqueda, advertencias de duplicado y reutilización de pacientes bajo alcance propio. El rol y el alcance DEBEN (SHALL) derivarse del token y de la fila `Usuario`, nunca de datos enviados por el cliente; ningún vínculo DEBE (SHALL) cruzar el tenant.

#### Scenario: La recepción gestiona el directorio completo
- **WHEN** un usuario con `rol = recepcion` lista, crea o edita un paciente de cualquier profesional
- **THEN** la operación se procesa sin 403

#### Scenario: El dueño gestiona el directorio completo
- **WHEN** un usuario con `rol = profesional` y `es_dueno = true` lista, crea o edita un paciente de cualquier profesional
- **THEN** la operación se procesa sin 403

#### Scenario: El profesional sin flag solo lista los suyos
- **WHEN** un usuario con `rol = profesional` y `es_dueno = false` lista pacientes
- **THEN** la respuesta contiene únicamente pacientes que creó o con los que su profesional tiene un turno reservado, confirmado o atendido en el tenant

#### Scenario: El profesional sin flag no edita un paciente ajeno
- **WHEN** un usuario con `rol = profesional` y `es_dueno = false` intenta leer o editar un paciente que no cumple ninguno de los vínculos permitidos
- **THEN** la respuesta es HTTP 403 con código `RN-AU-03` y no se devuelve ni se modifica la ficha ajena

#### Scenario: Un paciente creado por el profesional queda bajo su alcance
- **WHEN** un usuario con `rol = profesional` y `es_dueno = false` crea un paciente
- **THEN** el paciente queda asociado a su alcance y aparece en su listado, incluso si no tiene turnos o se cancelan todos

#### Scenario: Un turno pendiente permite preparar la atención
- **WHEN** recepción asigna al profesional un turno reservado o confirmado de un paciente cuya ficha creó otra persona
- **THEN** el profesional puede encontrar, leer y editar esa ficha

#### Scenario: Una atención previa conserva el vínculo
- **WHEN** el profesional tiene un turno atendido con el paciente y se cancela su único turno futuro
- **THEN** conserva acceso a la ficha por la atención previa

#### Scenario: Cancelar la única cita no atendida quita el acceso
- **WHEN** se cancela el único turno del profesional con un paciente que no creó ni atendió
- **THEN** la ficha deja de aparecer en listado, búsqueda, duplicados y reutilización bajo alcance propio, y leerla o editarla devuelve 403 `RN-AU-03`

#### Scenario: Otro turno pendiente mantiene el acceso
- **WHEN** se cancela un turno pero sigue existiendo otro reservado o confirmado entre el mismo profesional y paciente
- **THEN** conserva acceso a la ficha

#### Scenario: Una ausencia sola no habilita la ficha
- **WHEN** el único vínculo es un turno ausente y el profesional no creó ni atendió al paciente
- **THEN** no puede leer ni editar la ficha ni verla en búsquedas o advertencias

#### Scenario: Las coincidencias y la reutilización aplican el mismo alcance
- **WHEN** un profesional busca, crea con advertencia de duplicados o reutiliza por teléfono un paciente con un vínculo permitido por turno
- **THEN** se lo trata igual que a un paciente creado por ese usuario, sin ampliar las coincidencias a fichas sin vínculo

#### Scenario: Otro profesional o tenant no concede el vínculo
- **WHEN** un paciente solo tiene turnos con otro profesional o existe un vínculo semejante en otro tenant
- **THEN** esos turnos no conceden acceso al profesional solicitante

#### Scenario: El profesional sin vínculo conserva únicamente lo que creó
- **WHEN** un usuario profesional no tiene fila de Profesional vinculada pero sí creó una ficha
- **THEN** conserva esa ficha por creador, sin adquirir fichas por turnos de otras identidades

### Requirement: El borrado es físico en v1 y la falta de auditoría queda como deuda explícita (RN-PA-03, DD-07, IN-01)

El sistema DEBE (SHALL) permitir el borrado físico de un paciente a nivel de dominio, sin columna de borrado lógico ni marca de inactividad, y NO DEBE (SHALL) registrar una traza de auditoría en v1. La operación de borrado DEBE (SHALL) quedar documentada como deuda explícita (IN-01, DD-07) en el código y en el design. C-05 no DEBE (SHALL) exponer una ruta HTTP de borrado: el scope de este change cubre `GET`, `POST` y `PATCH`.

#### Scenario: El modelo no tiene borrado lógico

- **WHEN** se inspecciona la tabla `paciente`
- **THEN** no existe una columna `deleted_at`, `eliminado_en` ni `activo` que permita ocultar filas

#### Scenario: El borrado elimina la fila físicamente

- **WHEN** la operación de dominio elimina un paciente existente del tenant
- **THEN** la fila deja de existir en la base y una lectura posterior responde HTTP 404

#### Scenario: La deuda de auditoría está documentada

- **WHEN** se revisa el código del dominio y el design del change
- **THEN** ambos registran que no hay auditoría ni soft delete y que revertirlo es prioridad post-MVP (IN-01)

### Requirement: El seed demo crea dos pacientes ficticios e idempotentes (R9)

El sistema DEBE (SHALL) ampliar el seed demo con exactamente dos pacientes ficticios del tenant `demo`, creados por el usuario dueño, usando nombres y teléfonos inventados. Ejecutar el seed más de una vez DEBE (SHALL) dejar el mismo estado, sin duplicar pacientes ni sobreescribir datos existentes. El seed NUNCA DEBE (SHALL) contener datos personales reales.

#### Scenario: El seed crea los dos pacientes demo

- **WHEN** se ejecuta el seed sobre una base migrada sin datos
- **THEN** existen dos pacientes del tenant `demo` con datos ficticios y asociados al dueño demo

#### Scenario: Reejecutar el seed no duplica pacientes

- **WHEN** se ejecuta el seed por segunda vez sobre la misma base
- **THEN** siguen existiendo exactamente dos pacientes demo, sin filas nuevas ni cambios de datos

#### Scenario: El seed no contiene PII real

- **WHEN** se inspeccionan los pacientes creados por el seed
- **THEN** los nombres y teléfonos son ficticios y no corresponden a personas reales
