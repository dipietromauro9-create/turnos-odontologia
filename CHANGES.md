# CHANGES — Secuencia de Implementación

> Índice canónico de todos los changes del proyecto **turnos-odontologia** (sistema web de turnos para consultorios odontológicos chicos, Argentina).
> Cada change es atómico: un agente puede implementarlo en una sesión (~4-6 horas).
> **Leer este archivo antes de ejecutar cualquier `/opsx:propose`.**
> MVP v1.0 = agenda multi-profesional + turnero público 24/7 + WA manual + ficha básica + reportes + export CSV. Post-MVP (MP, WA API, odontograma, OS, ARCA) fuera de alcance — ver `knowledge-base/11_post_mvp_e_integraciones.md`.

---

## Cómo usar este documento

1. Identificar el change a implementar (verificar que sus dependencias están en `openspec/changes/archive/`).
2. Leer los docs de la knowledge-base indicados en "Leer antes".
3. Ejecutar `/opsx:propose <nombre-del-change>`.
4. Al terminar el change, archivarlo con `/opsx:archive <nombre-del-change>`.
5. Marcar el checkbox `[x]` en este archivo.

---

## Árbol de dependencias

```
C-01 foundation-setup
  └── C-02 core-models-tenancy              ← tenant_id + middleware base
        └── C-03 auth-rbac                  ← desbloquea TODO lo protegido
              │
              ├── C-04 profesionales-prestaciones      [A]
              ├── C-05 pacientes-ficha                 [B]  ← paralelo con C-04
              └── C-06 disponibilidad-bloqueos         [C]  ← paralelo con C-04
                    │
                    └── C-07 turnos-state-machine      ← une C-04 + C-05 + C-06
                          │
                          ├── C-08 motor-disponibilidad  [A]
                          └── C-11 recordatorios-manuales [B]  ← solo necesita C-07
                                │
                                └── (GATE 6, cuando C-08 ✓)
                                      ├── C-09 turnero-publico   [C]
                                      ├── C-10 agenda-panel      [A]
                                      └── C-12 reportes-export   [B — si C-11 ✓]
```

### Paralelismo por fase

> Cada "gate" es un punto de sincronización. Los changes dentro de un grupo pueden ejecutarse en paralelo.

```
GATE 0: ninguna
  → C-01 (solo)

GATE 1: C-01 ✓
  → C-02 (solo)

GATE 2: C-02 ✓
  → C-03 (solo)

GATE 3: C-03 ✓                     ← PRIMER FORK (3 paralelos)
  → C-04 profesionales-prestaciones  [Agente A]
  → C-05 pacientes-ficha             [Agente B]
  → C-06 disponibilidad-bloqueos     [Agente C]

GATE 4: C-04 + C-05 + C-06 ✓
  → C-07 turnos-state-machine (solo)

GATE 5: C-07 ✓                     ← SEGUNDO FORK (2 paralelos)
  → C-08 motor-disponibilidad        [Agente A]
  → C-11 recordatorios-manuales      [Agente B]

GATE 6: C-08 ✓                      ← TERCER FORK (3 paralelos)
  → C-09 turnero-publico             [Agente C]
  → C-10 agenda-panel                [Agente A — si C-08 ✓]
  → C-12 reportes-export             [Agente B — si C-11 ✓]
```

### Camino crítico (7 changes — mínimo irreducible)

```
C-01 → C-02 → C-03 → C-04 → C-07 → C-08 → C-09
                                              ↳ *C-10 terminal alternativo (sin panel no hay operación interna)
```

### Plan óptimo con 3 agentes

