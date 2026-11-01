# Diseño

## Contexto

C-02 dejó todo lo que C-03 consume y nada de lo que C-03 agrega:

- `backend/app/db/models/usuario.py` define `Usuario` con `password_hash`, `rol` (`RolUsuario.recepcion | profesional`), `es_dueno` y `activo`; el CHECK `NOT es_dueno OR rol = 'profesional'` ya vive en la migración `0002_tenancy_usuario`.
- `backend/app/db/session.py` expone `TenantContextMiddleware`, `resolve_tenant()`, `get_session()` (dependencia tenant-scoped), `tenant_session()`, `system_session()`, `current_tenant()`/`require_tenant()` y la lista `PUBLIC_PATHS` (hoy: `/health`, `/openapi.json`, `/docs`, `/docs/oauth2-redirect`, `/redoc`). Esa lista exime de **resolver tenant**, no de autenticar: son conceptos distintos y C-03 debe separarlos.
- `backend/app/core/settings.py` ya tiene `secret_key` (mínimo 32), `access_minutes`, `refresh_days`, `redis_url` y `frontend_origin`, con `extra='forbid'`.
- `backend/app/core/errors.py` ya provee `DomainError` + `ErrorEnvelope` (`code` con patrón `RN-XX-NN`) y `register_handlers()`.
- `backend/app/main.py` construye la app, registra CORS y `TenantContextMiddleware`, y expone `GET /health` público.
- `backend/tests/conftest.py` provee `db_url`, `db_engine`, `clean_db`, `session_factory`, `app_env` (con `REDIS_URL` y `SECRET_KEY` ficticios) y el marcador `integration`; `backend/tests/factories.py` crea usuarios con `PASSWORD_FICTICIO`, que **no es un hash Argon2 válido** (C-02 no necesitaba verificarlo).
- `redis>=5.0` y `argon2-cffi` ya están en `backend/pyproject.toml`; **no hay librería JWT instalada** (verificado en `backend/.venv/lib/python3.12/site-packages`).
- `docker-compose.yml` ya levanta `redis:7`; `.github/workflows/ci.yml` **no** tiene servicio de Redis todavía.

Ver `proposal.md` para la motivación y `specs/core/auth` + `specs/core/rbac` para el contrato de comportamiento.

## Objetivos / No objetivos

**Objetivos:**

- Un único punto donde se decide si una request está autenticada, que falle cerrado por defecto y cuya exención pública sea una lista corta y auditable.
- Una única fuente de verdad de autorización: la fila `Usuario` del tenant resuelto (rol, `es_dueno`, `activo`), consultada en cada request.
- Estado efímero de seguridad (lockout, rate limit, blacklist) en Redis, sin tablas nuevas ni migración.
- Dejar listos los helpers que C-04/C-05/C-07/C-10 van a usar, sin que C-03 invente endpoints de negocio que no le corresponden.

**No objetivos:**

- Frontend del panel (guardado del access token, interceptor de refresh, rutas protegidas): C-10. C-03 solo fija el contrato HTTP y la cookie.
- Endpoints de turnero y su rate limit de 10 req/min por IP: C-09. C-03 solo define la frontera de exención.
- CRUD de usuarios (alta/baja/roles): C-12 o el change que corresponda; C-03 solo autentica usuarios que ya existen.
- Recuperación de contraseña, MFA, CAPTCHA, revocación de familias de refresh, RLS y selector multi-tenant: post-MVP.
- Migración Alembic: no hay cambio de modelo (R7 no se dispara).

## Decisiones

