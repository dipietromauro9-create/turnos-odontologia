# Auth Specification

## Purpose

Define el ciclo de vida de la sesión del panel: cómo un usuario demuestra su identidad con Argon2id, cómo se emiten y rotan los tokens JWT, cómo se cierra la sesión, qué información expone la identidad actual, cómo se frena la fuerza bruta y qué rutas quedan fuera del JWT por ser públicas.

## Requirements

### Requirement: El panel exige una sesión JWT válida (RN-AU-01)

El sistema DEBE (SHALL) exigir un access token JWT válido y no expirado en toda ruta de panel, y DEBE (SHALL) rechazar con HTTP 401 cualquier request de panel sin token, con token mal firmado, con token expirado o con un token de tipo distinto a `access`. Las únicas rutas exentas de JWT son las que abren o cierran la sesión (`POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout`) y las declaradas públicas: `GET /health`, la documentación de la API y el turnero público bajo `/turnero/*` (RN-AU-01).

#### Scenario: Una ruta de panel sin token responde 401

- **WHEN** un cliente sin cabecera `Authorization` llama a `GET /auth/me`
- **THEN** la respuesta es HTTP 401 con el sobre de error de dominio (`code`, `message`) y no se devuelve ningún dato del usuario

#### Scenario: Un access token válido habilita la ruta de panel

- **WHEN** un cliente envía `Authorization: Bearer <access>` con un token vigente emitido por el login
- **THEN** la request se procesa con la identidad del usuario del token y la respuesta no es 401

#### Scenario: Un access token expirado se rechaza de forma distinguible

- **WHEN** un cliente usa un access token cuyo `exp` ya pasó
- **THEN** la respuesta es HTTP 401 y el cuerpo identifica el motivo de expiración para que el panel sepa que debe intentar `POST /auth/refresh`

#### Scenario: Un refresh token no sirve como access token

- **WHEN** un cliente envía en `Authorization: Bearer` un token cuyo claim `type` es `refresh`
- **THEN** la respuesta es HTTP 401 y la request no se procesa como autenticada

#### Scenario: Las rutas públicas siguen accesibles sin token

- **WHEN** un cliente sin token llama a `GET /health` o a una ruta del turnero público
- **THEN** la respuesta no es 401 porque esas rutas están exentas de JWT

### Requirement: El login verifica la contraseña con Argon2id y emite el par de tokens

El sistema DEBE (SHALL) autenticar `POST /auth/login` con email y contraseña, verificando la contraseña contra el `password_hash` Argon2id del usuario del tenant resuelto, y DEBE (SHALL) responder HTTP 200 con un access token en el cuerpo y un refresh token en una cookie `HttpOnly`, `Secure` y `SameSite=Lax`. Los tokens DEBEN (SHALL) llevar los claims `sub`, `tenant_id`, `roles`, `email`, `jti`, `type`, `iat` y `exp`; el access DEBE (SHALL) vencer a los `ACCESS_MINUTES` configurados (15 por defecto) y el refresh a los `REFRESH_DAYS` configurados (7 por defecto). Las credenciales inválidas, el email inexistente y el usuario inactivo DEBEN (SHALL) responder el mismo HTTP 401 sin revelar cuál de los tres casos ocurrió, y no DEBEN (SHALL) emitir cookie.

#### Scenario: Login correcto emite access y refresh

- **WHEN** un usuario activo envía su email y su contraseña correcta a `POST /auth/login`
- **THEN** la respuesta es HTTP 200 con un access token en el cuerpo y una cookie de refresh `HttpOnly`, `Secure` y `SameSite=Lax`, y ambos tokens incluyen `sub`, `tenant_id`, `roles`, `email`, `jti`, `type`, `iat` y `exp`

#### Scenario: Contraseña incorrecta no emite tokens

- **WHEN** un usuario activo envía su email con una contraseña incorrecta
- **THEN** la respuesta es HTTP 401 con el sobre de error de dominio y no se setea cookie de refresh

#### Scenario: Email inexistente responde igual que una contraseña incorrecta

- **WHEN** un cliente envía un email que no existe en el tenant resuelto
- **THEN** la respuesta es HTTP 401 con el mismo cuerpo y estado que una contraseña incorrecta, sin revelar que el email no existe

