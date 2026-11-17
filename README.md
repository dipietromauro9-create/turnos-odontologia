# Turnos Odontología

Sistema de gestión de turnos para consultorios odontológicos argentinos de 1 a 3 profesionales. Une agenda multi-profesional, turnero público 24/7, recordatorios manuales por WhatsApp, reportes de gestión y exportación de datos en un solo flujo.

Proyecto académico desarrollado para **Metodología de Sistemas I**.

## Equipo

- **Mauro Di Pietro**
- **Franco Sampieri**

## Funcionalidades

- **Agenda interna** día/semana por profesional, con duración variable, bloqueos, sobreturnos explícitos y defensa anti-solape en base de datos.
- **Turnero público** sin registro: el paciente elige profesional, prestación y horario; recibe un código de 12 caracteres para consultar, cancelar o reprogramar.
- **Máquina de estados de turnos** (`reservado → confirmado → atendido | ausente` y cancelación) con validaciones centralizadas.
- **Recordatorios de WhatsApp manual**: cola de recepción, texto pre-generado y marcado de enviado/fallido.
- **Reportes** de ocupación, ausentismo y efectividad de recordatorios, con exportación CSV asíncrona.
- **Autenticación JWT** con access + refresh y RBAC de tres roles: recepción, profesional y dueño.
- **Multi-tenant lógico** desde el día uno: todo el dominio cuelga de `tenant_id`.

## Stack

| Capa | Tecnología |
|---|---|
| Backend | Python 3.12 · FastAPI · SQLAlchemy 2 · Alembic · Pydantic v2 |
| Base de datos | PostgreSQL 16 |
| Cola / jobs | Redis 7 · RQ · rq-scheduler |
| Frontend | React 18 · TypeScript · Vite |
| Auth | JWT (access 15 min + refresh 7 días) + RBAC |
| Tests | pytest (backend) · Vitest (frontend) |
| Deploy | Docker Compose |

## Requisitos

Para el camino recomendado con Docker:

- Docker Engine 24 o superior.
- Docker Compose v2.20 o superior (`docker compose version`).
- Puertos libres: `5173` (web), `8000` (API), `5432` (Postgres) y `6379` (Redis).

Para desarrollo local sin contenedores para la app:

- Python 3.12+ y `uv` (o `pip`).
- Node.js 20+ y npm.
- PostgreSQL 16 y Redis 7 accesibles.

## Instalación y arranque (Docker Compose)

```bash
git clone https://github.com/dipietromauro9-create/turnos-odontologia.git
cd turnos-odontologia
cp .env.example .env
docker compose up -d --build
```

Eso construye y levanta: `postgres`, `redis`, `api`, `worker`, `scheduler` y `web`. La API aplica las migraciones de Alembic y ejecuta el seed idempotente del consultorio demo al arrancar.

Verificación rápida:

```bash
curl -sS http://localhost:8000/health          # {"status":"ok","database":"up"}
curl -sS -o /dev/null -w "%{http_code}\n" http://localhost:5173/   # 200
```


| Servicio | URL |
|---|---|
| Web | http://localhost:5173 |
| API | http://localhost:8000 |
| **Swagger / OpenAPI** | **http://localhost:8000/docs** · `/openapi.json` |
| PostgreSQL | `localhost:5432` |
| Redis | `localhost:6379` |

Comandos útiles:

```bash
docker compose ps
docker compose logs -f api
docker compose logs -f worker
docker compose down          # bajar servicios (conserva el volumen)
```

> **Si el puerto 8000 está ocupado** por otro proceso, creá un `docker-compose.override.yml` local que exponga la API en `8001` y apunte Vite ahí. No lo commitees:
>
> ```yaml
> services:
>   api:
>     ports: !override
>       - "8001:8000"
>   web:
>     environment:
>       VITE_API_URL: http://localhost:8001
> ```
>
> En ese caso Swagger queda en `http://localhost:8001/docs`.

## Configuración de ejemplo (sin secretos)

El repositorio **no incluye secretos reales**. `.env.example` contiene únicamente valores de ejemplo y placeholders; copialo a `.env` y ajustá lo necesario. El `.env` real está ignorado por git.

