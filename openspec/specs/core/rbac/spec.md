# RBAC Specification

## Purpose

Define quién puede hacer qué dentro del panel: la matriz de permisos de roles, el rechazo por defecto de toda ruta que no declare roles, la distinción entre dueño y profesional y el alcance del profesional sobre su propia agenda y sus propios pacientes.

## Requirements

### Requirement: Toda ruta de panel declara los roles habilitados y se rechaza por defecto

El sistema DEBE (SHALL) exigir que cada ruta de panel declare explícitamente qué roles pueden usarla, y DEBE (SHALL) negar el acceso a toda ruta de panel que no haya declarado roles. La autorización DEBE (SHALL) ocurrir en el backend en cada request, sin depender de que el frontend oculte opciones. Un usuario autenticado con un rol no habilitado DEBE (SHALL) recibir HTTP 403 con el sobre de error de dominio; un usuario no autenticado DEBE (SHALL) recibir HTTP 401 antes de evaluar roles.

#### Scenario: Un rol no habilitado recibe 403

- **WHEN** un usuario autenticado con rol `recepcion` llama a una ruta de panel que solo habilita al profesional dueño
- **THEN** la respuesta es HTTP 403 con el sobre de error de dominio y el efecto de la operación no ocurre

#### Scenario: Un rol habilitado accede

- **WHEN** un usuario autenticado con el rol habilitado llama a una ruta de panel
- **THEN** la request se procesa y la respuesta no es 403

#### Scenario: Sin autenticación el rechazo es 401 y no 403

- **WHEN** un cliente sin token llama a una ruta de panel que declara roles
- **THEN** la respuesta es HTTP 401, porque primero se resuelve la identidad y solo después los permisos

#### Scenario: Una ruta sin roles declarados no pasa la verificación

- **WHEN** se agrega una ruta de panel sin declarar roles habilitados
- **THEN** la verificación automática de arquitectura falla y la ruta no se considera entregable, de modo que olvidar la declaración falla cerrado en lugar de abrir la ruta

### Requirement: La recepción nunca accede a configuración, usuarios ni exports (RN-AU-02)

El sistema DEBE (SHALL) negar a todo usuario con `rol = recepcion` el acceso a las rutas de configuración (prestaciones, horarios, parámetros del consultorio), de usuarios y de exportación de datos, sin importar el flag `es_dueno`. La recepción SÍ DEBE (SHALL) poder operar la agenda de todos los profesionales, la cola de recordatorios y las fichas de pacientes según la matriz de `03_actores_y_roles.md`.

#### Scenario: Recepción recibe 403 en configuración

- **WHEN** un usuario con `rol = recepcion` llama a una ruta de configuración de prestaciones u horarios
- **THEN** la respuesta es HTTP 403 y la configuración no cambia

#### Scenario: Recepción recibe 403 en usuarios

- **WHEN** un usuario con `rol = recepcion` llama a una ruta de gestión de usuarios
- **THEN** la respuesta es HTTP 403 y no se crea ni modifica ningún usuario

#### Scenario: Recepción recibe 403 en exportación

- **WHEN** un usuario con `rol = recepcion` llama a una ruta de exportación de datos
- **THEN** la respuesta es HTTP 403 y no se genera ningún archivo

#### Scenario: Recepción sí opera la agenda completa

- **WHEN** un usuario con `rol = recepcion` consulta la agenda de cualquier profesional del consultorio
- **THEN** la respuesta es exitosa y no es 403

### Requirement: El dueño es un flag sobre el profesional (DD-08)

El sistema DEBE (SHALL) considerar dueño únicamente a un usuario que cumpla simultáneamente `rol = profesional` y `es_dueno = true`. Las rutas de dueño DEBEN (SHALL) exigir ambas condiciones: un flag verdadero sin rol profesional NO DEBE (SHALL) conceder permisos, y un profesional sin el flag NO DEBE (SHALL) acceder a rutas de dueño. Un usuario con rol `recepcion` NUNCA DEBE (SHALL) ser tratado como dueño.

