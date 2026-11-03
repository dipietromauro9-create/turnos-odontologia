# Profesionales Specification

## Purpose

Define el directorio de profesionales del consultorio: alta, consulta y edición por parte del dueño, vínculo opcional con un usuario de login, desactivación sin borrado y aislamiento de datos por tenant.

## Requirements

### Requirement: El profesional pertenece al consultorio y puede vincularse a un usuario de login

El sistema DEBE (SHALL) modelar cada profesional con `tenant_id` obligatorio, un `nombre` no vacío, `matricula` y `especialidad` opcionales, un flag `activo` y un `usuario_id` opcional. Cuando `usuario_id` está presente DEBE (SHALL) referenciar un usuario del mismo tenant con `rol = profesional`, y NINGÚN usuario DEBE (SHALL) estar vinculado a más de un profesional. Un profesional sin `usuario_id` DEBE (SHALL) poder existir (por ejemplo, un profesional histórico o sin acceso al panel).

#### Scenario: Se crea un profesional sin usuario de login

- **WHEN** el dueño crea un profesional solo con `nombre` y sin `usuario_id`
- **THEN** el profesional queda persistido con `activo = true` y sin vínculo a usuario

#### Scenario: Se vincula un usuario profesional al profesional

- **WHEN** el dueño crea un profesional con el `usuario_id` de un usuario del mismo tenant con `rol = profesional`
- **THEN** el profesional queda persistido con ese vínculo

#### Scenario: Un usuario no puede ser dos profesionales

- **WHEN** el dueño intenta crear un segundo profesional con un `usuario_id` ya vinculado
- **THEN** la operación se rechaza con un error de dominio y no se crea una segunda fila

#### Scenario: Un usuario de recepción no puede ser profesional

- **WHEN** el dueño intenta vincular a un usuario con `rol = recepcion`
- **THEN** la operación se rechaza y no se crea el profesional

#### Scenario: Un usuario de otro tenant no puede vincularse

- **WHEN** el dueño envía el `usuario_id` de un usuario que pertenece a otro consultorio
- **THEN** la operación se rechaza como si el usuario no existiera y no se crea el profesional

### Requirement: El catálogo de profesionales es exclusivo del dueño (RN-AU-02)

El sistema DEBE (SHALL) permitir listar, crear y editar profesionales únicamente a un usuario con `rol = profesional` y `es_dueno = true`. Un usuario autenticado sin ese privilegio DEBE (SHALL) recibir HTTP 403 con el sobre de error de dominio, y una request sin autenticación DEBE (SHALL) recibir HTTP 401 antes de evaluar permisos.

#### Scenario: El dueño administra el catálogo

- **WHEN** un usuario con `rol = profesional` y `es_dueno = true` llama a `GET`, `POST` o `PATCH` de `/profesionales`
- **THEN** la request se procesa y la respuesta no es 401 ni 403

#### Scenario: La recepción no accede al catálogo

- **WHEN** un usuario con `rol = recepcion` intenta listar, crear o editar profesionales
- **THEN** la respuesta es HTTP 403 y no se crea ni modifica ningún profesional

#### Scenario: Un profesional sin flag no administra el catálogo

- **WHEN** un usuario con `rol = profesional` y `es_dueno = false` intenta crear o editar un profesional
- **THEN** la respuesta es HTTP 403 y no se crea ni modifica ningún profesional

#### Scenario: Sin token no se llega al catálogo

- **WHEN** un cliente sin token llama a cualquier ruta de `/profesionales`
- **THEN** la respuesta es HTTP 401

### Requirement: El profesional se desactiva y nunca se borra físicamente

El sistema NO DEBE (SHALL) exponer el borrado físico de profesionales. El dueño DEBE (SHALL) poder marcar un profesional como inactivo, y un profesional inactivo NO DEBE (SHALL) ofrecerse para nuevas asignaciones, aunque DEBE (SHALL) seguir siendo consultable para conservar el historial de turnos que lo referencian.

#### Scenario: Desactivar un profesional lo saca de los activos

- **WHEN** el dueño marca `activo = false` sobre un profesional y luego lista filtrando por `activo = true`
- **THEN** el profesional desactivado no aparece en el listado de activos pero sigue siendo consultable por su identificador

#### Scenario: No existe borrado físico de profesionales

- **WHEN** un cliente intenta `DELETE /profesionales/{id}`
- **THEN** la operación no está expuesta y el profesional no se elimina

### Requirement: El acceso a profesionales está aislado por tenant

El sistema DEBE (SHALL) impedir que una sesión de un consultorio lea o modifique profesionales de otro consultorio, sin depender de que cada consulta agregue el filtro manualmente (R3).

#### Scenario: Un consultorio no ve profesionales de otro

- **WHEN** desde el tenant A se lista el catálogo de profesionales y el tenant B también tiene profesionales
- **THEN** el resultado contiene únicamente profesionales del tenant A

#### Scenario: No se puede editar un profesional de otro tenant

- **WHEN** el dueño del tenant A intenta editar un profesional del tenant B por su identificador
- **THEN** la respuesta es HTTP 404 y el profesional del tenant B no cambia
