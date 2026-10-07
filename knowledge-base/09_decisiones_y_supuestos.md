# Decisiones y Supuestos

## Decisiones documentadas

### DD-01 — Monolito modular, no microservicios
**Decisión**: un solo backend FastAPI + un frontend, deploy en Compose.
**Contexto**: un consultorio, equipo chico, materia con fecha de entrega.
**Alternativas consideradas**: microservicios por dominio; serverless.
**Justificación**: el costo operativo de microservicios supera cualquier beneficio a esta escala; la modularidad por capas da el orden sin la red.
**Trade-offs aceptados**: si el día de mañana hay 100 consultorios, habrá que extraer workers/servicios; la frontera multi-tenant (DD-02) mitiga lo peor.

### DD-02 — Frontera multi-tenant lógica desde día 1
**Decisión**: `tenant_id` en todo el dominio + middleware de inyección (P0-sys:c).
**Contexto**: hoy un tenant, mañana potencialmente SaaS.
**Alternativas consideradas**: single-tenant puro (migrar después); multi-tenant real ya (schemas por tenant).
**Justificación**: el costo hoy es marginal (una columna + middleware) y evita la migración más dolorosa del producto.
**Trade-offs aceptados**: disciplina permanente (todo query filtrado); tests que lo verifiquen.

### DD-03 — Stack Python + React
**Decisión**: FastAPI + SQLAlchemy + Postgres + Redis/RQ; React + TS + Vite (P4:a, confirmado por el equipo).
**Contexto**: sin restricciones impuestas; criterio = mantenibilidad (P5:b).
**Alternativas consideradas**: NestJS + Prisma; Next.js fullstack.
**Justificación**: tipado y validación punta a punta en ambos lados, ecosistemas maduros, Compose simple.
**Trade-offs aceptados**: dos runtimes que mantener; si el equipo dominara solo JS, Nest valdría la pena (registrado, no bloquea).

### DD-04 — RQ sobre Redis, no Celery
**Decisión**: RQ + rq-scheduler para recordatorios y exports.
**Contexto**: async acotado (jobs programados + background simples).
**Alternativas consideradas**: Celery; APScheduler en proceso.
**Justificación**: RQ es ordenes de magnitud más simple de operar que Celery; APScheduler en proceso muere con el deploy y no escala a worker separado.
**Trade-offs aceptados**: si aparecen prioridades, reintentos con backoff complejo o miles de jobs/min, migrar a Celery (anotar en `11`).

### DD-05 — WhatsApp manual en v1
**Decisión**: el sistema genera el texto; la recepción envía y marca estado.
**Contexto**: API oficial de Meta = costo, verificación y complejidad fuera del MVP.
**Alternativas consideradas**: WA API desde día 1; SMS.
**Justificación**: el valor (recordatorio efectivo) se captura sin la integración; el modelo `Recordatorio` ya prevé `canal` para sumar el automático después.
**Trade-offs aceptados**: depende de la disciplina de recepción; el ausentismo baja menos que con envío automático.

### DD-06 — MVP mínimo (P2:a), integraciones fuera
**Decisión**: v1 = agenda + turnero + WA manual + ficha básica; MP, ARCA, OS, odontograma gráfico y lista de espera automática a post-MVP (`11`).
**Contexto**: ronda 1 revisada: P2:c → P2:a por realismo académico.
**Alternativas consideradas**: MVP completo del Discovery en v1.
**Justificación**: cada integración externa (MP/ARCA) es un proyecto en sí; una v1 que anda sin ellas vale más que una v1 completa que no llega.
**Trade-offs aceptados**: sin cobros ni facturación, el "flujo de dinero" queda manual; hay que diseñarlo para enchufarlo después (ver `11`).

### DD-07 — Sin auditoría formal en v1 (Q-datos:c)
**Decisión**: borrado físico permitido, sin audit trail; solo `enviado_por` en recordatorios y metadata en exports.
**Contexto**: decisión explícita del equipo contra recomendación técnica.
**Alternativas consideradas**: audit append-only; logs + soft delete.
**Justificación**: velocidad de entrega; el equipo asume el riesgo conscientemente.
**Trade-offs aceptados**: riesgo legal (datos de salud) y de debugging; revertir esta decisión es la prioridad #1 del post-MVP — queda como pregunta abierta P0 en `10`.

### DD-08 — Dueño como flag, no como rol
**Decisión**: `es_dueno` sobre rol profesional (P3:a).
**Contexto**: consultorio chico donde dueño ≈ odontólogo.
**Alternativas consideradas**: rol admin separado.
**Justificación**: menos RBAC que mantener; promovible a rol sin migrar datos.
**Trade-offs aceptados**: si aparecen permisos finos de dueño-no-profesional, hay que partir el rol.

### DD-09 — Errores con código de regla
**Decisión**: RN-GL-01 — toda respuesta de error de dominio incluye su `RN-XX-NN`.
**Contexto**: mensajes exactos en UI y tests que asertan comportamiento, no strings.
**Trade-offs aceptados**: acopla API a la numeración de la KB (cambio de código = cambio versionado).

## Supuestos inferidos

### SU-01 — El consultorio piloto existe y colabora
**Supuesto**: hay al menos un consultorio real para seed, validación y métricas de éxito (`01`).
**Origen**: `01` define métricas contra línea base; sin piloto no hay baseline.
**Riesgo si es falso**: métricas imposibles; validación solo sintética.
**Cómo validar**: conseguir el piloto antes del Sprint 2; si no, redefinir métricas a sintéticas.

### SU-02 — La recepción adopta el panel a diario
**Supuesto**: WA manual y transiciones de estado dependen de que la recepción use el sistema siempre.
**Origen**: flujos 2 y 4 de `07`.
**Riesgo si es falso**: agenda desactualizada, recordatorios sin enviar, ausentismo sin bajar.
**Cómo validar**: medir "turnos sin transición a tiempo" en reportes; si supera el 10%, el problema es adopción, no código.

### SU-03 — Ficha básica alcanza para la v1
**Supuesto**: datos + motivo + observaciones bastan; el odontograma gráfico puede esperar (supuesto (i) de ronda 2, no corregido).
**Origen**: alcance `01` + P2:a.
**Riesgo si es falso**: el profesional siente que "le falta lo clínico" y no usa el sistema.
**Cómo validar**: mostrar `01`+`06` al odontólogo piloto antes del Sprint 1; si pide odontograma, re-evaluar US clínicas mínimas.

### SU-04 — Un solo huso horario
**Supuesto**: todo el sistema opera en America/Argentina/Buenos_Aires (RN-GL-03).
**Origen**: segmento Argentina, v1 single-tenant.
**Riesgo si es falso**: turnos corridos una hora en cambios de horario o tenants de otras provincias con distinto uso.
**Cómo validar**: guardar siempre timestamptz; la decisión solo fija el default de visualización.