#### Scenario: Un usuario inactivo no puede iniciar sesión

- **WHEN** un usuario con `activo = false` envía credenciales correctas
- **THEN** la respuesta es HTTP 401 y no se emiten tokens

#### Scenario: Los tiempos de vida salen de la configuración

- **WHEN** la aplicación corre con `ACCESS_MINUTES=15` y `REFRESH_DAYS=7`
- **THEN** la diferencia entre `exp` e `iat` es de 15 minutos en el access y de 7 días en el refresh

### Requirement: El refresh rota el par de tokens e invalida el anterior

El sistema DEBE (SHALL) aceptar `POST /auth/refresh` únicamente con un refresh token válido, no expirado y no invalidado, y DEBE (SHALL) responder con un access nuevo y un refresh nuevo, invalidando el refresh presentado. Un refresh ya invalidado que se presente de nuevo DEBE (SHALL) responder HTTP 401 sin emitir tokens nuevos. Un refresh ausente, expirado o con firma inválida DEBE (SHALL) responder HTTP 401. El nuevo par DEBE (SHALL) conservar la misma identidad y el mismo `tenant_id` del token original.

#### Scenario: Un refresh válido devuelve un par nuevo

- **WHEN** un cliente presenta la cookie de refresh vigente en `POST /auth/refresh`
- **THEN** la respuesta es HTTP 200 con un access nuevo y una cookie de refresh nueva, y el refresh anterior deja de ser aceptado

#### Scenario: Reusar un refresh ya rotado responde 401

- **WHEN** un cliente presenta en `POST /auth/refresh` un refresh token que ya fue usado para rotar
- **THEN** la respuesta es HTTP 401 y no se emite ningún token nuevo

#### Scenario: El refresh sin cookie responde 401

- **WHEN** un cliente llama a `POST /auth/refresh` sin cookie de refresh
- **THEN** la respuesta es HTTP 401 y no se emite ningún token

#### Scenario: El refresh conserva la identidad y el tenant

- **WHEN** un refresh válido de un usuario del tenant resuelto se canjea por un par nuevo
- **THEN** el `sub` y el `tenant_id` de los tokens nuevos son los mismos que los del token original

### Requirement: El logout invalida el refresh y es idempotente

El sistema DEBE (SHALL) invalidar en `POST /auth/logout` el refresh token presentado y DEBE (SHALL) borrar la cookie de refresh. Después del logout, ese refresh NO DEBE (SHALL) poder canjearse. Llamar a logout sin cookie o repetirlo DEBE (SHALL) responder un resultado exitoso sin error, porque el cierre de sesión no debe depender de un token que el cliente ya descartó.

#### Scenario: Logout invalida el refresh vigente

- **WHEN** un cliente con cookie de refresh vigente llama a `POST /auth/logout` y luego intenta `POST /auth/refresh` con esa misma cookie
- **THEN** el logout responde exitosamente, la cookie se borra y el refresh posterior responde HTTP 401

#### Scenario: Logout repetido no falla

- **WHEN** un cliente llama a `POST /auth/logout` dos veces seguidas, o sin cookie de refresh
- **THEN** ambas respuestas son exitosas y no se devuelve error por token ausente o ya invalidado

### Requirement: La identidad actual expone solo datos del usuario autenticado

El sistema DEBE (SHALL) exponer `GET /auth/me` con el usuario derivado del access token: `id`, `tenant_id`, `nombre`, `email`, `rol` y `es_dueno`. La respuesta NUNCA DEBE (SHALL) incluir `password_hash` ni ningún otro secreto, y NUNCA DEBE (SHALL) devolver datos de un usuario de otro tenant.

#### Scenario: Me devuelve el usuario del token

- **WHEN** un usuario autenticado llama a `GET /auth/me`
- **THEN** la respuesta es HTTP 200 con su `id`, `tenant_id`, `nombre`, `email`, `rol` y `es_dueno`

#### Scenario: Me nunca expone el hash de la contraseña

- **WHEN** se inspecciona el cuerpo de `GET /auth/me`
- **THEN** no aparece `password_hash` ni ningún campo de credenciales