#### Scenario: El profesional dueño accede a las rutas de dueño

- **WHEN** un usuario con `rol = profesional` y `es_dueno = true` llama a una ruta exclusiva de dueño
- **THEN** la request se procesa y la respuesta no es 403

#### Scenario: El profesional sin flag recibe 403

- **WHEN** un usuario con `rol = profesional` y `es_dueno = false` llama a una ruta exclusiva de dueño
- **THEN** la respuesta es HTTP 403 y la operación no se ejecuta

#### Scenario: Un flag de dueño sobre recepción no concede permisos

- **WHEN** un usuario con `rol = recepcion` y `es_dueno = true` llama a una ruta exclusiva de dueño
- **THEN** la respuesta es HTTP 403, porque el flag solo vale combinado con el rol profesional

### Requirement: El profesional solo accede a su propia agenda y a sus propios pacientes salvo que sea dueño (RN-AU-03)

El sistema DEBE (SHALL) restringir al usuario con `rol = profesional` y `es_dueno = false` a los recursos vinculados a su propia identidad: su agenda y las fichas de sus pacientes. Cuando intente leer o modificar un recurso de otro profesional DEBE (SHALL) recibir HTTP 403. El profesional dueño DEBE (SHALL) acceder a los recursos de todos los profesionales del consultorio. La recepción DEBE (SHALL) acceder a la agenda de todos, sin acceder a configuración, usuarios ni exports (RN-AU-02).

#### Scenario: Un profesional no ve la agenda de otro profesional

- **WHEN** un usuario con `rol = profesional` y `es_dueno = false` consulta la agenda de otro profesional del mismo consultorio
- **THEN** la respuesta es HTTP 403 y no se devuelve la agenda ajena

#### Scenario: Un profesional ve su propia agenda

- **WHEN** un usuario con `rol = profesional` y `es_dueno = false` consulta su propia agenda
- **THEN** la respuesta es exitosa y contiene únicamente sus propios turnos

#### Scenario: Un profesional no ve fichas de pacientes de otro profesional

- **WHEN** un usuario con `rol = profesional` y `es_dueno = false` intenta leer la ficha de un paciente de otro profesional
- **THEN** la respuesta es HTTP 403 y no se devuelven datos de la ficha

#### Scenario: El dueño ve las agendas de todos

- **WHEN** un usuario con `rol = profesional` y `es_dueno = true` consulta la agenda de cualquier profesional del consultorio
- **THEN** la respuesta es exitosa y no es 403

#### Scenario: La recepción ve las agendas de todos

- **WHEN** un usuario con `rol = recepcion` consulta la agenda de cualquier profesional del consultorio
- **THEN** la respuesta es exitosa y no es 403

### Requirement: La autorización usa la identidad del token y el tenant resuelto, nunca datos del cliente

El sistema DEBE (SHALL) derivar el rol, el flag de dueño, el usuario y el tenant exclusivamente del token validado y del tenant resuelto para la request. El sistema NUNCA DEBE (SHALL) aceptar un `rol`, un `es_dueno` o un `tenant_id` enviados en el cuerpo, en la query o en cabeceras del cliente para decidir permisos, y DEBE (SHALL) rechazar un token cuyo `tenant_id` no coincida con el tenant resuelto.

#### Scenario: Un rol enviado por el cliente se ignora

- **WHEN** un usuario con `rol = recepcion` envía en el cuerpo de la request un campo que declara rol de dueño
- **THEN** la autorización sigue usando el rol del token y la respuesta es HTTP 403 si la ruta es de dueño

#### Scenario: Un token de otro tenant se rechaza

- **WHEN** un cliente presenta un token válido emitido para un `tenant_id` distinto del tenant resuelto para la request
- **THEN** la respuesta es HTTP 401 o 403 y no se accede a ningún dato del consultorio
