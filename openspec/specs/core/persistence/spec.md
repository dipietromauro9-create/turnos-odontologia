# Persistence Specification

## Purpose

Brinda el contrato común de persistencia del dominio: modelos con `tenant_id` y timestamps, un repositorio que siempre opera dentro del tenant de la sesión y una unidad de trabajo que hace atómicas las operaciones de negocio.

## Requirements

### Requirement: Todo modelo de dominio declara tenant y timestamps

El sistema DEBE (SHALL) proveer mixins reutilizables para que cada modelo de dominio declare `tenant_id` como FK obligatoria al tenant, con índices compuestos que empiecen por `tenant_id`, y timestamps `creado_en`/`actualizado_en` con zona horaria.

#### Scenario: Un modelo de dominio no puede existir sin tenant

- **WHEN** se inspecciona la metadata de un modelo que usa el mixin de tenant
- **THEN** la columna `tenant_id` es NOT NULL, referencia la tabla `tenant` y participa en los índices compuestos del modelo

#### Scenario: Los timestamps son siempre con zona horaria

- **WHEN** se persiste una fila con los mixins de auditoría
- **THEN** `creado_en` y `actualizado_en` son `timestamptz` con valor no nulo, y `actualizado_en` avanza al modificar la fila

### Requirement: El repositorio base siempre respeta el tenant de la sesión

El sistema DEBE (SHALL) ofrecer un repositorio genérico reutilizable que reciba únicamente una sesión tenant-scoped y que aplique la frontera de tenant en todas sus operaciones de lectura y escritura, para que un repositorio de dominio no pueda olvidar el filtro (R3).

#### Scenario: Listar y obtener solo devuelven filas del tenant de la sesión

- **WHEN** un repositorio construido sobre la sesión del tenant A lista u obtiene entidades que también existen en el tenant B
- **THEN** solo devuelve las entidades del tenant A y una búsqueda por id de una entidad del tenant B no devuelve resultado

#### Scenario: Crear desde un repositorio asigna el tenant de la sesión

- **WHEN** un repositorio crea una entidad sin especificar `tenant_id`
- **THEN** la entidad queda persistida con el `tenant_id` de la sesión, sin posibilidad de elegir otro tenant

#### Scenario: No se puede construir un repositorio sin sesión tenant-scoped

- **WHEN** se intenta construir el repositorio base con una sesión que no tiene tenant asociado
- **THEN** la construcción falla explícitamente en lugar de operar sin filtro

### Requirement: Las operaciones de negocio son atómicas

El sistema DEBE (SHALL) proveer una unidad de trabajo que agrupe varias escrituras en una sola transacción: si cualquier paso falla, no queda ningún cambio parcial visible (RN-GL-02). El commit DEBE (SHALL) ocurrir una sola vez, al cerrar exitosamente la unidad de trabajo.

#### Scenario: Un fallo intermedio revierte todo el grupo

- **WHEN** una unidad de trabajo realiza dos inserciones y la segunda falla
- **THEN** la transacción se revierte y ninguna de las dos filas queda persistida

#### Scenario: Un cierre exitoso persiste todo el grupo

- **WHEN** una unidad de trabajo realiza varias escrituras válidas y termina sin errores
- **THEN** todas las escrituras quedan visibles juntas después del commit

#### Scenario: La unidad de trabajo no deja estados intermedios visibles

- **WHEN** otra sesión consulta los datos mientras la unidad de trabajo aún no commiteó
- **THEN** no ve las escrituras parciales; solo las ve después del commit exitoso

### Requirement: La zona horaria de persistencia es única

El sistema DEBE (SHALL) persistir y leer los instantes en la zona `America/Argentina/Buenos_Aires` (RN-GL-03), usando exclusivamente tipos con zona horaria (`timestamptz`) y rechazando valores naive en los bordes de la aplicación.

#### Scenario: La conexión de base de datos usa la zona del sistema

- **WHEN** se abre una sesión de base de datos de la aplicación
- **THEN** la zona horaria efectiva de la sesión es `America/Argentina/Buenos_Aires`

#### Scenario: Un datetime naive se rechaza en el borde

- **WHEN** un datetime sin zona horaria intenta entrar a un schema o servicio de dominio validado
- **THEN** el sistema lo rechaza con un error de validación en lugar de persistirlo como naive
