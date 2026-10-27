# Tenancy Specification

## Purpose

Define la identidad del consultorio y de sus usuarios, resuelve el tenant de cada request y garantiza que ningún acceso a datos pueda leer o escribir filas de otro tenant.

## Requirements

### Requirement: El tenant tiene un slug único e inmutable

El sistema DEBE (SHALL) identificar cada tenant por un `id` UUID y un `slug` no vacío, único en toda la base y que no puede modificarse una vez creado.

#### Scenario: Dos tenants no pueden compartir slug

- **WHEN** se intenta crear un segundo tenant con el mismo `slug` que uno existente
- **THEN** la operación falla y el tenant original queda sin cambios (violación de unicidad reportada como error, nunca como 500 genérico)

#### Scenario: El slug no cambia después de crear el tenant

- **WHEN** se intenta actualizar el `slug` de un tenant existente
- **THEN** la operación se rechaza y el valor persistido sigue siendo el original

### Requirement: El email del usuario es único por tenant sin distinguir mayúsculas

El sistema DEBE (SHALL) garantizar que, dentro de un mismo tenant, dos usuarios no puedan compartir el mismo email comparado de forma case-insensitive; el mismo email SÍ puede existir en tenants distintos.

#### Scenario: Email duplicado en el mismo tenant se rechaza

- **WHEN** se crea un usuario con un email que ya existe en su tenant, ignorando mayúsculas/minúsculas (por ejemplo `Dueno@Demo` frente a `dueno@demo`)
- **THEN** la creación falla por violación de unicidad y no se inserta una segunda fila

#### Scenario: El mismo email puede existir en otro tenant

- **WHEN** se crea un usuario con un email que ya existe en un tenant diferente
- **THEN** la creación tiene éxito y cada usuario queda asociado a su propio tenant

### Requirement: Solo un usuario profesional puede ser dueño

El sistema DEBE (SHALL) aceptar `es_dueno = true` únicamente cuando el usuario tiene `rol = profesional`, y DEBE (SHALL) rechazar en la base cualquier fila que viole esa combinación (RN-AU-02).

#### Scenario: Profesional dueño es válido

- **WHEN** se crea un usuario con `rol = profesional` y `es_dueno = true`
- **THEN** la fila se persiste correctamente

#### Scenario: Recepción no puede ser dueño

- **WHEN** se intenta crear o actualizar un usuario con `rol = recepcion` y `es_dueno = true`
- **THEN** la base rechaza la escritura por violación de constraint y no queda ninguna fila con esa combinación

### Requirement: Toda request de dominio opera dentro de un tenant resuelto

El sistema DEBE (SHALL) resolver el tenant de cada request antes de abrir la sesión de datos. En v1 solo existe el tenant configurado en `TENANT_DEFAULT_SLUG`; no hay selector de tenant por cliente. La sesión de datos de una request DEBE (SHALL) quedar asociada al `tenant_id` resuelto, y una request de dominio sin tenant resuelto DEBE (SHALL) fallar en lugar de consultar sin filtro.

#### Scenario: La request usa el tenant por defecto configurado

- **WHEN** llega una request de dominio con `TENANT_DEFAULT_SLUG=demo` y existe el tenant `demo`
- **THEN** la sesión de esa request queda asociada al `tenant_id` de `demo` y toda consulta de dominio se ejecuta bajo ese tenant

#### Scenario: La request de dominio no puede ejecutar sin tenant

- **WHEN** una request de dominio intenta abrir una sesión de datos sin tenant resuelto
- **THEN** el acceso falla explícitamente antes de ejecutar la consulta, en lugar de devolver datos de todos los tenants

#### Scenario: El health check sigue siendo público y sin tenant

- **WHEN** un cliente no autenticado llama a `GET /health`
- **THEN** la respuesta es 200 sin requerir tenant ni autenticación

### Requirement: El acceso a datos está aislado por tenant

El sistema DEBE (SHALL) impedir que una sesión asociada a un tenant lea o escriba filas de otro tenant, sin depender de que cada consulta agregue el filtro manualmente.

#### Scenario: Una consulta no devuelve filas de otro tenant

- **WHEN** existen usuarios o tenants en dos tenants distintos y se consultan usuarios desde la sesión del tenant A
- **THEN** el resultado contiene únicamente filas del tenant A; las filas del tenant B no aparecen

#### Scenario: Una escritura no puede asignar filas a otro tenant

- **WHEN** desde la sesión del tenant A se intenta insertar o actualizar una fila con `tenant_id` del tenant B
- **THEN** la operación se rechaza y la transacción no persiste el cambio

#### Scenario: La consulta de sistema queda limitada a la resolución de tenants

- **WHEN** el código de la aplicación necesita resolver el slug del tenant antes de abrir una sesión tenant-scoped
- **THEN** solo puede hacerlo mediante un acceso de sistema explícito y acotado a la tabla de tenants, no mediante una sesión de dominio

### Requirement: El seed demo es idempotente

El sistema DEBE (SHALL) proveer un seed reproducible que cree el tenant `demo`, un usuario `dueno@demo` (`rol = profesional`, `es_dueno = true`, `activo`) y un usuario `recepcion@demo` (`rol = recepcion`, `es_dueno = false`, `activo`), usando solo datos ficticios (R9). Ejecutar el seed más de una vez DEBE (SHALL) dejar exactamente el mismo estado, sin duplicados ni sobreescrituras.

#### Scenario: El seed crea el escenario demo en una base vacía

- **WHEN** se ejecuta el seed sobre una base migrada sin datos
- **THEN** existen el tenant `demo` y los usuarios `dueno@demo` y `recepcion@demo` con los roles y flags esperados

#### Scenario: Reejecutar el seed no duplica ni altera datos

- **WHEN** se ejecuta el seed por segunda vez sobre la misma base
- **THEN** sigue habiendo un solo tenant `demo` y un solo usuario por email, con los mismos valores que en la primera ejecución

#### Scenario: El seed no contiene datos de pacientes reales

- **WHEN** se inspeccionan los datos creados por el seed
- **THEN** solo hay datos ficticios de tenant y usuarios; no se crean pacientes ni datos personales reales (R9)