```
Paso │ Agente A (Backend Core)      │ Agente B (Backend Aux)         │ Agente C (Frontend/Agenda)
─────┼──────────────────────────────┼────────────────────────────────┼─────────────────────────────
  1  │ C-01 foundation-setup        │ —                              │ —
  2  │ C-02 core-models-tenancy     │ —                              │ —
  3  │ C-03 auth-rbac               │ —                              │ —
  4  │ C-04 profesionales-prest.    │ C-05 pacientes-ficha           │ C-06 disponibilidad-bloqueos
  5  │ C-07 turnos-state-machine    │ — (apoya review C-07)          │ — (apoya review C-07)
  6  │ C-08 motor-disponibilidad    │ C-11 recordatorios-manuales    │ — (prepara shell turnero)
  7  │ C-10 agenda-panel            │ C-12 reportes-export           │ C-09 turnero-publico
```

---

## FASE 0 — Cimientos

### [C-01] `foundation-setup`
- **Estado**: `[x]` archivado (2026-10-06)
- **Scope**: Scaffolding completo del monorepo + infraestructura base
  - Estructura `backend/app/{core,domain/workers,db}` + `frontend/src/{features,shared,pages}` + `docker-compose.yml` (api + web + postgres 16 + redis 7 + worker)
  - `backend/`: FastAPI app mínima con `GET /health`, SQLAlchemy 2 + Alembic inicializado, `core/` con settings por entorno, logger, `db.session.get_session`, excepciones de dominio base `{"code": "RN-XX-NN"}` (RN-GL-01)
  - `frontend/`: Vite + React 18 + TS 5, `shared/api` client base, `routes.tsx` con guardia público/privado (vacía, se llena en C-09/C-10)
  - `.env.example` (DATABASE_URL, REDIS_URL, SECRET_KEY, ACCESS_MINUTES/REFRESH_DAYS, TENANT_DEFAULT_SLUG=demo, TZ=America/Argentina/Buenos_Aires, FRONTEND_ORIGIN, RECORDATORIO_VENTANA_HS) — RN-GL-03: TZ única fijada desde día 1
  - `pyproject.toml` (pytest) + CI GitHub Actions con jobs paralelos backend/frontend
  - Tests: health check, carga de settings, conexión DB en Compose
- **Dependencias**: ninguna
- **Governance**: BAJO
- **Leer antes**:
  - `knowledge-base/01_vision_y_objetivos.md` (qué es el sistema y alcance v1.0)
  - `knowledge-base/02_descripcion_general.md` §Stack tecnológico
  - `knowledge-base/08_arquitectura_propuesta.md` §Estructura de directorios
  - `knowledge-base/08_arquitectura_propuesta.md` §Variables de entorno

### [C-02] `core-models-tenancy`
- **Estado**: `[x]` archivado (2026-10-27)
- **Scope**: Núcleo multi-tenant + usuarios + base de patrones
  - Modelos: `Tenant` (slug inmutable unique), `Usuario` (email citext único por tenant, `rol` enum recepcion/profesional, `es_dueno` bool, constraint `es_dueno=true` solo si `rol=profesional`), `TenantMixin` (`tenant_id` FK + índices compuestos) y `AuditMixin` (timestamps)
  - Middleware de tenant: resuelve tenant (v1: `TENANT_DEFAULT_SLUG`), inyecta `tenant_id` en `get_session`; imposible olvidar el filtro (DD-02)
  - `BaseRepository[T]` + `UnitOfWork` transaccional (RN-GL-02: reserva/reprogramación/transiciones siempre atómicas)
  - Migración Alembic 001: tablas tenant + usuario; seed demo (tenant `demo`, `dueno@demo` profesional dueño, `recepcion@demo`)
  - Zona horaria: `timestamptz` everywhere, default America/Argentina/Buenos_Aires (RN-GL-03)
  - Tests: unicidad (tenant_id, email), constraint es_dueno, aislamiento multi-tenant (query de otro tenant no devuelve filas), seed idempotente