| Variable | Ejemplo | Para qué |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://turnos:turnos_dev@postgres:5432/turnos` | Conexión a PostgreSQL (en Compose el host es `postgres`) |
| `REDIS_URL` | `redis://redis:6379/0` | Cola RQ y scheduler |
| `SECRET_KEY` | `cambiar-en-cada-deploy-32-bytes-minimo-...` | Firma JWT; **generar uno real de 32+ bytes por deploy** |
| `ACCESS_MINUTES` | `15` | Vida del access token |
| `REFRESH_DAYS` | `7` | Vida del refresh token |
| `TENANT_DEFAULT_SLUG` | `demo` | Consultorio único de la v1 |
| `TZ` | `America/Argentina/Buenos_Aires` | Zona horaria del sistema (RN-GL-03) |
| `FRONTEND_ORIGIN` | `http://localhost:5173` | Origen permitido por CORS |
| `RECORDATORIO_VENTANA_HS` | `24,48` | Ventana de generación de recordatorios |
| `CONSULTORIO_DIRECCION` | `Av. Ficticia 123` | Dirección ficticia en la plantilla de WhatsApp |
| `VITE_API_URL` | `http://localhost:8000` | URL de la API que usa el navegador |
| `STITCH_API_KEY` | *(vacío)* | Opcional, solo para el MCP de diseño; personal y no requerida para correr el sistema |

> `SECRET_KEY`, credenciales de base y `STITCH_API_KEY` son ejemplos o placeholders. No uses estos valores en producción ni subas tu `.env`.

### Desarrollo local (opcional)

Backend (con Postgres y Redis ya levantados, por ejemplo `docker compose up -d postgres redis`):

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"   # alternativa: uv sync --extra dev
export DATABASE_URL="postgresql+psycopg://turnos:turnos_dev@localhost:5432/turnos"
export REDIS_URL="redis://localhost:6379/0"
export SECRET_KEY="$(printf 't%.0s' {1..40})"
export ACCESS_MINUTES=15 REFRESH_DAYS=7 TENANT_DEFAULT_SLUG=demo
export TZ="America/Argentina/Buenos_Aires" FRONTEND_ORIGIN="http://localhost:5173"
export RECORDATORIO_VENTANA_HS="24,48"
alembic upgrade head
python -m app.db.seed
uvicorn app.main:app --reload --port 8000
```

Frontend:

```bash
cd frontend
npm install
VITE_API_URL=http://localhost:8000 npm run dev
```

## Datos ficticios

El seed (`backend/app/db/seed.py`) crea un consultorio demo **idempotente**:

- 1 tenant `demo`.
- 2 usuarios: `recepcion@demo` y `dueno@demo`.
- 1 profesional, 5 prestaciones, 2 pacientes, 10 franjas de disponibilidad y 3 turnos (reservado, confirmado y atendido).
- Todos los nombres, teléfonos y datos clínicos son ficticios (R9).

Credenciales:

| Rol | Email | Contraseña |
|---|---|---|
| Recepción | `recepcion@demo` | `demo-recepcion-ficticio-2026` |
| Dueño / profesional | `dueno@demo` | `demo-profesional-ficticio-2026` |

Para reiniciar la base y volver a sembrar desde cero:

```bash
docker compose down -v     # ⚠️ borra el volumen de PostgreSQL
docker compose up -d --build
```

Para ejecutar el seed a mano (es idempotente, no duplica datos):

```bash
# con Compose
docker compose exec api python -m app.db.seed

# local
cd backend && .venv/bin/python -m app.db.seed
```

## Rutas principales

| Ruta | Descripción |
|---|---|
| `/` | Portada pública |
| `/login` | Login del panel |
| `/app` | Agenda interna (día/semana) |
| `/app/recordatorios` | Cola de recordatorios |
| `/app/reportes` | Reportes y exportación (dueño) |
| `/turnero/demo` | Turnero público del consultorio demo |
| `/turnero/mis-turnos` | Autogestión del paciente por código |

El paciente **no tiene cuenta**: reserva desde el turnero público y gestiona su turno con el código que recibe.

## Swagger

- UI interactiva: **http://localhost:8000/docs** (o `8001` si usás el override).
- Esquema OpenAPI: `http://localhost:8000/openapi.json`.
- El esquema no declara `securitySchemes`, así que Swagger **no muestra el botón Authorize**. Para probar rutas protegidas:
  1. Ejecutá `POST /auth/login` desde Swagger con un usuario demo.
  2. Copiá el `access_token` de la respuesta.
  3. En cada request protegida agregá manualmente el header `Authorization: Bearer <access_token>`.

También podés hacerlo por consola:

```bash
TOKEN=$(curl -sS -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"recepcion@demo","password":"demo-recepcion-ficticio-2026"}' \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['access_token'])")

curl -sS "http://localhost:8000/agenda/semana?desde=2026-11-17" \
  -H "Authorization: Bearer $TOKEN"
```


## Tests

Con Postgres y Redis levantados:

```bash
# Backend
cd backend
.venv/bin/python -m pytest -q

# Frontend
cd frontend
npm run typecheck
npm run lint
npm test
```

