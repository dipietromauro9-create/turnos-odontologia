# Spec Delta

## MODIFIED Requirements

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