- **Dependencias**: C-01
- **Governance**: CRITICO
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` §Tenant
  - `knowledge-base/04_modelo_de_datos.md` §Usuario
  - `knowledge-base/08_arquitectura_propuesta.md` §Patrones aplicados
  - `knowledge-base/09_decisiones_y_supuestos.md` §DD-02

---

## FASE 1 — Acceso

### [C-03] `auth-rbac`
- **Estado**: `[ ]` pendiente
- **Scope**: Autenticación JWT + RBAC de 3 roles con dueño como flag
  - `POST /auth/login` (Argon2id, lockout tras 10 intentos fallidos, rate limit 5/60s por IP+email), `POST /auth/refresh` (rotación con blacklist), `POST /auth/logout`, `GET /auth/me`
  - JWT: access 15 min + refresh 7 días en cookie HttpOnly (secure, samesite=lax); claims `sub, tenant_id, roles, email, jti, type, iat, exp`
  - Dependencia `require_role(...)` por router + helper `es_dueno`; matriz de `03` aplicada (recepción nunca configura/usuarios/exports — RN-AU-02; profesional solo agenda propia salvo dueño — RN-AU-03)
  - Turnero público exento de JWT: opera con `codigo_publico` por turno (RN-AU-01), rate-limit 10 req/min por IP (detalle en C-09)
  - Tests: login ok/credenciales malas, access expirado, refresh rotation reusa token viejo → 401, RBAC (recepción → 403 en endpoints de dueño), lockout tras 10 intentos
- **Dependencias**: C-02
- **Governance**: CRITICO
- **Leer antes**:
  - `knowledge-base/03_actores_y_roles.md` (matriz RBAC + rutas públicas)
  - `knowledge-base/05_reglas_de_negocio.md` §Autenticación y autorización (RN-AU)
  - `knowledge-base/08_arquitectura_propuesta.md` §Seguridad
  - `knowledge-base/09_decisiones_y_supuestos.md` §DD-08

---

## FASE 2 — Directorio y agenda base

> Los changes C-04, C-05 y C-06 pueden proponerse en paralelo (GATE 3). Los tres deben archivarse antes de C-07.

### [C-04] `profesionales-prestaciones`
- **Estado**: `[ ]` pendiente
- **Scope**: Catálogo clínico-administrativo que todo turno referencia (US-008 parcial)
  - Modelos: `Profesional` (usuario_id unique nullable, matrícula/especialidad nullables, índice (tenant_id, activo)), `Prestacion` (duracion_min múltiplo de 5 > 0, precio_ref informativo, índice (tenant_id, activa))
  - Endpoints dueño-only: `GET/POST/PATCH /profesionales`, `GET/POST/PATCH /prestaciones` (+ desactivar, sin borrado físico de referenciadas)
  - Regla: cambiar `duracion_min` no altera turnos existentes — duración congelada vía `fin` (RN-AG-03)
  - Migración 002: tablas profesional + prestacion; seed prestaciones demo (Consulta 30, Limpieza 60, Extracción 45, Control 20, Urgencia 30) + disponibilidad Lun–Vie 9–13/16–20 demo (si C-06 no existe aún, el seed de disponibilidad vive aquí como filas SQL, el CRUD en C-06)
  - Tests: CRUD dueño ok, recepción → 403, duracion_min inválida → 422 `RN-AG-03`, aislamiento por tenant
- **Dependencias**: C-03
- **Governance**: MEDIO
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` §Profesional
  - `knowledge-base/04_modelo_de_datos.md` §Prestacion
  - `knowledge-base/05_reglas_de_negocio.md` §Agenda y disponibilidad (RN-AG-02, RN-AG-03)
  - `knowledge-base/06_funcionalidades.md` §US-008

