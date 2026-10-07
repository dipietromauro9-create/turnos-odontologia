# Tareas

## 1. Andamiaje del repo y contrato de entorno

- [x] 1.1 Crear la estructura del monorepo (`backend/app/{core,domain,workers,db}`, `backend/tests/`, `frontend/src/{features,shared,pages}`) y verificar que el árbol coincide con `08` §Estructura de directorios
- [x] 1.2 Crear `.env.example` con las 8 variables (`DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`, `ACCESS_MINUTES`, `REFRESH_DAYS`, `TENANT_DEFAULT_SLUG=demo`, `TZ=America/Argentina/Buenos_Aires`, `FRONTEND_ORIGIN`, `RECORDATORIO_VENTANA_HS`) y verificar que cada una tenga un valor de ejemplo sensato y ningún secreto real
- [x] 1.3 Agregar `.gitignore` (env, venv, node_modules, dist, `__pycache__`) y verificar que `git status` no muestra archivos generados como trackeados

## 2. Base del backend (FastAPI + configuración + errores + DB + Alembic)

- [x] 2.1 Agregar `backend/pyproject.toml` (Python ≥3.12, fastapi ≥0.110, sqlalchemy 2, alembic, pydantic v2 + settings, psycopg, pytest) con config de ruff y verificar que `pip install -e .` (o `uv sync`) resuelve sin conflictos
- [x] 2.2 Implementar `app/core/settings.py` (Pydantic Settings, `extra='forbid'` por R1, `TZ` por defecto `America/Argentina/Buenos_Aires`, `SECRET_KEY` con longitud mínima) más logger estructurado, y verificar que `pytest tests/test_settings.py` pasa (arranca con env válido, falla rápido nombrando la variable faltante, nunca loguea secretos)
- [x] 2.3 Implementar la excepción base de dominio + handler que emite `{"code": "RN-XX-NN", "message", "details?"}` (RN-GL-01) y verificar con un test unitario que aserta la forma del sobre y el estado 4xx para una regla conocida
- [x] 2.4 Implementar `app/db/` (Base, motor + fábrica `get_session` como único punto de inyección, convención de datetimes aware) y `app/main.py` con `GET /health` público (`def` sincrónico, anotación de tipo de retorno, ping a DB) más CORS restringido a `FRONTEND_ORIGIN`, y verificar que `pytest tests/test_health.py` pasa (200 `{"status": "ok"}` sin autenticación, con indicador de DB presente)
- [x] 2.5 Inicializar Alembic (env importa los metadatos de Base, revisión base vacía, `alembic upgrade head` limpio sobre Postgres 16 vacío) y verificar que `alembic check` (o conteo de heads = 1) pasa

## 3. Shell del frontend (Vite + React 18 + TS 5 estricto)

- [x] 3.1 Armar la app Vite + React 18 + TS 5 con `tsconfig` estricto (strict true, `noImplicitAny`, lint que prohíbe `any` por R2) y componentes provisorios en PascalCase, y verificar que `tsc --noEmit` pasa
- [x] 3.2 Implementar el cliente tipado en `shared/api` (URL base desde `VITE_API_URL`, manejo JSON, propaga el `code: RN-XX-NN` del backend en fallos, único punto de attach de auth) solo con imports directos (sin barrel files) y verificar con un test Vitest que aserta el passthrough del código de regla
- [x] 3.3 Implementar `routes.tsx` con guardianes `PublicRoute`/`PrivateRoute` (anónimo → pública renderiza, anónimo → privada redirige al login provisorio) y verificar que los tests de router en Vitest cubren ambas ramas

## 4. Compose, stub del worker y CI

- [x] 4.1 Escribir `docker-compose.yml` (api + web + postgres 16 + redis 7 + worker que reutiliza la imagen de api con comando de worker, volumen con nombre para pgdata, healthchecks que condicionan api/worker) y verificar que `docker compose up --build -d` levanta los 5 servicios sanos
- [x] 4.2 Agregar el stub del worker (`workers/` con job provisorio + chequeo de conexión RQ/scheduler) y verificar que el contenedor del worker se conecta a Redis sin entrar en crash-loop
- [x] 4.3 Agregar CI con GitHub Actions con jobs paralelos de backend (ruff + pytest) y frontend (tsc + vitest + build) y verificar que el YAML del workflow parsea y ambos jobs pasan en este change

## 5. Verificación de punta a punta

- [x] 5.1 Levantar el stack completo desde cero (`cp .env.example .env && docker compose up --build`) y verificar que `GET /health` → 200, el shell del frontend renderiza y la prueba de humo de conectividad a DB pasa
- [x] 5.2 Correr `openspec validate --change c-01-foundation-setup --strict` y verificar cero errores (los specs parsean, cada requisito tiene su `#### Scenario`, Propósito ≥ 50 caracteres)
