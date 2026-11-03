# Spec Delta — core/tenancy

## MODIFIED Requirements

### Requirement: El seed demo es idempotente

El sistema DEBE (SHALL) proveer un seed reproducible que cree el tenant `demo`, un usuario `dueno@demo` (`rol = profesional`, `es_dueno = true`, `activo`) y un usuario `recepcion@demo` (`rol = recepcion`, `es_dueno = false`, `activo`), y que pueda extender el escenario demo con filas ficticias de catálogo (profesionales, prestaciones, disponibilidad y demás entidades de los changes de agenda), usando exclusivamente datos ficticios (R9). Ejecutar el seed más de una vez DEBE (SHALL) dejar exactamente el mismo estado, sin duplicados ni sobreescrituras, y NUNCA DEBE (SHALL) contener datos reales de pacientes.

#### Scenario: El seed crea el escenario demo en una base vacía

- **WHEN** se ejecuta el seed sobre una base migrada sin datos
- **THEN** existen el tenant `demo` y los usuarios `dueno@demo` y `recepcion@demo` con los roles y flags esperados

#### Scenario: Reejecutar el seed no duplica ni altera datos

- **WHEN** se ejecuta el seed por segunda vez sobre la misma base
- **THEN** sigue habiendo un solo tenant `demo`, un solo usuario por email y una sola fila por cada entidad de catálogo sembrada, con los mismos valores que en la primera ejecución

#### Scenario: El seed no contiene datos de pacientes reales

- **WHEN** se inspeccionan los datos creados por el seed
- **THEN** todos los datos son ficticios y no se crea ningún dato personal real de pacientes (R9)

#### Scenario: El seed tolera que una entidad de otro change todavía no exista

- **WHEN** el seed se ejecuta antes de que exista la tabla de disponibilidad de C-06
- **THEN** el seed crea el resto del escenario demo, omite el bloque de disponibilidad sin fallar y queda listo para sembrarlo en una ejecución posterior