### [C-05] `pacientes-ficha`
- **Estado**: `[ ]` pendiente
- **Scope**: Ficha básica del paciente + búsqueda (US-009)
  - Modelo: `Paciente` (nombre, teléfono, documento/fecha_nac nullables, observaciones ficha básica; duplicados (nombre, teléfono) advertidos no bloqueados; índices (tenant_id, teléfono) + trigram (tenant_id, nombre))
  - Endpoints `GET/POST/PATCH /pacientes` (recepción CRUD todos; profesional CRUD sus pacientes, resto 403 — RN-AU-03; jamás expuesto en rutas públicas — RN-PA-02)
  - Búsqueda `GET /pacientes?q=` por nombre (trigram) y teléfono; match por teléfono para reutilización en reserva (RN-PA-01, usado por C-09)
  - Borrado físico permitido en v1 con nota de deuda explícita en código/doc (RN-PA-03, DD-07, IN-01)
  - Migración 003: tabla paciente; seed 2 pacientes demo
  - Tests: búsqueda trigram, duplicado → 201 + advertencia (contrato que C-09 consume), RN-PA-02 (paciente no visible sin login), aislamiento por tenant
- **Dependencias**: C-03
- **Governance**: MEDIO
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` §Paciente
  - `knowledge-base/05_reglas_de_negocio.md` §Pacientes (RN-PA)
  - `knowledge-base/06_funcionalidades.md` §US-009
  - `knowledge-base/10_preguntas_abiertas.md` §IN-01

### [C-06] `disponibilidad-bloqueos`
- **Estado**: `[ ]` pendiente
- **Scope**: Plantilla semanal + cierres puntuales (US-008)
  - Modelos: `Disponibilidad` (profesional_id, dia_semana 0–6, hora_desde/hasta; constraints hora_hasta > hora_desde, sin duplicados por profesional/día/rango), `Bloqueo` (profesional_id nullable, desde/hasta; `hasta > desde`; profesional nulo = cierra todo el consultorio — RN-AG-02)
  - Endpoints dueño-only: `GET/POST/DELETE /disponibilidad`, `GET/POST/DELETE /bloqueos` (recepción R, profesional R propia)
  - Migración 004: tablas disponibilidad + bloqueo
  - Tests: bloqueo null cierra consultorio (RN-AG-02), rangos inválidos → 422, recepción no puede crear (403), aislamiento por tenant
- **Dependencias**: C-03 (usa Profesional de C-04 solo como FK; si C-04 no está archivado, crear contra su contrato de `04_modelo_de_datos.md` y verificar integración en C-07)
- **Governance**: MEDIO
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` §Disponibilidad (plantilla semanal)
  - `knowledge-base/04_modelo_de_datos.md` §Bloqueo
  - `knowledge-base/05_reglas_de_negocio.md` §Agenda y disponibilidad (RN-AG-01, RN-AG-02)
  - `knowledge-base/06_funcionalidades.md` §US-008

---

## FASE 3 — Núcleo de turnos

### [C-07] `turnos-state-machine`
- **Estado**: `[ ]` pendiente
- **Scope**: Entidad Turno + máquina de estados explícita + endpoints internos (US-006, US-007)
  - Modelo `Turno`: profesional/paciente/prestación FK, `inicio/fin` timestamptz, `estado` enum (reservado, confirmado, atendido, cancelado, ausente), `codigo_publico` varchar(12) unique ≥70 bits entropía, `es_sobreturno` bool, `motivo_cancelacion` nullable
  - **Anti-solape**: `EXCLUDE USING gist (profesional_id WITH =, tsrange(inicio, fin) WITH &&) WHERE (estado NOT IN ('cancelado'))` + validación previa en servicio para error legible `RN-TU-01` (RN-GL-01)
  - Servicio: `fin = inicio + duracion(prestacion)` calculado en backend, cliente nunca envía `fin` (RN-TU-02); máquina `reservado → confirmado|cancelado`, `confirmado → atendido|cancelado|ausente`, terminales sin salida, otra transición → 422 con código (RN-TU-04); todo transaccional (RN-GL-02); solo `cancelado` libera hueco, `ausente` conserva historial (RN-TU-05)
  - Endpoints internos: `GET/POST /turnos`, `GET/PATCH /turnos/:id`, `POST /turnos/:id/confirmar|/cancelar|/registrar-ausencia|/reprogramar` (interna); sobreturno exige `es_sobreturno=true` + motivo urgencia y nace `confirmado`, sin excepcionar RN-TU-01 (RN-TU-03, flujo 4 de `07`)
  - Migración 005: tabla turno + EXCLUDE + índices ((tenant_id, profesional_id, inicio), codigo_publico, (tenant_id, estado, inicio)); seed 3 turnos demo (reservado, confirmado, atendido)
  - Tests: anti-solape concurrente (doble insert → 409 `RN-TU-01`), cada transición válida/inválida de RN-TU-04, sobreturno con/sin motivo, `ausente` no libera hueco, RBAC (profesional solo propios)
