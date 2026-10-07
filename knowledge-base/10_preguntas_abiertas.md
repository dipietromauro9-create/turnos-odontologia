# Preguntas Abiertas

## Inconsistencias detectadas

### IN-01 — Sin auditoría con datos de salud (Q-datos:c vs. leyes 25.326/26.529)
**Documento `09` dice**: borrado físico permitido, sin audit trail en v1 (decisión explícita del equipo).
**Documento `discovery/discovery.md` dice**: restricción de adecuación a normativa argentina de datos de salud.
**Impacto**: riesgo legal y de trazabilidad; un reclamo o una pérdida de datos no tiene cómo auditarse.
**Resolución propuesta**: mantener en v1 solo con consentimiento informado del piloto + plan fechado de reversión (soft delete primero, audit después). Prioridad Alta en la tabla.

### IN-02 — Frontera multi-tenant para un solo tenant (P0-sys:c vs. P0-scale:a)
**Documento `02`/`08` dice**: `tenant_id` + middleware desde día 1.
**Decisión P0-scale dice**: un consultorio, < 50 personas.
**Impacto**: leve sobrecosto de disciplina y tests; ningún costo operativo.
**Resolución propuesta**: ninguna acción — la tensión es intencional y barata (DD-02). Se deja registrada para que nadie la "simplifique" quitando el `tenant_id`.

### IN-03 — Meta de ausentismo con WA manual (métrica `01` vs. DD-05)
**Documento `01` dice**: ausentismo −30% como métrica de éxito.
**Documento `09` dice**: envío manual dependiente de recepción (DD-05, SU-02).
**Impacto**: si la recepción no envía, la métrica no se mueve y parece falla del sistema.
**Resolución propuesta**: medir "recordatorios enviados / turnos confirmados" como métrica intermedia; si < 90%, el problema es adopción (SU-02), no producto.

## Preguntas abiertas (priorizadas)

| Prioridad | Pregunta | Bloquea | Decisor |
|---|---|---|---|
| Alta | ¿Plan fechado para revertir IN-01 (soft delete + audit trail)? | Post-MVP (diseño de `11`) | Equipo + tutor |
| Alta | ¿Consultorio piloto confirmado para baseline de métricas (SU-01)? | Sprint 2 | Product Owner |
| Alta | ¿Odontograma básico entra en v1 o la ficha textual alcanza (SU-03)? | Sprint 1 | Odontólogo piloto |
| Media | ¿WhatsApp arranca manual o con API oficial desde v1 (supuesto ii ronda 2)? | Sprint 2 (modelo `Recordatorio` ya lo prevé) | Equipo |
| Media | ¿Seña obligatoria u opcional por defecto (post-MVP, diseño en `11`)? | Post-MVP | Product Owner |
| Media | ¿Qué obras sociales priorizar cuando toque el post-MVP? | Post-MVP | Product Owner |
| Baja | ¿Precio y modalidad de cobro del producto (suscripción/por profesional)? | Lanzamiento | Product Owner |
| Baja | ¿Migración RQ → Celery bajo qué umbral (jobs/min)? | Post-MVP | Tech Lead |