- Backend: **875 tests** (unitarios, integración y E2E) en verde.
- Frontend: **58 tests** Vitest en verde.
- Los tests de integración crean/usan una base `turnos_test` y se omiten si Postgres o Redis no están disponibles.

## Estructura del repositorio

```
backend/
  app/domain/        # auth, agenda, turnos, huecos, turnero, recordatorios, reportes, exportación
  app/db/            # modelos, sesión tenant-scoped, seed
  alembic/           # migraciones
  tests/             # pytest (unitarios + integración + E2E)
frontend/
  src/features/      # agenda, turnero, recordatorios, reportes, auth, shell
  src/shared/        # cliente HTTP, contratos de API, estilos
knowledge-base/      # 11 documentos de dominio (fuente de verdad)
docs/design/         # pantallas exportadas de Stitch (agenda, turnero, recordatorios, reportes)
docs/skills-mcp/     # ficha de la skill propia y del MCP
openspec/            # changes archivados y specs principales
CHANGES.md           # roadmap de implementación
```

## Documentación

- [Base de conocimiento](knowledge-base/README.md): visión, actores, modelo de datos, reglas de negocio y flujos.
- [Roadmap de changes](CHANGES.md): 12 changes del MVP + mantenimiento post-MVP.
- [Specs OpenSpec](openspec/specs/): contratos de comportamiento por capability.
- [Diseño](docs/design/README.md): pantallas de Stitch y convención de exportación.
- [Skill + MCP](docs/skills-mcp/investigacion.md): skill `pantalla-a-componente` y MCP de Stitch.

## Alcance: qué está completo y qué queda pendiente

### ✅ Completo (MVP)

| Área | Estado |
|---|---|
| Cimientos: Compose, scaffolding, multi-tenant lógico | ✅ |
| Auth: login, refresh, logout, `/auth/me`, lockout, rate limit | ✅ |
| RBAC: recepción, profesional, dueño | ✅ |
| Profesionales y prestaciones (catálogo dueño, proyección de agenda) | ✅ |
| Pacientes: ficha básica, búsqueda, anti-duplicado | ✅ |
| Disponibilidad semanal y bloqueos | ✅ |
| Turnos: alta, máquina de estados, anti-solape con `EXCLUDE`, sobreturnos | ✅ |
| Motor de huecos y reprogramación atómica | ✅ |
| Turnero público: catálogo, reserva, código, cancelar y reprogramar | ✅ |
| Panel interno: agenda día/semana, filtros, alta y transiciones | ✅ |
| Recordatorios WhatsApp manuales (cola + scheduler) | ✅ |
| Reportes de ocupación/ausencias/IN-03 y export CSV asíncrono | ✅ |
| Diseño de panel, turnero, recordatorios y reportes | ✅ |
| Tests y documentación OpenSpec/KB | ✅ |

### ⏳ Pendiente / post-MVP

| Ítem | Estado |
|---|---|
| Señas y cobros con **Mercado Pago** | ⏳ |
| Facturación electrónica **ARCA** | ⏳ |
| Integración con **obras sociales / prepagas** | ⏳ |
| **WhatsApp API oficial** (envío automático) | ⏳ |
| **Multi-tenant real** con selector de consultorio/subdominio | ⏳ |
| Cuentas y portal del paciente | ⏳ |
| **Odontograma** y periodontograma gráficos | ⏳ |
| Ficha clínica avanzada / imágenes y RX | ⏳ |
| Auditoría formal append-only (deuda DD-07) | ⏳ |
| Lista de espera automática y recordatorios de recall | ⏳ |
| Google Calendar y app móvil | ⏳ |
| Shell completo del mockup (sidebar, buscador global, métricas) | ⏳ |
| Drag & drop para reprogramar desde la agenda | ⏳ |
| Endurecimiento de producción: HTTPS, gestor de secretos, backups | ⏳ |

### Limitaciones conocidas de la v1

- Un solo consultorio (`TENANT_DEFAULT_SLUG=demo`) y una sola zona horaria (`America/Argentina/Buenos_Aires`).
- WhatsApp es **manual**: el sistema genera el texto y recepción lo envía.
- El paciente no tiene usuario ni contraseña; opera con el código público del turno.
- No hay despliegue productivo ni estrategia de backups incluida.
- El shell del panel es mínimo (agenda, recordatorios y reportes), no el sidebar completo del diseño.

## Reglas del proyecto

Las reglas duras de desarrollo (tipado estricto, `tenant_id` obligatorio, máquina de estados centralizada, migraciones siempre en sync, datos de pacientes ficticios) están documentadas en [AGENTS.md](AGENTS.md).
