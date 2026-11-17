# Turnos Odontología

Sistema de gestión de turnos para consultorios odontológicos argentinos de 1 a 3 profesionales. Une agenda multi-profesional, turnero público 24/7, recordatorios manuales por WhatsApp, reportes de gestión y exportación de datos en un solo flujo.

Proyecto académico desarrollado para **Metodología de Sistemas I**.

## Equipo

- **Mauro Di Pietro**
- **Franco Sampieri**

## Funcionalidades

- **Agenda interna** día/semana por profesional, con duración variable, bloqueos, sobreturnos explícitos y defensa anti-solape en base de datos.
- **Turnero público** sin registro: el paciente elige profesional, prestación y horario; recibe un código de 12 caracteres para consultar, cancelar o reprogramar.
- **Máquina de estados de turnos** (`reservado → confirmado → atendido | ausente` y cancelación) con validaciones de negocio centralizadas.
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

## Cómo levantarlo

Requisitos: Docker y Docker Compose.

```bash
git clone https://github.com/dipietromauro9-create/turnos-odontologia.git
cd turnos-odontologia
cp .env.example .env
docker compose up -d --build
```

Servicios:

| Servicio | URL |
|---|---|
| Web | http://localhost:5173 |
| API + Swagger | http://localhost:8000 · http://localhost:8000/docs |
| PostgreSQL | `localhost:5432` |
| Redis | `localhost:6379` |

Al arrancar, la API aplica las migraciones de Alembic y ejecuta el seed idempotente del consultorio demo.

> Si el puerto `8000` está ocupado en tu máquina, podés exponer la API en otro puerto con un `docker-compose.override.yml` local y apuntar `VITE_API_URL` al nuevo puerto.

### Credenciales demo

| Rol | Email | Contraseña |
|---|---|---|
| Recepción | `recepcion@demo` | `demo-recepcion-ficticio-2026` |
| Dueño / profesional | `dueno@demo` | `demo-profesional-ficticio-2026` |

Los datos del seed son **exclusivamente ficticios** (R9): no hay información real de pacientes.

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

## Tests

Con los servicios de Postgres y Redis levantados:

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

Estado actual: **875 tests backend** y **58 tests frontend** en verde.

## Estado del proyecto

- MVP completo: 12 changes archivados (cimientos, acceso, directorio, agenda, turnos, canales y reportes).
- Mantenimiento post-MVP: estilos del panel y pasada visual del turnero, recordatorios y reportes.
- Arquitectura: monolito modular, multi-tenant lógico y RBAC; sin microservicios.
- Integraciones post-MVP previstas: Mercado Pago, ARCA, obras sociales y WhatsApp API oficial.

## Reglas del proyecto

Las reglas duras de desarrollo (tipado estricto, `tenant_id` obligatorio, máquina de estados centralizada, migraciones siempre en sync, datos de pacientes ficticios) están documentadas en [AGENTS.md](AGENTS.md).