- **Dependencias**: C-04, C-05, C-06
- **Governance**: CRITICO
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` §Turno
  - `knowledge-base/05_reglas_de_negocio.md` §Turnos (RN-TU)
  - `knowledge-base/06_funcionalidades.md` §US-006
  - `knowledge-base/06_funcionalidades.md` §US-007
  - `knowledge-base/07_flujos_principales.md` §Flujo 4

### [C-08] `motor-disponibilidad`
- **Estado**: `[ ]` pendiente
- **Scope**: Cálculo de huecos reservables (corazón del turnero, RN-AG-01)
  - Servicio puro `calcular_huecos(profesional, prestación, desde, hasta)`: disponibilidad semanal − bloqueos (incl. null = todo cerrado) − turnos activos, solo `inicio` futuro, granularidad = duracion_min de la prestación; `GET /disponibilidad?profesional=&prestacion=&desde=&hasta=` paginado por rango, < 1 s por semana
  - Respuesta pública-compatible: solo huecos, cero datos de pacientes (RN-AG-04) — el envoltorio público con slug va en C-09, aquí el motor + endpoint interno
  - Tests: hueco dentro/fuera de disponibilidad, intersectado por bloqueo parcial y total, ocupado por turno activo vs. libre por cancelado, inicio pasado excluido, prestación con distinta duración cambia la grilla, performance semana < 1 s
- **Dependencias**: C-07 (requiere C-06 y C-04 ya archivados vía C-07)
- **Governance**: ALTO
- **Leer antes**:
  - `knowledge-base/05_reglas_de_negocio.md` §Agenda y disponibilidad (RN-AG-01, RN-AG-04)
  - `knowledge-base/04_modelo_de_datos.md` §Disponibilidad (plantilla semanal)
  - `knowledge-base/07_flujos_principales.md` §Flujo 1
  - `knowledge-base/06_funcionalidades.md` §US-001

---

## FASE 4 — Canales (público + panel + comunicación)

> C-09, C-10 y C-12 pueden proponerse en paralelo cuando C-08 está archivado (GATE 6). C-11 arranca en GATE 5 (solo necesita C-07).

### [C-09] `turnero-publico`
- **Estado**: `[ ]` pendiente
- **Scope**: Turnero online 24/7 sin cuenta (US-001, US-002, US-003, US-004)
  - Endpoints públicos por slug: `GET /turnero/:slug/disponibilidad` (solo huecos, RN-AG-04), `POST /turnero/:slug/reservas` (nombre + teléfono; transacción busca/crea paciente por teléfono con advertencia de duplicado RN-PA-01, crea turno `reservado` con `fin` calculado y `codigo_publico`; → 201 + código; hueco ocupado → 409 `RN-TU-01` legible), `GET /turnero/mis-turnos?codigo=`, `POST /turnero/mis-turnos/cancelar|/reprogramar` (exige código RN-TU-06, 404 genérico si inválido; reprogramación atómica — sin hueco destino el original queda intacto RN-TU-07; cancelación guarda motivo y libera hueco RN-TU-05)
  - Rate limit 10 req/min por IP en rutas públicas; códigos de error RN-XX-NN en toda respuesta (RN-GL-01)
  - Frontend `features/turnero-publico` + `pages//turnero/:slug`: semana navegable, filtro profesional/prestación, formulario reserva, pantalla de código (sugerir guardarlo), vista mis-turnos con cancelar/reprogramar
  - Tests: reserva E2E crea paciente + turno, duplicado telefónico advierte, doble-clic concurrente → un 201 + un 409, reprogramación fallida deja original intacto, código inválido → 404 sin enumerar, rate limit