- **Autenticación en middleware con allowlist pública; autorización en dependencias por router + test de arquitectura.** Un `AuthMiddleware` (ASGI, sin acceso a base) valida el `Authorization: Bearer`, verifica firma/`exp`/`type` y publica el principal en un `ContextVar`; si la ruta no es pública y no hay token válido, corta con 401 antes de llegar al endpoint. Los roles se declaran con `require_role(...)` en el `APIRouter`/endpoint y un test de arquitectura recorre `app.routes` y falla si una ruta no pública no declara autenticación y roles. Fundamento: es la única forma de que "ruta nueva sin protección" falle cerrado sin depender de la disciplina de cada router (una dependencia a nivel `FastAPI(...)` no se puede desactivar por ruta; una dependencia por router se olvida y falla abierto). Alternativa descartada: decorar cada router a mano y confiar en la revisión.
  - El middleware se registra **antes** de `TenantContextMiddleware` en `create_app()` porque en Starlette el último middleware agregado es el más externo: el tenant debe quedar resuelto antes de que auth compare `tenant_id`.
  - La allowlist de auth (`/health`, `/openapi.json`, `/docs*`, `/redoc`, prefijo `/turnero` y los endpoints que abren o cierran sesión: `/auth/login`, `/auth/refresh`, `/auth/logout`) es independiente de `PUBLIC_PATHS` de `backend/app/db/session.py`: `/turnero/*` y `/auth/*` sí resuelven tenant (por eso no entran en `PUBLIC_PATHS`) pero no exigen JWT; `/auth/me` queda fuera de la allowlist y por lo tanto exige access token.

- **`get_current_user` recarga el `Usuario` desde la base en cada request; los claims no son la autoridad.** El access token identifica (`sub`, `jti`, `tenant_id`), pero el rol, `es_dueno` y `activo` se leen de la fila usando la sesión tenant-scoped de `get_session()`. Fundamento: desactivar un usuario o cambiarle el rol surte efecto inmediato en lugar de esperar hasta 15 minutos; y un `tenant_id` de token que no coincide con el tenant resuelto se rechaza. El claim `roles` se conserva por contrato (lo pide `CHANGES.md`) y para observabilidad/pre-chequeo barato, nunca como decisión final. Alternativa descartada: confiar en claims firmados (más rápido, pero sin revocación y con riesgo de token de otro tenant).

- **JWT HS256 con `SECRET_KEY`, claims exactos y `jti` por token.** `sub` (UUID del usuario), `tenant_id`, `roles` (lista con el rol), `email`, `jti` (UUID v4), `type` (`access` | `refresh`), `iat`, `exp`. El access vence a `settings.access_minutes` y el refresh a `settings.refresh_days`; el refresh lleva `jti` distinto para poder blacklistearlo. Fundamento: HS256 con un secreto de 32+ bytes ya configurado evita gestión de claves asimétricas en v1; `jti` habilita revocación puntual sin estado en el token. Alternativa descartada: RS256 (complejidad de rotación de claves sin beneficio en un solo servicio).

- **Access en el cuerpo, refresh en cookie `HttpOnly; SameSite=Lax`; `Secure` derivado del origen del frontend.** `POST /auth/login` y `POST /auth/refresh` devuelven `{access_token, token_type, expires_in}` y setean `refresh_token` con `HttpOnly`, `SameSite=Lax`, `Path=/auth`, `Max-Age=REFRESH_DAYS*86400`. `Secure` se activa cuando `settings.frontend_origin` empieza con `https://`: en producción siempre lo será y en desarrollo local (`http://localhost:5173`) la cookie no se descartaría. Fundamento: el refresh nunca queda accesible a JavaScript (mitiga XSS) y `SameSite=Lax` + métodos POST evita CSRF en `refresh`/`logout` sin token CSRF adicional en v1. Alternativas descartadas: access en cookie (obliga a CSRF en todas las rutas), `SameSite=Strict` (rompe el retorno desde enlaces externos), variable de entorno nueva para `secure` (obligaría a tocar el contrato `extra='forbid'` de `Settings`).

- **Rotación de refresh con blacklist en Redis y `SET NX` atómico.** En `POST /auth/refresh` se decodifica el refresh, se verifica `type=refresh`, se consulta `auth:revocado:{jti}` y se marca el `jti` viejo con `SET auth:revocado:{jti} 1 EX <segundos-hasta-exp> NX` antes de emitir el par nuevo. Si el `SET NX` falla (carrera con otro refresh del mismo token) o el `jti` ya estaba revocado, la respuesta es 401 sin tokens nuevos. Fundamento: TTL nativo, cero migraciones y Redis ya es dependencia dura del stack (worker/RQ). Alternativa descartada: tabla `refresh_token` en Postgres — da durabilidad y permitiría revocar familias, pero exige migración, limpieza periódica y suma escrituras al camino crítico del login.

