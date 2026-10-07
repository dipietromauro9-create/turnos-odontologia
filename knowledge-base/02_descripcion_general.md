# Descripción General

## Stack tecnológico

Propuesto por el equipo técnico (P4:a — sin restricciones impuestas). Criterio director: **mantenibilidad primero** (P5:b) para equipo chico y materia, con deploy simple y frontera multi-tenant.

| Capa | Tecnología | Versión mínima | Por qué |
|---|---|---|---|
| Backend | Python + FastAPI + SQLAlchemy 2 + Alembic + Pydantic v2 | Python 3.12, FastAPI 0.110 | Tipado punta a punta, validación automática, OpenAPI gratis, testeo simple con pytest |
| Base de datos | PostgreSQL | 16 | Relacional (agenda = integridad referencial + exclusiones), `tenant_id` desde día 1, export CSV trivial |
| Frontend | React + Vite + TypeScript | React 18, TS 5 | Panel interno + turnero público en el mismo deploy (rutas públicas vs. privadas) |
| Auth | JWT (access corto + refresh) + RBAC por rol | — | 3 roles (P3:a); dueño = profesional con permiso extra |
| Jobs / async | Redis + RQ (+ rq-scheduler para recordatorios programados) | Redis 7 | Cola real desde día 1: recordatorios y exports CSV sin bloquear la API; worker separado en Compose |
| Deploy | Docker Compose (api + web + postgres + redis + worker) | — | Un servidor/PaaS, costo mínimo, reproducible para la materia |
| Tests | pytest (backend) + Vitest (frontend) | — | P5:b lo exige: cobertura en reglas de turno (anti-solape, máquina de estados) desde día 1 |

**Decisión confirmada por el equipo**: stack Python (FastAPI + SQLAlchemy + Postgres + Redis) y React + TS + Vite. RQ como cola (simpleza sobre Celery); si el volumen futuro lo exige, migrar a Celery queda documentado en `09`.

## Arquitectura general

Monolito modular con frontera multi-tenant lógica:

```
                    ┌─────────────────────────────┐
                    │  Frontend (React+Vite+TS)   │
                    │  /turnero/:slug (público)   │
                    │  /app/* (panel con login)   │
                    └──────────────┬──────────────┘
                                   │ REST/JSON
                    ┌──────────────▼──────────────┐
                    │  API (FastAPI)              │
                    │  routers → services →       │
                    │  repositories (SQLAlchemy)  │
                    │  + tenant middleware        │
                    │  + encola jobs (RQ)         │
                    └──────────────┬──────────────┘
                        ┌──────────┴──────────┐
                        ▼                     ▼
           ┌────────────────────┐  ┌────────────────────┐
           │  PostgreSQL 16     │  │  Redis 7 + RQ      │
           │  tenant_id en      │  │  worker + scheduler│
           │  dominio           │  │  (recordatorios,   │
           └────────────────────┘  │   exports CSV)     │
                                   └────────────────────┘
```

Decisiones de alto nivel:
- **Monolito, no microservicios**: un consultorio, un deploy; la modularidad es por capas/dominios, no por red.
- **Frontera multi-tenant preparada, no implementada**: toda tabla de dominio lleva `tenant_id` + índice compuesto; un middleware resuelve el tenant (v1: tenant único por defecto). El día que haya N consultorios no se migra el esquema, solo se enciende el aislamiento (detalle en `08`).
- **Turnero público aislado por slug**: el link público (`/turnero/:slug`) expone solo disponibilidad y reserva, nunca datos de otros pacientes.
- **WA manual en v1**: el backend genera el texto del recordatorio (plantilla por estado) y la recepción lo envía; el cambio de estado lo hace la recepción en el panel. Sin dependencias externas obligatorias.

## Integraciones externas

| Servicio | Propósito | Tipo | Etapa |
|---|---|---|---|
| Ninguno obligatorio en v1 | — | — | v1.0 |
| WhatsApp API oficial (Meta) | Envío automático de recordatorios/confirmaciones | REST + webhooks | Post-MVP (ver `11`) |
| Mercado Pago | Señas y cobros atados al turno | SDK + webhooks | Post-MVP (ver `11`) |
| ARCA | Factura electrónica | WS AFIP/ARCA | Post-MVP (ver `11`) |
| Google Calendar | Sincronización de agenda profesional | REST/OAuth | Post-MVP (ver `11`) |

## API REST

Agrupada por recurso (detalle de contratos en `08`, flujos en `07`):

- `POST /auth/login · POST /auth/refresh` — sesiones por rol.
- `GET/POST/PATCH /profesionales` — staff del consultorio (dueño gestiona).
- `GET/POST/PATCH /prestaciones` — catálogo con duración y precio referencial.
- `GET /disponibilidad?profesional=&desde=&hasta=` — huecos calculados (pública, por slug).
- `GET/POST /turnos · GET/PATCH/DELETE /turnos/:id` — CRUD + transiciones de estado (`POST /turnos/:id/confirmar`, `/cancelar`, `/registrar-ausencia`, `/reprogramar`).
- `GET/POST/PATCH /pacientes` — ficha básica + búsqueda.
- `GET /recordatorios/pendientes` — cola manual de mensajes a enviar (v1).
- `GET /reportes/ocupacion · /reportes/ausencias` — métricas v1.
- `GET /export/turnos.csv · /export/pacientes.csv` — exportación abierta.
