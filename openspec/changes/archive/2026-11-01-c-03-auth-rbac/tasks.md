# Tareas

Ciclo estricto: cada bloque de implementación empieza con un test que falla (rojo), sigue con la implementación mínima que lo pone en verde, y cierra triangulando casos borde y refactorizando. Los escenarios de `specs/core/auth` y `specs/core/rbac` son los criterios de aceptación.

**Prerrequisitos de C-02 (ya archivado, no se reimplementan):** `TenantContextMiddleware` + `get_session()` tenant-scoped en `backend/app/db/session.py`, `Usuario` con `password_hash`/`rol`/`es_dueno`/`activo` en `backend/app/db/models/usuario.py`, `BaseRepository`/`UnitOfWork` en `backend/app/domain/persistence.py`, seed Argon2id en `backend/app/db/seed.py`, harness `backend/tests/conftest.py` y migración `0002_tenancy_usuario`. **Este change no agrega migración** (el estado de seguridad vive en Redis).

## 1. Dependencias y preparación del harness

- [x] 1.1 Obtener la aprobación explícita del usuario (U3) para instalar `pyjwt`, agregarla a las dependencias de `backend/pyproject.toml` con la justificación del design, y verificar que `uv sync --group dev` resuelve y que `uv run python -c "import jwt; print(jwt.__version__)"` funciona
- [x] 1.2 Agregar el servicio `redis:7` con healthcheck y la variable `REDIS_URL` al job `backend` de `.github/workflows/ci.yml`, y verificar que el YAML parsea (`python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/ci.yml'))"`) y que `uv run pytest -q -m integration` corre localmente con Compose
- [x] 1.3 Extender `backend/tests/factories.py` con `crear_usuario_con_password(session, tenant, email, password, rol=..., es_dueno=...)` que hashee con `app.core.security.hash_password`, y verificar con un test que `verify_password` acepta ese hash y rechaza una contraseña distinta (hoy `PASSWORD_FICTICIO` no es un hash Argon2 válido)

## 2. Primitivas de seguridad

- [x] 2.1 Escribir primero en rojo `backend/tests/test_security.py`: `hash_password` produce hashes Argon2id distintos para la misma contraseña (salt) y `verify_password` acepta la correcta y rechaza la incorrecta; `crear_token` emite los claims `sub, tenant_id, roles, email, jti, type, iat, exp` con `exp - iat` igual a `ACCESS_MINUTES`/`REFRESH_DAYS`; `decodificar_token` rechaza firma inválida, token expirado, `type` inesperado y token sin los claims requeridos. Correr `uv run pytest tests/test_security.py` y confirmar el fallo porque el módulo no existe
- [x] 2.2 Implementar `backend/app/core/security.py` (`PasswordHasher` de Argon2id reutilizado, `hash_password`, `verify_password` con hash ficticio de tiempo constante, `crear_token`, `decodificar_token` con `algorithms=["HS256"]` y claims requeridos) y verificar que los tests de 2.1 pasan
- [x] 2.3 Triangular rechazo de `alg: none`, `jti` único entre dos tokens emitidos en el mismo segundo, y `decodificar_token` distinguiendo expiración de firma inválida en el motivo del error; verificar los tests nuevos y refactorizar el manejo de errores de `jwt`

## 3. Estado efímero de seguridad (lockout, rate limit, blacklist)

- [x] 3.1 Escribir primero en rojo `backend/tests/test_token_store.py` contra `InMemoryTokenStore` con reloj inyectable: 9 fallos no bloquean y el 10.º bloquea; `esta_bloqueado` es verdadero dentro de la ventana y falso al avanzar el reloj; un login exitoso (`limpiar_fallos`) reinicia el contador; `consumir_cuota` acepta 5 requests de la misma IP+email en 60 s y rechaza la 6.ª con los segundos restantes; la cuota de un email no afecta a otro; `revocar` + `esta_revocado` respeta el TTL del `jti`. Confirmar el fallo
- [x] 3.2 Implementar `backend/app/core/token_store.py`: protocolo `TokenStore` con las operaciones del design, `InMemoryTokenStore` (dicts + reloj) y `RedisTokenStore` (INCR/EXPIRE, `SET NX EX` para revocación, email hasheado en la clave) construido desde `settings.redis_url`; verificar que los tests de 3.1 pasan
- [x] 3.3 Agregar el test `integration` contra Redis real que valida TTL de la revocación, `SET NX` fallando en el segundo intento y expiración de la ventana de fallos, y verificar con `uv run pytest tests/test_token_store.py -m integration` (se omite si Redis no está disponible, igual que el harness de Postgres)

## 4. Servicio de autenticación