- **Sin familias de refresh: limitación aceptada y registrada.** Si un atacante roba un refresh y lo usa primero, la víctima detecta el reuso (401) pero el token del atacante sigue vigente hasta su `exp`. Fundamento: revocar la familia exige `familia_id` + tabla durable (ver decisión anterior); en v1 con un consultorio y refresh de 7 días se acepta y se mitiga con detección de reuso y logout. Queda como deuda explícita en `## Riesgos`.

- **Lockout y rate limit en Redis, con contadores separados y ventanas propias.** Fallos por cuenta: `auth:fallos:{tenant_id}:{user_id}` (INCR + EXPIRE 15 min); al llegar a 10 se crea `auth:bloqueo:{tenant_id}:{user_id}` con TTL de 15 min y el login responde 429 hasta que expire. Tasa por origen: `auth:tasa:{ip}:{sha256(email)}` (INCR + EXPIRE 60 s, límite 5). Fundamento: cumple la KB (`10 intentos`, `5/60s por IP+email`) con TTL nativo y sin tabla. El email se hashea para no guardar PII en claves de Redis (R9). Alternativa descartada: columnas `intentos_fallidos`/`bloqueado_hasta` en `usuario` — migración nueva y escrituras por intento fallido en el camino de login.

- **Política ante caída de Redis: fail-open en throttling, fail-closed en blacklist.** Si Redis no responde, lockout y rate limit se degradan (se loguea warning y el login sigue) para no dejar el panel inaccesible; el refresh, en cambio, responde 503 si no puede confirmar que el `jti` no está revocado, porque aceptar un token sin verificar revocación rompe la garantía de rotación. Fundamento: prioriza disponibilidad del login y conserva la integridad de la sesión. Alternativa descartada: fail-closed en todo (un Redis caído bloquea el panel entero, incluido el acceso de emergencia del dueño).

- **Store abstracto `TokenStore` con implementación Redis e implementación en memoria.** Un protocolo con las operaciones (`registrar_fallo`, `esta_bloqueado`, `limpiar_fallos`, `consumir_cuota`, `revocar`, `esta_revocado`) y dos implementaciones: `RedisTokenStore` (runtime, `redis.Redis` desde `settings.redis_url`) e `InMemoryTokenStore` (tests unitarios, con reloj inyectable). Se resuelve por dependencia FastAPI. Fundamento: los tests de login/lockout/rotación no dependen de un Redis vivo, y la semántica de TTL se prueba aparte con un test `integration` contra Redis real. Alternativa descartada: `fakeredis` (dependencia nueva solo para tests) y acoplar los servicios a `redis.Redis`.

- **Tenant resuelto por `TENANT_DEFAULT_SLUG`; el `tenant_id` del claim se deriva de ese contexto.** El login no recibe tenant del cliente: la query de usuario corre en la sesión tenant-scoped que ya inyecta `TenantContextMiddleware`, así que la unicidad `(tenant_id, email)` de C-02 hace que el email identifique al usuario dentro del consultorio. En `refresh` y en `get_current_user` se compara el `tenant_id` del token con `require_tenant().tenant_id` y se rechaza si difiere. Fundamento: v1 es de un solo consultorio (DD-02, spec `core/tenancy`) y esto evita que un token de otro tenant opere acá. Consecuencia: un mismo email en dos tenants no es un caso de login en v1; el selector de tenant (subdominio/header) es post-MVP.