- **Dependencias**: C-08
- **Governance**: ALTO
- **Leer antes**:
  - `knowledge-base/06_funcionalidades.md` §Épica 1 (US-001 a US-004)
  - `knowledge-base/07_flujos_principales.md` §Flujo 1
  - `knowledge-base/07_flujos_principales.md` §Flujo 3
  - `knowledge-base/03_actores_y_roles.md` §Rutas públicas
  - `knowledge-base/05_reglas_de_negocio.md` §Turnos (RN-TU-05, RN-TU-06, RN-TU-07)

### [C-10] `agenda-panel`
- **Estado**: `[ ]` pendiente
- **Scope**: Panel interno día/semana multi-profesional (US-005 + UI de US-006/US-007/US-008)
  - Frontend `features/agenda` + `pages//app/*`: vista día y semana con colores por estado, filtro por profesional (recepción/dueño todos; profesional solo propia — RN-AU-03), crear turno interno + sobreturno con flag explícito (usa endpoints de C-07), botones de transición (confirmar/atender/ausencia/cancelar) con mensajes por código RN-XX-NN, gestión de disponibilidad/bloqueos (dueño)
  - Sin endpoints nuevos salvo `GET /agenda/dia|/semana` agregador si el filtrado cliente resulta insuficiente (justificar en propose)
  - Tests frontend (Vitest): RBAC de vistas, colores por estado, transición inválida muestra error de regla; tests backend del agregador si se crea
- **Dependencias**: C-07, C-08
- **Governance**: MEDIO
- **Leer antes**:
  - `knowledge-base/06_funcionalidades.md` §US-005
  - `knowledge-base/03_actores_y_roles.md` (matriz RBAC)
  - `knowledge-base/08_arquitectura_propuesta.md` §Estructura de directorios
  - `knowledge-base/05_reglas_de_negocio.md` §Turnos (RN-TU-03, RN-TU-04)

### [C-11] `recordatorios-manuales`
- **Estado**: `[ ]` pendiente
- **Scope**: Cola WA manual con generación programada (US-010, US-011)
  - Modelo `Recordatorio` (turno FK, canal enum `whatsapp_manual`, texto por plantilla, estado pendiente/enviado/fallido, enviado_por nullable; constraint un pendiente por turno y tipo — RN-CO-01) + migración 006
  - Worker RQ `generar_recordatorios` + rq-scheduler cada hora: crea un pendiente por turno confirmado en ventana 24–48 h (`RECORDATORIO_VENTANA_HS`), idempotente; job `export_csv` NO aquí (va en C-12)
  - Endpoints: `GET /recordatorios/pendientes` (cola recepción, índice (tenant_id, estado)), `POST /recordatorios/:id/enviado|/fallido` (registra enviado_por — RN-CO-03; fallido sigue visible para reintento)
  - Plantilla: nombre, profesional, fecha/hora (TZ RN-GL-03), dirección; texto copiable en un clic (frontend `features/recordatorios`)
  - Tests: scheduler genera exactamente 1 por turno (re-ejecución no duplica), ventana 24–48 h respetada, marcar enviado guarda quién, fallido reintentable, worker caído → regenera al recuperarse
