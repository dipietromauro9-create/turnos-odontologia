# Frontend Shell Specification

## Purpose

Brinda el shell de frontend ejecutable sobre el que construyen todas las funcionalidades siguientes: un cliente API tipado, guardianes de rutas públicas/privadas y una compuerta estricta de TypeScript que rechaza código sin tipos desde el día uno.

## Requirements

### Requirement: El cliente API base maneja el sobre y la auth

El shell DEBE (SHALL) proveer un único cliente HTTP tipado apuntado a la URL base del backend tomada del entorno, que envía JSON, parsea el sobre de errores de dominio (`code: RN-XX-NN`) y adjunta la credencial de auth (cableado de JWT / codigo_publico que se completa en C-03/C-09) desde un solo lugar.

#### Scenario: La petición fallida propaga el código de regla

- **WHEN** el backend responde con un sobre de error de dominio
- **THEN** el cliente propaga el `code` al llamante en lugar de un error genérico de red

#### Scenario: La URL base viene del entorno

- **WHEN** la app se construye con la variable de URL de API definida
- **THEN** todas las peticiones apuntan a esa URL base sin hosts hardcodeados en el código de features

### Requirement: El router separa rutas públicas y privadas

El shell DEBE (SHALL) definir una tabla de rutas con una rama pública (sin login; las páginas del turnero caen acá en C-09) y una rama privada que requiere autenticación (las páginas del panel caen acá en C-10), redirigiendo las visitas no autenticadas a la rama privada hacia un login provisorio.

#### Scenario: La ruta pública renderiza sin login

- **WHEN** un visitante anónimo abre una ruta pública
- **THEN** la página renderiza sin ninguna redirección de auth

#### Scenario: La ruta privada protege a anónimos

- **WHEN** un visitante anónimo abre una ruta privada
- **THEN** el router redirige a la entrada de login en lugar de renderizar contenido protegido

### Requirement: Compuerta estricta de TypeScript sin any

El shell DEBE (SHALL) compilar bajo TypeScript estricto (modo strict activado, `any` prohibido por lint) para que el código sin tipos falle el CI desde el primer change (R2).

#### Scenario: El código sin tipos falla la compuerta

- **WHEN** un archivo fuente usa `any` (explícito o implícito)
- **THEN** el typecheck/lint falla y el CI bloquea el change

#### Scenario: El shell renderiza la prueba de humo

- **WHEN** corre la suite de tests del frontend
- **THEN** el componente raíz del shell renderiza sin romperse
