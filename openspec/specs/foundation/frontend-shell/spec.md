# Frontend Shell Specification

## Purpose

Brinda el shell de frontend ejecutable sobre el que construyen todas las funcionalidades siguientes: un cliente API tipado, guardianes de rutas públicas/privadas y una compuerta estricta de TypeScript que rechaza código sin tipos desde el día uno.

## Requirements

### Requirement: El cliente API base maneja el sobre y la auth

El shell DEBE (SHALL) proveer un único cliente HTTP tipado apuntado a la URL base del backend tomada del entorno, que envía JSON, parsea el sobre de errores de dominio (`code: RN-XX-NN`) y adjunta la credencial de auth desde un solo lugar. El access token DEBE (SHALL) guardarse en el almacenamiento local versionado del shell y adjuntarse como `Authorization: Bearer` en toda request de panel. Cuando una request de panel responde 401 por access expirado o inválido y existe un refresh válido en la cookie `HttpOnly`, el cliente DEBE (SHALL) reintentar la operación una sola vez tras `POST /auth/refresh`; si el refresh falla, DEBE (SHALL) limpiar la sesión y redirigir al login. Un 401 de credenciales inválidas en `POST /auth/login` NUNCA DEBE (SHALL) disparar un refresh. Las requests a `/auth/refresh` y `/auth/logout` DEBEN (SHALL) enviar la cookie de refresh.

#### Scenario: La petición fallida propaga el código de regla

- **WHEN** el backend responde con un sobre de error de dominio
- **THEN** el cliente propaga el `code` al llamante en lugar de un error genérico de red

#### Scenario: La URL base viene del entorno

- **WHEN** la app se construye con la variable de URL de API definida
- **THEN** todas las peticiones apuntan a esa URL base sin hosts hardcodeados en el código de features

#### Scenario: El access vencido se refresca una vez

- **WHEN** una request de panel responde 401 por access vencido y la cookie de refresh es válida
- **THEN** el cliente renueva el access con `/auth/refresh` y repite la operación original una sola vez

#### Scenario: El refresh inválido devuelve al login

- **WHEN** el refresh también es rechazado
- **THEN** el cliente limpia el access local y la aplicación redirige al login sin repetir en bucle

#### Scenario: Credenciales inválidas no disparan refresh

- **WHEN** el usuario envía credenciales incorrectas en el login
- **THEN** la respuesta 401 se muestra como error de login y no se llama a `/auth/refresh`

### Requirement: El router separa rutas públicas y privadas

El shell DEBE (SHALL) definir una tabla de rutas con una rama pública (el turnero, sin login) y una rama privada que requiere autenticación. La rama privada DEBE (SHALL) exigir una sesión válida y redirigir a la pantalla de login real cuando no la haya. El login DEBE (SHALL) autenticar con `POST /auth/login`, guardar el access token y cargar `GET /auth/me` para obtener `rol` y `es_dueno`. La navegación del panel DEBE (SHALL) mostrar u ocultar secciones según el rol: recepción no ve configuración ni reportes exclusivos del dueño, y el profesional sin flag solo accede a su propia agenda. El logout DEBE (SHALL) invocar `POST /auth/logout`, limpiar la sesión y volver al login.

#### Scenario: La ruta pública renderiza sin login

- **WHEN** un visitante anónimo abre una ruta pública
- **THEN** la página renderiza sin ninguna redirección de auth

#### Scenario: La ruta privada protege a anónimos

- **WHEN** un visitante anónimo abre una ruta privada
- **THEN** el router redirige al login real en lugar de renderizar contenido protegido

#### Scenario: Login exitoso carga la identidad

- **WHEN** el usuario ingresa credenciales válidas
- **THEN** el shell guarda el access, obtiene rol y `es_dueno` desde `/auth/me` y entra a la agenda

#### Scenario: La navegación depende del rol

- **WHEN** inicia sesión un usuario con `rol = recepcion`
- **THEN** la navegación no muestra las secciones de configuración exclusivas del dueño

#### Scenario: Logout limpia la sesión

- **WHEN** el usuario cierra sesión
- **THEN** se invalida el refresh en el backend, se limpia el access local y se vuelve al login

### Requirement: Compuerta estricta de TypeScript sin any

El shell DEBE (SHALL) compilar bajo TypeScript estricto (modo strict activado, `any` prohibido por lint) para que el código sin tipos falle el CI desde el primer change (R2).

#### Scenario: El código sin tipos falla la compuerta

- **WHEN** un archivo fuente usa `any` (explícito o implícito)
- **THEN** el typecheck/lint falla y el CI bloquea el change

#### Scenario: El shell renderiza la prueba de humo

- **WHEN** corre la suite de tests del frontend
- **THEN** el componente raíz del shell renderiza sin romperse
