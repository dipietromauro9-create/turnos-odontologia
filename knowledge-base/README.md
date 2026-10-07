# turnos-odontologia — Base de Conocimiento

Base de conocimiento generada interactivamente (rondas estratégicas P0–P2 + Ronda 2) sobre el Discovery previo (`discovery/` — 18 competidores). Fuente: `interactive`.

## Índice de Archivos

| Archivo | Contenido |
|---------|-----------|
| [01_vision_y_objetivos.md](01_vision_y_objetivos.md) | Propósito, objetivos por actor, alcance v1.0, fuera de alcance, métricas |
| [02_descripcion_general.md](02_descripcion_general.md) | Stack (FastAPI + Postgres + Redis/RQ + React/TS), arquitectura, API REST |
| [03_actores_y_roles.md](03_actores_y_roles.md) | Actores, matriz RBAC (3 roles), rutas públicas |
| [04_modelo_de_datos.md](04_modelo_de_datos.md) | 9 entidades, ERD, anti-solape EXCLUDE, seed demo |
| [05_reglas_de_negocio.md](05_reglas_de_negocio.md) | 20 reglas RN-TU/AG/PA/CO/AU/RP/GL |
| [06_funcionalidades.md](06_funcionalidades.md) | 5 épicas, 13 historias US-001–US-013 |
| [07_flujos_principales.md](07_flujos_principales.md) | 5 flujos e2e con secuencias y errores |
| [08_arquitectura_propuesta.md](08_arquitectura_propuesta.md) | Patrones, directorios, seguridad, env vars |
| [09_decisiones_y_supuestos.md](09_decisiones_y_supuestos.md) | 9 decisiones DD + 4 supuestos SU |
| [10_preguntas_abiertas.md](10_preguntas_abiertas.md) | 3 inconsistencias + 8 preguntas priorizadas |
| [11_post_mvp_e_integraciones.md](11_post_mvp_e_integraciones.md) | Post-MVP ordenado (MP, WA API, odontograma, OS, ARCA) |

## Quick Start para Desarrolladores

1. Entender el dominio → [01](01_vision_y_objetivos.md), [03](03_actores_y_roles.md)
2. Entender los datos → [04](04_modelo_de_datos.md)
3. Entender las reglas → [05](05_reglas_de_negocio.md)
4. Entender la arquitectura → [02](02_descripcion_general.md), [08](08_arquitectura_propuesta.md)
5. Implementar → [07](07_flujos_principales.md), [06](06_funcionalidades.md)
6. Antes de codificar → [10](10_preguntas_abiertas.md)

## Resumen Ejecutivo

Sistema web de turnos odontológicos para consultorios chicos AR: agenda multi-profesional con anti-solape a nivel DB, turnero público 24/7 sin cuentas, recordatorios WhatsApp manuales y ficha básica — monolito FastAPI + React con frontera multi-tenant, dejando pagos, ARCA y obras sociales para un post-MVP ya diseñado.