- **RBAC como funciones puras + factorías de dependencia en `app/domain/auth/dependencies.py`.** `es_dueno(usuario)` devuelve verdadero solo con `rol == profesional and es_dueno`; `require_role(*roles)` produce una dependencia que responde 403 (`RN-AU-02`) si el rol no está habilitado; `require_dueno` exige ambas condiciones; `alcance_agenda(usuario)` devuelve `TODAS` para recepción o dueño y `PROPIA` para profesional sin flag. Los alias tipados (`CurrentUserDep = Annotated[Usuario, Depends(get_current_user)]`) evitan repetir `Depends` en las firmas. Fundamento: las funciones puras son testeables sin HTTP y las dependencias se declaran en el `APIRouter` (`APIRouter(prefix=..., tags=..., dependencies=[Depends(require_role(...))])`), no en `include_router()`.

- **RN-AU-03 se entrega como helper + verificación con router de prueba, no como endpoint nuevo.** El vínculo "usuario ↔ profesional" recién existe cuando C-04 cree `Profesional.usuario_id`; C-03 no puede inventar esa tabla. Se entrega `alcance_agenda` + `require_acceso_profesional(usuario, usuario_id_duenio_del_recurso)` y se prueba con un router montado en el test (mismo patrón que `_app_de_dominio()` en `backend/tests/test_tenancy_session.py`), con recepción → 200, profesional ajeno → 403, dueño → 200. C-04 y C-05 conectan el helper al `Profesional` real.

- **Errores de auth usan el sobre existente con códigos `RN-AU-*`.** 401 → `RN-AU-01` con `details.reason` (`credenciales_invalidas`, `token_expirado`, `token_invalido`, `refresh_revocado`, `usuario_inactivo`); 403 de rol o dueño → `RN-AU-02`; 403 de alcance profesional → `RN-AU-03`; 429 de lockout/rate → `RN-AU-01` con `details.reason` (`cuenta_bloqueada`, `rate_limit`) y `Retry-After`. Fundamento: RN-GL-01 exige código `RN-XX-NN` y el frontend necesita distinguir "reintentar refresh" de "volver a login". La KB solo define `RN-AU-01..03`; ver `## Preguntas abiertas` sobre códigos nuevos.

- **Comparación de tiempo constante ante email inexistente.** Cuando el email no existe se verifica la contraseña contra un hash Argon2id ficticio precalculado antes de responder 401, para no filtrar por latencia qué emails existen. Alternativa descartada: responder rápido (más simple, pero enumerable).

- **Sin migración Alembic; `alembic check` debe seguir limpio.** No se agregan tablas, columnas ni índices: el estado de seguridad es efímero (Redis) y `Usuario` ya tiene todo lo necesario. R7 no aplica porque no hay cambio de modelo; el task de verificación corre `alembic check` para demostrarlo.

- **Dependencia nueva: `pyjwt`.** Elegida por ser mantenida, sin dependencias criptográficas extra para HS256 y con API mínima (`jwt.encode/decode` con `algorithms=["HS256"]` y `options={"require": [...]}`). Alternativas descartadas: `python-jose` (arrastra `ecdsa`/`rsa`, historial de CVEs) y `authlib` (framework completo, sobredimensionado). **U3: requiere aprobación explícita del usuario antes de instalarla**; es el primer task y bloquea al resto.

- **Tests sobre el harness de C-02 más un Redis opcional.** Los tests de login/refresh/RBAC usan `app_env`, `db_url` y `InMemoryTokenStore` (sin Redis). Un test `integration` contra Redis real valida TTL/`SET NX`. `backend/tests/factories.py` gana un helper `crear_usuario_con_password(...)` que hashea con `app.core.security.hash_password`, porque `PASSWORD_FICTICIO` no es un hash válido y el login lo rechazaría. El job `backend` de `.github/workflows/ci.yml` suma un servicio `redis:7` y `REDIS_URL`.

## Riesgos / Compromisos