- **Dependencias**: C-07
- **Governance**: ALTO
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` §Recordatorio
  - `knowledge-base/05_reglas_de_negocio.md` §Comunicación (RN-CO)
  - `knowledge-base/07_flujos_principales.md` §Flujo 2
  - `knowledge-base/06_funcionalidades.md` §US-010
  - `knowledge-base/06_funcionalidades.md` §US-011

---

## FASE 5 — Gestión y cierre MVP

### [C-12] `reportes-export`
- **Estado**: `[ ]` pendiente
- **Scope**: Métricas de gestión + exportación anti-lock-in (US-012, US-013) — cierra el MVP
  - Endpoints: `GET /reportes/ocupacion` (turnos activos / huecos disponibles por profesional y período) y `GET /reportes/ausencias` (`ausente` / (atendido + ausente)) — fórmulas RN-RP-01, rango seleccionable; dueño ve consolidado, profesional solo lo propio, recepción 403 (RN-AU-02)
  - Export: `POST /export/turnos.csv|/pacientes.csv?desde=&hasta=` → 202 + job_id (worker RQ genera CSV con `tenant_id` + timestamp en primera línea de metadata — RN-RP-02), `GET /export/:job_id` estado/descarga; dueño-only; reintento con un clic si falla, nunca bloquea la API (flujo 5 de `07`)
  - Frontend `features/reportes`: selectores de período/profesional, tablas, botón exportar con estado de job
  - Métrica intermedia IN-03: incluir "recordatorios enviados / turnos confirmados" en reportes (distingue falla de adopción vs. falla de producto)
  - Tests: fórmulas RN-RP-01 contra seed conocido, RBAC por rol, export contiene metadata, job fallido → estado failed + reintento ok
- **Dependencias**: C-07 (si C-11 está archivado, reutilizar su worker/scheduler setup; no bloquearse en él)
- **Governance**: MEDIO
- **Leer antes**:
  - `knowledge-base/05_reglas_de_negocio.md` §Reportes y exportación (RN-RP)
  - `knowledge-base/06_funcionalidades.md` §US-012
  - `knowledge-base/06_funcionalidades.md` §US-013
  - `knowledge-base/07_flujos_principales.md` §Flujo 5
  - `knowledge-base/10_preguntas_abiertas.md` §IN-03

---

## Checklist de validación al cerrar

- [x] El header dice "CHANGES — Secuencia de Implementación".
- [x] La sección "Cómo usar este documento" tiene los 5 pasos numerados.
- [x] El "Árbol de dependencias" usa ASCII art con `└──` y `│`.
- [x] Hay al menos un GATE por cada fork de paralelismo detectado.
- [x] El camino crítico tiene una flecha lineal sin ramas.
- [x] La tabla de "Plan óptimo con 3 agentes" tiene 3 columnas y los pasos enumerados.
- [x] Cada change tiene exactamente 5 campos: Estado, Scope, Dependencias, Governance, Leer antes.
- [x] Cada "Leer antes" tiene 3 a 5 archivos KB con sección cuando aplique.
- [x] El Scope tiene bullets operacionales (modelos, endpoints, migraciones, tests).
- [x] Cada Governance tiene uno de los 4 niveles: BAJO, MEDIO, ALTO, CRITICO.
- [x] Los changes están agrupados en FASES con nombres semánticos (no "Fase 1, 2, 3" pelados).

## Resumen

| Fase | Changes | Contenido |
|---|---|---|
| FASE 0 — Cimientos | C-01, C-02 | Compose + scaffolding, tenant + usuarios |
| FASE 1 — Acceso | C-03 | JWT + RBAC 3 roles |
| FASE 2 — Directorio y agenda base | C-04, C-05, C-06 | Profesionales/prestaciones, pacientes, disponibilidad/bloqueos |
| FASE 3 — Núcleo de turnos | C-07, C-08 | State machine + EXCLUDE, motor de huecos |
| FASE 4 — Canales | C-09, C-10, C-11 | Turnero público, agenda panel, recordatorios WA manual |
| FASE 5 — Gestión y cierre MVP | C-12 | Reportes + export CSV |

**12 changes, 6 fases, 7 gates, camino crítico de 7 changes. Primer change recomendado: `C-01` (foundation-setup). Para arrancar: `/opsx:propose C-01-foundation-setup`.**
