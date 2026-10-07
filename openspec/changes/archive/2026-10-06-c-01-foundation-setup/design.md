# Diseño

## Contexto

Repo greenfield: no hay `backend/`, ni `frontend/`, ni Compose. Ver proposal.md (Por qué) para la motivación. Restricciones que dan forma al enfoque: el layout de directorios y la tabla de entorno de la KB `08` son normativos; R1 (`extra='forbid'` en todos los schemas Pydantic), R2 (TS estricto, sin `any`), R7 (modelos ↔ Alembic en sync), RN-GL-01 (sobre de errores), RN-GL-03 (TZ única). Gobernanza BAJA — autonomía total mientras los tests pasen. Los changes posteriores asumen que existen `db.session.get_session`, la cabeza de Alembic, el objeto de configuración y los guardianes de rutas.

## Objetivos / No objetivos

**Objetivos:**

- Arranque local con un solo comando (`docker compose up`) que deja una API sana + DB + Redis + worker + shell web.
- Shells de backend/frontend que C-02/C-03 extienden sin reestructurar (routers, servicios, cadena de Alembic y guardianes ya en su lugar).
- CI que verifica ambos shells en cada push (jobs paralelos de backend/frontend).

**No objetivos:**

- Sin tablas de dominio, sin auth, sin middleware de tenant (C-02/C-03). La línea base de Alembic queda vacía a propósito.
- Sin UI más allá de un cascarón provisorio (las páginas reales del turnero/agenda son C-09/C-10); todavía sin sistema visual más allá de evitar defaults de plantilla según frontend-design.
- Sin endurecimiento productivo (TLS, gestor de secretos, backups) — Compose es de grado dev/MVP.

## Decisiones

- **Monorepo, dos paquetes, un Compose.** Fundamento: la KB `08` exige `backend/` + `frontend/` + `docker-compose.yml` con 5 servicios; un solo repo mantiene al equipo de tamaño curso en un único flujo de revisión. Alternativa (repos separados) descartada — duplica el costo de CI/versionado para un sistema de 1–3 profesionales.
- **Núcleo FastAPI plano: `app/main.py` + `app/core/` (configuración, logging, errores) + `app/db/` (Base, sesión, entorno Alembic) + `app/domain/` vacío + stub de `app/workers/`.** Fundamento: coincide exactamente con el layout de la KB `08`; routers/servicios/repositorios llegan con C-02+. Convenciones de la skill FastAPI aplicadas: `def` sincrónico para el endpoint de health (bloquea en el ping a DB vía threadpool), estilo de dependencias `Annotated` reservado para consumidores de `get_session`, anotación de tipo de retorno como contrato de respuesta, sin `ORJSONResponse`. Alternativa (carpetas DDD completas ahora) descartada — estructura prematura sin dominio.
- **Pydantic Settings para configuración (`extra='forbid'` por R1), `TZ` por defecto `America/Argentina/Buenos_Aires`.** Fundamento: arranque tipado que falla rápido; TZ fija desde el día uno por RN-GL-03 para no arrastrar deuda de datetimes naive. `SECRET_KEY` requerida, con longitud mínima validada; los secretos nunca se loguean.
- **Sobre de errores `{code, message, details?}` vía excepción base de dominio + handler.** Fundamento: RN-GL-01 desde el primer endpoint; el cliente del frontend y todos los tests futuros asertan sobre `code`.
- **DB: SQLAlchemy 2 + Alembic, driver `psycopg`, línea base lista para `timestamptz`; fábrica de sesiones `get_session` como único punto de inyección.** Fundamento: el middleware de tenant de C-02 se engancha exactamente en esta fábrica (DD-02 "imposible olvidar el filtro"). Timestamps: solo datetimes aware (patrón `datetime.now(UTC)` según la skill sqlmodel). Alternativa (SQLModel ya) diferida — todavía no hay modelos de tablas; se retoma en C-02 cuando lleguen `Tenant`/`Usuario`.
- **Compose: `postgres:16`, `redis:7`, api (uvicorn), worker (RQ + stub de rq-scheduler), web (Vite dev).** Volumen con nombre para pgdata; healthchecks en postgres/redis que condicionan el arranque de api/worker. Alternativa (SQLite para dev) descartada — los EXCLUDE y trigram (C-05/C-07) necesitan Postgres real; la paridad dev/prod pesa más que la liviandad.
- **Frontend: Vite + React 18 + TS 5 estricto, `features/` + `shared/` + `pages/` + `routes.tsx` con guardianes `PublicRoute`/`PrivateRoute`; wrapper fetch en `shared/api` (sin barrel files según vercel-react-best-practices `bundle-barrel-imports`; imports directos).** Almacenamiento de auth mínimo y versionado (`client-localstorage-schema`); la lógica real de tokens va en C-03. Alternativa (Next.js) descartada — la KB fija SPA con Vite servida detrás de un único servicio Compose `web`.
- **CI: GitHub Actions, dos jobs paralelos (backend: ruff + pytest; frontend: tsc + vitest + build).** Fundamento: la señal más rápida por stack; con gobernanza BAJA el CI es la compuerta.

## Riesgos / Compromisos

- [Riesgo] Colisiones de puertos/volúmenes en las máquinas de los estudiantes → Mitigación: puertos estándar documentados en `.env.example`, el nombre del proyecto Compose aísla las redes.
- [Riesgo] Deriva de la línea base de Alembic cuando C-02 agregue tablas → Mitigación: la revisión base es vacía-pero-real; R7 se enforcea con chequeo de CI (`alembic check` / conteo de heads = 1).
- [Riesgo] Shell de frontend sobrediseñado antes de que existan las páginas reales → Mitigación: solo guardianes + cliente + páginas provisorias; sin sistema de diseño ni librería de componentes todavía.
- [Riesgo] Worker sin jobs parece muerto → Mitigación: job stub + chequeo de conexión para que C-11/C-12 se conecte a un worker ya probado.

## Plan de migración

Greenfield — sin migración. Despliegue/verificación: `cp .env.example .env && docker compose up --build`, después `GET /health` → 200, `vite dev` sirve el shell, CI en verde. Rollback: borrar los directorios generados (todavía no hay datos).

## Preguntas abiertas

- Ninguna bloqueante. Diferimientos menores (registrados como supuestos): `RECORDATORIO_VENTANA_HS` se guarda como string CSV `"24,48"` que se parsea en C-11; la imagen del worker reutiliza la imagen de api con otro comando; la URL de la API del frontend vía `VITE_API_URL`.