- [Riesgo] Sin familias de refresh, un refresh robado y usado primero sigue vigente hasta 7 días → Mitigación: detección de reuso (401 en el segundo uso), logout revoca el `jti` vigente, access de 15 min y deuda registrada para agregar `familia_id` + tabla durable post-MVP.
- [Riesgo] El access token sigue válido hasta 15 min después del logout (solo se blacklistea el refresh) → Mitigación aceptada por el TTL corto; si se requiere revocación inmediata de access, se blacklistea también su `jti` en logout (costo: una lectura a Redis por request).
- [Riesgo] Pérdida de datos de Redis (flush/restart) rehabilita refresh ya rotados y borra bloqueos → Mitigación: aceptado en v1 (Redis sin persistencia configurada); documentado como límite del blacklist en memoria.
- [Riesgo] El middleware agrega un 401 con sobre armado a mano (no pasa por el handler de `DomainError`) → Mitigación: construir el cuerpo con `ErrorEnvelope.model_dump(exclude_none=True)` y un test que verifique `code`/`message` en el 401 del middleware.
- [Riesgo] La IP del cliente detrás de proxy puede ser la del proxy y colapsar el rate limit → Mitigación: usar `request.client.host` (uvicorn aplica `--proxy-headers` en el deploy) y documentar que el rate limit por IP es una barrera, no una garantía.
- [Riesgo] El test de arquitectura puede dar falsos positivos/negativos al recorrer `app.routes` → Mitigación: recorrer el árbol `route.dependant` buscando la marca de `require_role`/`get_current_user`, y mantener una lista explícita de rutas públicas en el propio test.
- [Riesgo] Tests de auth dependientes de tiempo (`exp`, lockout, ventana de 60 s) son frágiles → Mitigación: inyectar reloj en `InMemoryTokenStore` y generar tokens con `exp` desplazado, en lugar de dormir; solo el test de Redis real usa TTL cortos.
- [Riesgo] Un cambio de rol o `activo` requiere una query extra por request (recarga del usuario) → Mitigación: es una lectura por PK en la sesión ya abierta; se acepta el costo frente a la revocación inmediata.
- [Riesgo] La cookie `Secure` se desactiva si `FRONTEND_ORIGIN` queda en `http://` en producción → Mitigación: test de configuración que falla si el origen no es `https://` con `ENV=production` cuando esa variable exista; por ahora queda como supuesto explícito y verificación manual en el smoke de deploy.

## Plan de migración

1. Aprobar e instalar `pyjwt` (U3). No hay migración de base: `alembic upgrade head` queda igual y `alembic check` debe reportar cero diferencias.
2. Desplegar con `REDIS_URL` alcanzable (ya presente en `docker-compose.yml` y en `Settings`). No hay variables de entorno nuevas.
3. Verificación de humo: `POST /auth/login` con `dueno@demo` devuelve access + cookie; `GET /auth/me` con ese access responde 200; `POST /auth/refresh` rota y el refresh viejo responde 401; `GET /turnero/<slug>` no pide JWT.
4. Rollback: revertir el change quita router y middleware; los usuarios y sus hashes quedan intactos (C-02 no se toca) y no hay estado persistido que limpiar, salvo claves `auth:*` en Redis que expiran solas.

## Preguntas abiertas

- **Códigos de error para auth.** La KB define solo `RN-AU-01..03`. Se propone agregar `RN-AU-04` (credenciales inválidas / sesión no válida) y `RN-AU-05` (cuenta bloqueada o límite de tasa) para que el frontend distinga casos sin parsear `details.reason`. Mientras no se apruebe, todo 401/429 de auth usa `RN-AU-01` con `details.reason`. Confirmar con el usuario si se actualiza `knowledge-base/05_reglas_de_negocio.md`.
- **Ventana de lockout.** La KB fija 10 intentos pero no la duración del bloqueo; se asume 15 minutos desde el décimo fallo, con reinicio al login exitoso.
- **`es_dueno` en el claim.** `CHANGES.md` fija los claims sin `es_dueno`; el flag se lee de la base. Si el frontend necesita ocultar secciones sin llamar a `/auth/me`, se puede agregar `dueno` al claim más adelante sin romper compatibilidad.
- **Consumo del access en el panel.** Se asume que C-10 lo guarda en memoria y lo adjunta como `Bearer`; si el equipo prefiere access también en cookie, cambia la estrategia CSRF y debe revisarse en C-10.