- [x] 4.1 Escribir primero en rojo `backend/tests/test_auth_login.py` (marcado `integration`): login correcto responde 200 con access y cookie `HttpOnly`/`SameSite=Lax`; contraseña incorrecta, email inexistente y usuario `activo=false` responden el mismo 401 sin cookie; los tokens emitidos llevan los claims y vidas esperadas. Confirmar el fallo
- [x] 4.2 Implementar `backend/app/domain/auth/schemas.py` (`LoginIn` y `TokenOut` con `extra='forbid'`, email validado) y `backend/app/domain/auth/service.py` (búsqueda del usuario en la sesión tenant-scoped, verificación Argon2id, emisión del par, `RN-AU-01` en 401); verificar que 4.1 pasa
- [x] 4.3 Escribir primero en rojo `backend/tests/test_auth_refresh.py`: un refresh vigente devuelve par nuevo con misma identidad y tenant; reusar el refresh ya rotado responde 401; sin cookie responde 401; un access token presentado como refresh responde 401; un refresh con `tenant_id` distinto del resuelto responde 401. Confirmar el fallo
- [x] 4.4 Implementar la rotación en `service.py` (validación de `type`, chequeo de blacklist, `SET NX` del `jti` viejo, emisión del par nuevo, cookie renovada) y verificar que 4.3 pasa
- [x] 4.5 Escribir primero en rojo `backend/tests/test_auth_me_logout.py`: `GET /auth/me` devuelve `id`, `tenant_id`, `nombre`, `email`, `rol`, `es_dueno` y nunca `password_hash`; logout invalida el refresh presentado y borra la cookie; logout repetido o sin cookie responde exitoso. Implementar y verificar
- [x] 4.6 Triangular el bloqueo y la tasa en `backend/tests/test_auth_throttle.py`: 10 fallos consecutivos bloquean incluso con contraseña correcta (429, `details.reason=cuenta_bloqueada`, `Retry-After`), el bloqueo expira con el reloj avanzado, 5 intentos en 60 s rechazan el 6.º (429, `details.reason=rate_limit`) aunque la contraseña sea correcta y otro email no hereda la cuota; verificar y refactorizar el servicio para separar login exitoso/fallido de la contabilidad en el store

## 5. Router, cookie y middleware de autenticación

- [x] 5.1 Escribir primero en rojo `backend/tests/test_auth_boundary.py`: `GET /auth/me` sin token responde 401 con sobre `RN-AU-01`; access expirado responde 401 con motivo distinguible; refresh token en `Authorization` responde 401; `GET /health` sigue 200 sin token; una ruta bajo `/turnero` no responde 401 por falta de JWT; la cookie de refresh llega con `Path=/auth`, `Max-Age` de `REFRESH_DAYS` y `Secure` según el esquema de `FRONTEND_ORIGIN`. Confirmar el fallo
- [x] 5.2 Implementar `backend/app/domain/auth/router.py` con `APIRouter(prefix="/auth", tags=["auth"])` y los cuatro endpoints, más los helpers de seteo/borrado de cookie; registrar el router en `backend/app/main.py` con `app.include_router(...)` sin `prefix` ni `dependencies` en el include; verificar que los escenarios de cookie y de `/auth/me` de 5.1 pasan
- [x] 5.3 Implementar `backend/app/domain/auth/middleware.py` (`AuthMiddleware` sin acceso a base: valida `Bearer`, firma, `exp` y `type`, publica el principal en `ContextVar`, corta con 401 armado con `ErrorEnvelope`, y salta la allowlist pública de auth) y registrarlo **antes** de `TenantContextMiddleware` en `create_app()`; verificar que `/health` y `/turnero/*` no piden JWT y que el 401 del middleware trae `code` y `message`
- [x] 5.4 Implementar `get_current_user` en `backend/app/domain/auth/dependencies.py` (recarga el `Usuario` por `sub` con la sesión tenant-scoped, exige `activo=true` y `tenant_id` coincidente, y define `CurrentUserDep = Annotated[Usuario, Depends(get_current_user)]`); verificar que un usuario desactivado con token vigente recibe 401 y que `/auth/me` no consulta datos de otro tenant

## 6. RBAC

- [x] 6.1 Escribir primero en rojo `backend/tests/test_rbac.py` con un router de prueba montado en el test (mismo patrón que `_app_de_dominio()` de `backend/tests/test_tenancy_session.py`): sin token → 401 antes de evaluar roles; rol no habilitado → 403 `RN-AU-02`; rol habilitado → 200; recepción → 403 en rutas de configuración, usuarios y export; dueño (`profesional` + `es_dueno=true`) → 200; profesional sin flag → 403; `recepcion` con `es_dueno=true` → 403. Confirmar el fallo
- [x] 6.2 Implementar `es_dueno`, `require_role`, `require_dueno` y `alcance_agenda` en `backend/app/domain/auth/dependencies.py`, y verificar que 6.1 pasa
- [x] 6.3 Escribir primero en rojo los escenarios de RN-AU-03 con el router de prueba (profesional sin flag sobre recurso de otro profesional → 403; sobre el propio → 200; dueño sobre cualquier profesional → 200; recepción → 200), implementar `require_acceso_profesional` y verificar que pasan junto con 6.1
- [x] 6.4 Extender `backend/tests/test_architecture.py` para recorrer `app.routes` y fallar si una ruta no pública no declara autenticación y roles, manteniendo la allowlist pública explícita (`/health`, docs y prefijo `/turnero`); verificar que el test pasa y que falla al agregar temporalmente una ruta sin roles para recorrer `app.routes` y fallar si una ruta no pública no declara autenticación y roles, manteniendo la allowlist pública explícita (`/health`, docs y prefijo `/turnero`); verificar que el test pasa y que falla al agregar temporalmente una ruta sin roles

## 7. Verificación integral

- [x] 7.1 Correr `uv run ruff check app tests`, `uv run ruff format --check app tests`, `uv run pytest -q` (unitarios + integración) y `uv run alembic check`; verificar cero errores, cero diferencias de metadata y que no se agregó ninguna migración
- [x] 7.2 Levantar el stack desde cero (`docker compose down -v && cp .env.example .env && docker compose up --build -d`) y verificar con `curl`: login `dueno@demo` → 200 con access y cookie; `/auth/me` con ese access → 200; `/auth/refresh` rota el par y el refresh viejo → 401; logout borra la cookie y su refresh → 401; `/health` → 200 sin token; una ruta bajo `/turnero/` no responde 401 por falta de JWT
- [x] 7.3 Correr `openspec validate c-03-auth-rbac --strict` y verificar cero errores, y actualizar `CHANGES.md` marcando `[C-03]` como archivado al cerrar el change