#### Scenario: Un usuario desactivado pierde el acceso

- **WHEN** un usuario con `activo = false` presenta un access token todavía vigente
- **THEN** la respuesta es HTTP 401 porque la sesión exige que el usuario siga activo

### Requirement: El login bloquea la cuenta tras diez intentos fallidos

El sistema DEBE (SHALL) contar los intentos de login fallidos por cuenta (tenant + usuario) y DEBE (SHALL) bloquear temporalmente el login de esa cuenta al llegar a 10 fallos consecutivos: incluso con la contraseña correcta, la respuesta DEBE (SHALL) ser un rechazo por bloqueo hasta que expire la ventana de bloqueo. Un login exitoso DEBE (SHALL) reiniciar el contador de fallos.

#### Scenario: El décimo fallo bloquea la cuenta

- **WHEN** una cuenta acumula 10 intentos de login fallidos consecutivos
- **THEN** el intento siguiente con la contraseña correcta es rechazado por bloqueo y no se emiten tokens

#### Scenario: El bloqueo expira y la cuenta vuelve a entrar

- **WHEN** la ventana de bloqueo de una cuenta bloqueada ya expiró y el usuario envía la contraseña correcta
- **THEN** el login es exitoso y el contador de fallos vuelve a cero

#### Scenario: Un login exitoso reinicia el contador

- **WHEN** una cuenta acumula 9 fallos y luego inicia sesión correctamente
- **THEN** el contador de fallos de esa cuenta queda en cero y hacen falta 10 fallos nuevos para bloquearla

### Requirement: El login limita la tasa de intentos por IP y email

El sistema DEBE (SHALL) limitar `POST /auth/login` a 5 requests por ventana de 60 segundos por combinación de IP de origen y email solicitado, y DEBE (SHALL) rechazar los intentos que excedan el límite sin verificar la contraseña. El rechazo por tasa DEBE (SHALL) ser distinguible del rechazo por credenciales y DEBE (SHALL) informar cuándo reintentar. El límite DEBE (SHALL) ser independiente del resultado del login: los intentos exitosos también consumen cuota.

#### Scenario: El sexto intento en un minuto se rechaza por tasa

- **WHEN** un mismo origen envía 5 intentos de login para el mismo email dentro de 60 segundos
- **THEN** el sexto intento es rechazado por límite de tasa, incluso si la contraseña es correcta

#### Scenario: El rechazo por tasa informa el reintento

- **WHEN** una request de login es rechazada por límite de tasa
- **THEN** la respuesta incluye un encabezado o campo que indica cuánto falta para reintentar

#### Scenario: Otro email no consume la cuota del primero

- **WHEN** un mismo origen agota la cuota de login para un email y luego intenta con otro email
- **THEN** el intento con el segundo email no se rechaza por la cuota del primero

### Requirement: El turnero público opera sin JWT con código por turno (RN-AU-01)

El sistema DEBE (SHALL) mantener el turnero público fuera del esquema JWT: sus rutas se autentican por `codigo_publico` por turno y no por sesión de panel. Las rutas del turnero NUNCA DEBEN (SHALL) exponer datos de pacientes ni requerir una cuenta, y su límite de tasa propio (10 req/min por IP) se especifica en el change del turnero. C-03 DEBE (SHALL) dejar el mecanismo de exención explícito y acotado, de modo que agregar una ruta al panel sin protección sea un error detectable y no un olvido silencioso.

#### Scenario: El turnero no requiere sesión de panel

- **WHEN** un cliente sin token llama a una ruta bajo `/turnero/*`
- **THEN** la request no es rechazada por falta de JWT

#### Scenario: La exención no cubre rutas de panel

- **WHEN** se agrega una ruta de panel que no está declarada como pública
- **THEN** la ruta exige JWT por defecto, sin necesidad de declarar nada

#### Scenario: El turnero no expone datos de pacientes

- **WHEN** un cliente consulta una ruta pública del turnero
- **THEN** la respuesta contiene únicamente información de disponibilidad o del turno identificado por `codigo_publico`, nunca datos personales de otros pacientes
