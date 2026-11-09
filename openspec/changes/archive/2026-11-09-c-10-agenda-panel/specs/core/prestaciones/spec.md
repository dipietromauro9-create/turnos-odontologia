# Spec Delta

## MODIFIED Requirements

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
