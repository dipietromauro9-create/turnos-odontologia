# Prestaciones Specification

## Purpose

Define el catálogo de prestaciones del consultorio: alta, consulta, edición y desactivación por parte del dueño, con una duración válida que queda congelada en cada turno al crearse, un precio de referencia informativo y aislamiento de datos por tenant.

## Requirements

### Requirement: La prestación declara una duración válida (RN-AG-03)

El sistema DEBE (SHALL) exigir que toda prestación tenga un `nombre` no vacío y una `duracion_min` entera mayor que cero y múltiplo de 5. Una duración inválida (cero, negativa o no múltiplo de 5) DEBE (SHALL) rechazarse con HTTP 422 y el sobre de error de dominio con código `RN-AG-03`, sin crear ni modificar la prestación. La restricción DEBE (SHALL) sostenerse también en la base de datos como última línea de defensa.

#### Scenario: Una duración múltiplo de 5 se acepta

- **WHEN** el dueño crea una prestación con `duracion_min` igual a 30
- **THEN** la prestación se crea con `duracion_min = 30` y `activa = true`

#### Scenario: Una duración no múltiplo de 5 se rechaza

- **WHEN** el dueño crea o edita una prestación con `duracion_min` igual a 33
- **THEN** la respuesta es HTTP 422 con código `RN-AG-03` y no se persiste el cambio

#### Scenario: Una duración no positiva se rechaza

- **WHEN** el dueño crea o edita una prestación con `duracion_min` igual a 0 o negativa
- **THEN** la respuesta es HTTP 422 con código `RN-AG-03` y no se persiste el cambio

### Requirement: El catálogo de prestaciones es exclusivo del dueño (RN-AU-02)

El sistema DEBE (SHALL) permitir crear, editar y desactivar prestaciones únicamente a un usuario con `rol = profesional` y `es_dueno = true` en las rutas de gestión `/prestaciones`. La recepción DEBE (SHALL) recibir HTTP 403 en todas las rutas de escritura del catálogo, y una request sin autenticación DEBE (SHALL) recibir HTTP 401 antes de evaluar permisos. Como excepción de solo lectura, la proyección de agenda (`core/agenda`) DEBE (SHALL) poder exponer a cualquier usuario autenticado del panel un subconjunto mínimo de las prestaciones activas del tenant —id, nombre, duración y estado activo— para armar turnos; esa proyección NUNCA DEBE (SHALL) habilitar la creación, edición ni desactivación del catálogo.

#### Scenario: El dueño administra el catálogo de prestaciones

- **WHEN** un usuario con `rol = profesional` y `es_dueno = true` llama a `GET`, `POST`, `PATCH` o a la desactivación de `/prestaciones`
- **THEN** la request se procesa y la respuesta no es 401 ni 403

#### Scenario: La recepción no configura prestaciones

- **WHEN** un usuario con `rol = recepcion` intenta crear, editar o desactivar una prestación
- **THEN** la respuesta es HTTP 403 y la prestación no cambia

#### Scenario: Un profesional sin flag no configura prestaciones

- **WHEN** un usuario con `rol = profesional` y `es_dueno = false` intenta crear o editar una prestación
- **THEN** la respuesta es HTTP 403 y la prestación no cambia

#### Scenario: Sin token no se llega al catálogo

- **WHEN** un cliente sin token llama a cualquier ruta de `/prestaciones`
- **THEN** la respuesta es HTTP 401

#### Scenario: La proyección de agenda no abre el catálogo

- **WHEN** un usuario con `rol = recepcion` arma un turno desde la agenda
- **THEN** recibe id, nombre y duración de las prestaciones activas, y cualquier escritura en `/prestaciones` le sigue respondiendo HTTP 403

### Requirement: Cambiar la duración de una prestación no altera turnos ya creados (RN-AG-03)

El sistema DEBE (SHALL) mantener la duración de cada turno congelada en su propio `fin`, calculado al crear el turno. Editar `duracion_min` en el catálogo DEBE (SHALL) modificar únicamente la fila de la prestación: NUNCA DEBE (SHALL) reescribir turnos existentes ni recalcular sus horarios, y la persistencia NO DEBE (SHALL) declarar cascadas de actualización que propaguen el cambio a turnos.

#### Scenario: Editar la duración solo actualiza el catálogo

- **WHEN** el dueño cambia `duracion_min` de 30 a 45 en una prestación existente
- **THEN** la prestación queda con `duracion_min = 45` y ninguna otra entidad del dominio cambia de valor

#### Scenario: La duración de un turno no se recalcula desde el catálogo

- **WHEN** un turno fue creado con una prestación de 30 minutos y luego la prestación pasa a 45 minutos
- **THEN** el `fin` del turno existente sigue siendo el calculado con 30 minutos; el nuevo valor solo aplica a turnos creados después

### Requirement: La prestación se desactiva sin borrado físico

El sistema NO DEBE (SHALL) exponer el borrado físico de prestaciones. El dueño DEBE (SHALL) poder desactivar una prestación, y una prestación inactiva NO DEBE (SHALL) ofrecerse para nuevas reservas, aunque DEBE (SHALL) seguir siendo consultable para conservar el historial de los turnos que la referencian. Desactivar una prestación ya inactiva DEBE (SHALL) ser una operación exitosa e idempotente.

#### Scenario: Desactivar una prestación la saca de las activas

- **WHEN** el dueño desactiva una prestación y luego lista filtrando por `activa = true`
- **THEN** la prestación desactivada no aparece en el listado de activas pero sigue siendo consultable por su identificador

#### Scenario: Desactivar dos veces no falla

- **WHEN** el dueño desactiva una prestación ya inactiva
- **THEN** la respuesta es exitosa y la prestación sigue con `activa = false`

#### Scenario: No existe borrado físico de prestaciones

- **WHEN** un cliente intenta `DELETE /prestaciones/{id}`
- **THEN** la operación no está expuesta y la prestación no se elimina

### Requirement: El precio de referencia es informativo y no interviene en el turno

El sistema DEBE (SHALL) aceptar un `precio_ref` opcional, no negativo, con hasta dos decimales, que NO DEBE (SHALL) participar en el cálculo de horarios, duraciones ni estados de turno. Cambiar `precio_ref` DEBE (SHALL) afectar únicamente a la prestación.

#### Scenario: Una prestación sin precio es válida

- **WHEN** el dueño crea una prestación sin `precio_ref`
- **THEN** la prestación se crea con `precio_ref` nulo

#### Scenario: El precio no altera la duración ni los turnos

- **WHEN** el dueño cambia `precio_ref` de una prestación existente
- **THEN** `duracion_min` no cambia y ningún turno existente se modifica

### Requirement: El acceso a prestaciones está aislado por tenant

El sistema DEBE (SHALL) impedir que una sesión de un consultorio lea o modifique prestaciones de otro consultorio, sin depender de que cada consulta agregue el filtro manualmente (R3).

#### Scenario: Un consultorio no ve prestaciones de otro

- **WHEN** desde el tenant A se lista el catálogo de prestaciones y el tenant B también tiene prestaciones
- **THEN** el resultado contiene únicamente prestaciones del tenant A

#### Scenario: No se puede editar una prestación de otro tenant

- **WHEN** el dueño del tenant A intenta editar o desactivar una prestación del tenant B por su identificador
- **THEN** la respuesta es HTTP 404 y la prestación del tenant B no cambia
