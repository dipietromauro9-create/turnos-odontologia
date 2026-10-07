# turnos-odontologia — Instrucciones para Agentes

> Este archivo (y su copia `CLAUDE.md`) es lo PRIMERO que todo agente lee al entrar al repo.
> Generado a partir de `knowledge-base/` y `CHANGES.md`. No editar a mano sin re-sincronizar ambos archivos.

---

## Stack Tecnológico

| Capa | Tecnología | Versión mínima |
|------|------------|----------------|
| Backend | Python + FastAPI + SQLAlchemy 2 + Alembic + Pydantic v2 | Python 3.12, FastAPI 0.110 |
| Base de datos | PostgreSQL | 16 |
| Cola / jobs | Redis + RQ (+ rq-scheduler) | Redis 7 |
| Frontend | React + Vite + TypeScript | React 18, TS 5 |
| Auth | JWT (access 15 min + refresh 7 días) + RBAC 3 roles | — |
| Tests | pytest (backend) + Vitest (frontend) | — |
| Deploy | Docker Compose (api + web + postgres + redis + worker) | — |
| Integraciones v1 | Ninguna obligatoria (WA manual) | — |

Detalle completo: [knowledge-base/02_descripcion_general.md](knowledge-base/02_descripcion_general.md)

---

## Base de Conocimiento

La fuente de verdad del dominio vive en `knowledge-base/`. **Leé el archivo relevante ANTES de implementar.**

| Archivo | Cuándo leerlo |
|---------|---------------|
| [01_vision_y_objetivos.md](knowledge-base/01_vision_y_objetivos.md) | Entender propósito y alcance |
| [02_descripcion_general.md](knowledge-base/02_descripcion_general.md) | Stack, arquitectura, API REST |
| [03_actores_y_roles.md](knowledge-base/03_actores_y_roles.md) | Auth, RBAC, permisos |
| [04_modelo_de_datos.md](knowledge-base/04_modelo_de_datos.md) | Entidades, ERD, migraciones |
| [05_reglas_de_negocio.md](knowledge-base/05_reglas_de_negocio.md) | Reglas codificadas (RN-XX) |
| [06_funcionalidades.md](knowledge-base/06_funcionalidades.md) | Historias de usuario por épica |
| [07_flujos_principales.md](knowledge-base/07_flujos_principales.md) | Flujos E2E |
| [08_arquitectura_propuesta.md](knowledge-base/08_arquitectura_propuesta.md) | Patrones, estructura, env vars |
| [09_decisiones_y_supuestos.md](knowledge-base/09_decisiones_y_supuestos.md) | Decisiones DD + supuestos SU |
| [10_preguntas_abiertas.md](knowledge-base/10_preguntas_abiertas.md) | ⚠️ Inconsistencias a resolver ANTES de codear |
| [11_post_mvp_e_integraciones.md](knowledge-base/11_post_mvp_e_integraciones.md) | Alcance post-MVP (MP, ARCA, OS, WA API) |

> ⚠️ Resolver las preguntas de prioridad **Alta** de `10_preguntas_abiertas.md` antes de arrancar el primer change (IN-01 auditoría vs. ley, piloto, odontograma en v1).

---

## Skills Disponibles

| Agente | Rol | Skills que carga |
|--------|-----|------------------|
| **Backend Core** | FastAPI, Pydantic, SQLAlchemy, migraciones | `fastapi`, `sqlmodel` |
| **Frontend** | React+TS, UX de agenda/turnero, E2E | `vercel-react-best-practices`, `frontend-design`, `playwright` |
| **Transversal** | Diagnóstico de bugs (ej. lógica anti-solape) | `diagnosing-bugs` |

Cargá la skill correspondiente al contexto ANTES de escribir código.

> Los compact rules de cada skill los resuelve el orquestador desde `.atl/skill-registry.md` (generado por `skill-registry`; no versionado — no está en el repo). Esta tabla solo mapea skill→rol.

---

## Roadmap de Changes

El plan de implementación completo está en [CHANGES.md](CHANGES.md). Resumen:

- **Total**: 12 changes en 6 fases (Cimientos → Acceso → Directorio y agenda base → Núcleo de turnos → Canales → Gestión y cierre MVP).
- **Camino crítico** (7): `C-01 → C-02 → C-03 → C-04 → C-07 → C-08 → C-09`.
- **Primer change**: `C-01` (foundation-setup — Compose + scaffolding).

**Antes de cualquier `/opsx:propose`**: leé [CHANGES.md](CHANGES.md), identificá las dependencias del change y los archivos de "Leer antes".

---

## Reglas Duras

> No existe `~/.claude/CLAUDE.md` global en este entorno: este archivo incluye las reglas universales que de otro modo se heredarían (U1–U3) + las específicas del proyecto confirmadas (R1–R9). Son contrato; romperlas es un defecto.

**Específicas del proyecto:**
- **R1.** NUNCA schema Pydantic sin `extra='forbid'` → rechazar campos no declarados.
- **R2.** NUNCA `any` en TypeScript → tipado estricto (`tsconfig` strict); componentes en PascalCase.
- **R3.** NUNCA query de dominio sin filtro `tenant_id` → usar la sesión/middleware del core.
- **R4.** NUNCA crear ni transicionar un turno fuera del servicio de turnos → máquina RN-TU-04 + anti-solape siempre vigentes.
- **R5.** NUNCA exponer datos de pacientes en rutas públicas → el turnero solo muestra huecos (RN-AG-04).
- **R6.** NUNCA enviar `fin` de turno desde el cliente → lo calcula el backend (RN-TU-02).
- **R7.** NUNCA cambiar un modelo sin su migración Alembic → schema y migraciones siempre en sync.
- **R8.** NUNCA cerrar un change con reglas RN en rojo → tests de reglas críticas en verde.
- **R9.** NUNCA almacenar datos reales de pacientes en el repositorio ni en los ejemplos → usar siempre datos mock/anonimizados cumpliendo privacidad médica.

**Universales (sin global que las cubra):**
- **U1.** NUNCA commitear ni pushear sin pedido explícito → proponer el commit y esperar.
- **U2.** Commits en formato conventional commits, sin co-autoría de IA.
- **U3.** NUNCA instalar dependencias del proyecto sin avisar qué y por qué.

---

## Flujo de Trabajo

```
1. Leer la KB relevante (knowledge-base/)        → entender el dominio
2. Identificar el change en CHANGES.md           → respetar dependencias
3. /opsx:propose C-NN-nombre                     → proposal + design + specs + tasks
4. Implementar las tasks (cargando skills)       → respetando las reglas duras
5. /opsx:archive C-NN-nombre + marcar [x]        → cerrar el change
```

Aplicar TODAS las reglas duras en cada paso. Ante conflicto entre la KB y este archivo, las reglas duras prevalecen.
