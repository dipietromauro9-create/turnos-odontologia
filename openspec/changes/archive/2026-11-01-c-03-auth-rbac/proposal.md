# Propuesta

## Por qué

C-02 dejó `Tenant`/`Usuario` con `rol` y `es_dueno`, una sesión tenant-scoped y un seed con hashes Argon2id, pero no existe forma de probar identidad: cualquier endpoint de dominio que agregue C-04 en adelante quedaría abierto. C-03 es el gate de acceso del roadmap —sin JWT, rotación de refresh y una matriz RBAC aplicada por router, ni la agenda ni las fichas de pacientes (RN-AU-03) pueden exponerse—.

## Qué cambia

- Agregar los endpoints de sesión sobre el `Usuario` de C-02:
  - `POST /auth/login`: verifica `password_hash` con Argon2id, emite access + refresh y setea el refresh en cookie HttpOnly.
  - `POST /auth/refresh`: rota el par de tokens y blacklistea el refresh usado; reusar un refresh ya rotado devuelve 401.
  - `POST /auth/logout`: blacklistea el refresh vigente y borra la cookie.
  - `GET /auth/me`: devuelve el usuario autenticado (sin `password_hash`).
- Emitir JWT con `sub`, `tenant_id`, `roles`, `email`, `jti`, `type`, `iat`, `exp`: access de `ACCESS_MINUTES` (15) y refresh de `REFRESH_DAYS` (7), firmados con `SECRET_KEY`. El refresh viaja en cookie `HttpOnly; Secure; SameSite=Lax`; el access se devuelve en el cuerpo para que el panel lo use como `Authorization: Bearer`.
- Agregar el control de intentos fallidos y de tasa en `POST /auth/login`: lockout de la cuenta tras 10 fallos y rate limit de 5 requests por 60 s por combinación IP+email. Ambos contadores viven en Redis (ya en el stack), sin tablas nuevas.
- Agregar la capa RBAC reutilizable: dependencia `require_role(...)` para declarar roles en el `APIRouter`/endpoint, helper `require_dueno` y helper `es_dueno(usuario)`; `Usuario.rol` + `es_dueno` de C-02 son la única fuente de verdad. Se aplica la matriz de `03_actores_y_roles.md`: la recepción nunca accede a configuración, usuarios ni exports (RN-AU-02); el profesional solo ve su propia agenda y sus fichas salvo que sea dueño (RN-AU-03).
- Declarar la frontera pública del turnero: los paths `/turnero/*` quedan exentos de JWT y operan con `codigo_publico` por turno (RN-AU-01). En C-03 solo se planifica y se deja el mecanismo de exención; el rate limit de 10 req/min por IP y los endpoints reales son de C-09.
- Agregar el módulo de seguridad (`core/security.py`: firma/verificación JWT y Argon2id) y el dominio `auth` (`domain/auth/`: schemas, servicio, router y dependencias), sin tocar los modelos de C-02 y por lo tanto sin migración nueva.
- Pruebas: login correcto, credenciales inválidas, access expirado, rotación de refresh con reuso del token viejo → 401, logout invalida el refresh, RBAC (recepción → 403 en endpoints de dueño), lockout tras 10 intentos, rate limit 5/60 s, `/auth/me` sin cookie/token → 401 y el turnero público respondiendo sin JWT.

## Capacidades

### Nuevas capacidades

- `core/auth`: ciclo de vida de la sesión del panel — login con Argon2id, emisión y rotación de JWT, cookie de refresh, logout, identidad actual (`/auth/me`), lockout por intentos fallidos, rate limit de login y la frontera de rutas exentas de JWT (turnero público, RN-AU-01).
- `core/rbac`: contrato de autorización por rol — matriz de permisos de `03_actores_y_roles.md`, dependencia `require_role(...)`, chequeo de dueño (`es_dueno` / `require_dueno`) y el alcance del profesional sobre agenda y fichas propias (RN-AU-02, RN-AU-03, DD-08).

### Capacidades modificadas

- Ninguna. `core/tenancy` ya resuelve el tenant de cada request y `core/persistence` ya garantiza el aislamiento; C-03 los consume sin cambiar su contrato. `foundation/backend-base` mantiene el sobre `{code, message, details}` de RN-GL-01: los fallos de auth lo usan con códigos `RN-AU-*`.

## Impacto

- Afecta: `backend/app/core/` (`security.py` nuevo, `settings.py` si hace falta una variable nueva, `errors.py` reutilizado), `backend/app/domain/auth/` (nuevo: `schemas.py`, `service.py`, `dependencies.py`, `router.py`), `backend/app/main.py` (registro del router), `backend/tests/` (nuevos tests de auth/RBAC y ajustes de fixtures), `backend/pyproject.toml`.
- APIs: cuatro endpoints nuevos bajo `/auth`; ninguna ruta existente cambia de contrato. `GET /health` sigue público y sin tenant; `/docs` y `/openapi.json` siguen públicos.
- Dependencias: nueva dependencia de runtime para firmar/verificar JWT (`pyjwt` recomendada). **Requiere aprobación explícita del usuario (U3) antes de instalarla**; el plan la deja como primer paso bloqueante. `redis` y `argon2-cffi` ya están en el stack.
- Base de datos: **sin migración**. No se agregan tablas ni columnas: lockout, rate limit y blacklist de refresh viven en Redis. `Usuario` de C-02 ya tiene `password_hash`, `rol`, `es_dueno` y `activo`.
- Aguas abajo: desbloquea C-04 (`profesionales-prestaciones` necesita `require_dueno` para sus endpoints), C-05, C-06, C-07, C-08 y C-10; C-09 consume la frontera pública del turnero y su propio rate limit. Gobernanza **CRÍTICO**: RN-AU-01/02/03 y la matriz de roles quedan enforced acá.
