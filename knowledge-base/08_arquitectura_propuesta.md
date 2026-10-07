# Arquitectura Propuesta

## Patrones aplicados

| Patrón | Dónde se usa | Por qué |
|---|---|---|
| Monolito modular | Backend FastAPI por routers de dominio (turnos, pacientes, agenda, reportes) | Un deploy, cero latencia de red; la modularidad evita el "big ball of mud" (P5:b) |
| Repository + Service | `repositories/` (SQLAlchemy) bajo `services/` (reglas RN) | Las reglas viven en un solo lugar testeable; los routers son finos |
| Tenant discriminator | `tenant_id` en todo el dominio + middleware que lo inyecta | Frontera multi-tenant sin costo operativo en v1 (P0-sys:c) |
| State machine explícita | Servicio de turnos valida transiciones RN-TU-04 | Q-turno:a; imposible representar estados inválidos |
| DB como última defensa | `EXCLUDE` anti-solape + uniques + FKs | La concurrencia real (doble clic, dos recepcionistas) la resuelve Postgres |
| Job queue | RQ + rq-scheduler sobre Redis | Recordatorios y exports fuera del request path; reintentos gratis |
| Códigos de error de dominio | Respuestas `{"code": "RN-TU-01", ...}` | RN-GL-01: frontend y tests hablan el mismo idioma que la KB |

## Estructura de directorios

```
turnos-odontologia/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI app, middlewares, routers
│   │   ├── core/                   # config, security (JWT), tenant middleware
│   │   ├── domain/
│   │   │   ├── turnos/             # router, service (máquina de estados), repository, schemas
│   │   │   ├── agenda/             # profesionales, prestaciones, disponibilidad, bloqueos
│   │   │   ├── pacientes/
│   │   │   ├── recordatorios/      # plantillas + cola manual
│   │   │   ├── reportes/           # ocupación, ausencias
│   │   │   └── sistema/            # auth, usuarios, export
│   │   ├── workers/                # jobs RQ (generar_recordatorios, export_csv)
│   │   └── db/                     # Base, session, migraciones Alembic
│   ├── tests/                      # espejo de domain; test_RN-TU-01_*.py por regla crítica
│   ├── Dockerfile
│   └── pyproject.toml
├── frontend/
│   └── src/
│       ├── features/               # turnero-publico, agenda, pacientes, recordatorios, reportes
│       ├── shared/                 # api client (inyecta JWT / codigo_publico), ui, hooks
│       ├── pages/                  # /turnero/:slug, /app/*
│       └── routes.tsx              # guardia: público vs. requiere rol
├── docker-compose.yml              # api + web + postgres + redis + worker
└── knowledge-base/
```

## Seguridad

- Autenticación: JWT access 15 min + refresh rotativo 7 días (httpOnly cookie para refresh); turnero público con `codigo_publico` de 12 chars (entropía ≥ 70 bits, rate-limit 10 req/min por IP).
- Autorización: dependencia `require_role(...)` por router + chequeo de `tenant_id` en cada query (middleware; imposible olvidar el filtro si se usa el `get_session` del core).
- Validación de input: Pydantic v2 en backend (los schemas son la única fuente), validación espejo liviana en frontend.
- Secrets management: solo por variables de entorno (ver tabla); nada en el repo. `SECRET_KEY` de 32+ bytes generado por deploy.
- Contraseñas: Argon2id; lockout tras 10 intentos fallidos (registrado, sin CAPTCHA en v1).
- Cabeceras y CORS: CORS restringido al origen del frontend; `X-Content-Type-Options`, `frame-ancestors 'self'`.

## Variables de entorno

| Variable | Descripción | Ejemplo | Sensible |
|---|---|---|---|
| `DATABASE_URL` | Conexión Postgres | `postgresql+psycopg://turnos:***@postgres:5432/turnos` | Y |
| `REDIS_URL` | Conexión Redis/RQ | `redis://redis:6379/0` | N |
| `SECRET_KEY` | Firma JWT | (generado, 32+ bytes) | Y |
| `ACCESS_MINUTES` / `REFRESH_DAYS` | Vida de tokens | `15` / `7` | N |
| `TENANT_DEFAULT_SLUG` | Tenant v1 | `demo` | N |
| `TZ` | Zona horaria del sistema | `America/Argentina/Buenos_Aires` | N |
| `FRONTEND_ORIGIN` | Origen permitido CORS | `http://localhost:5173` | N |
| `RECORDATORIO_VENTANA_HS` | Ventana de generación (RN-CO-01) | `24,48` | N |
