# Spec Delta

## MODIFIED Requirements

### Requirement: El catálogo de profesionales es exclusivo del dueño (RN-AU-02)

El sistema DEBE (SHALL) permitir listar, crear y editar profesionales únicamente a un usuario con `rol = profesional` y `es_dueno = true` en las rutas de gestión `/profesionales`. Un usuario autenticado sin ese privilegio DEBE (SHALL) recibir HTTP 403 con el sobre de error de dominio, y una request sin autenticación DEBE (SHALL) recibir HTTP 401 antes de evaluar permisos. Como excepción de solo lectura, la proyección de agenda (`core/agenda`) DEBE (SHALL) poder exponer a cualquier usuario autenticado del panel un subconjunto mínimo de los profesionales activos del tenant —id, nombre, especialidad y estado activo— para columnas y filtros; esa proyección NUNCA DEBE (SHALL) habilitar la creación, edición ni desactivación del catálogo, ni cambiar los permisos de las rutas de gestión.

#### Scenario: El dueño administra el catálogo

- **WHEN** un usuario con `rol = profesional` y `es_dueno = true` llama a `GET`, `POST` o `PATCH` de `/profesionales`
- **THEN** la request se procesa y la respuesta no es 401 ni 403

#### Scenario: La recepción no accede al catálogo

- **WHEN** un usuario con `rol = recepcion` intenta listar, crear o editar profesionales en `/profesionales`
- **THEN** la respuesta es HTTP 403 y no se crea ni modifica ningún profesional

#### Scenario: Un profesional sin flag no administra el catálogo

- **WHEN** un usuario con `rol = profesional` y `es_dueno = false` intenta crear o editar un profesional
- **THEN** la respuesta es HTTP 403 y no se crea ni modifica ningún profesional

#### Scenario: Sin token no se llega al catálogo

- **WHEN** un cliente sin token llama a cualquier ruta de `/profesionales`
- **THEN** la respuesta es HTTP 401

#### Scenario: La proyección de agenda no abre la gestión

- **WHEN** un usuario con `rol = recepcion` consulta la agenda
- **THEN** recibe id, nombre, especialidad y estado de los profesionales activos para armar la vista, y `GET`, `POST` o `PATCH` de `/profesionales` le siguen respondiendo HTTP 403
