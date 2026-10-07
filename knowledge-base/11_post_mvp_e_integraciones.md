# Post-MVP e Integraciones Futuras

Alcance explícitamente fuera de v1.0 (ver `01`). Cada ítem trae su pre-cableado en v1 para que el encaje posterior sea barato, y dependencias entre sí.

## Orden sugerido (por valor / costo)

1. **Lista de espera con reasignación automática** — sin dependencias externas; usa la máquina de estados existente. Pre-cableado v1: `motivo_cancelacion` + estados terminales.
2. **Señas y caja con Mercado Pago** — SDK + webhooks como eventos a la máquina de turnos (nuevo evento `seña_acreditada`; transiciones `reservado → señado → confirmado`). Pre-cableado v1: `precio_ref` en Prestación, `es_sobreturno` como antecedente de flags de pago, tabla `Pagos` pendiente de diseño. Abre la pregunta "seña obligatoria u opcional" (`10`).
3. **WhatsApp API oficial** — el modelo `Recordatorio` ya tiene `canal`; sumar `whatsapp_api` + worker de envío + webhook de lectura/confirmación. Pre-cableado v1: plantillas de texto y `enviado_por` (convive manual + auto por turno).
4. **Odontograma gráfico FDI (+ periodontograma después)** — nueva entidad `Odontograma` (paciente × pieza × estado × fecha, versionado) + visor en frontend. Pre-cableado v1: ficha básica con `observaciones` migra como notas iniciales. Depende de SU-03 (`10`).
5. **Obras sociales + liquidaciones** — entidades `Cobertura`, `Plan`, `Liquidacion`; la prestación suma `codigo_os`. Pre-cableado v1: `precio_ref` como precio particular de referencia.
6. **Factura ARCA** — la más costosa (certificados, WS, contingencias); entra última, montada sobre cobros (2) y OS (5). Pre-cableado v1: ninguno técnico, solo no cerrar el modelo de `Pagos`.
7. **Reversión de DD-07 (soft delete + audit trail)** — transversal, prioritaria por IN-01 (`10`): `borrado_en` en dominio + tabla `Auditoria` append-only en caja/turnos primero.
8. Después: multi-sede real, API pública, app móvil, portal del paciente, firma digital, Google Calendar, campañas (ver `discovery/market-research.md` §D).

## Notas de diseño anticipado

- **Pagos**: diseñar `Pagos(turno_id, medio, monto, estado, id_externo)` idempotente por `id_externo` del webhook (lección de Fresha/SimplyBook: el dinero nunca se reconcilia dos veces).
- **WA API**: el webhook de Meta confirma lectura; mapear `leido → confirmado` solo si el consultorio lo configura (algunos quieren confirmación explícita del paciente).
- **ARCA**: evaluar facturador intermedio vs. integración directa en `10` antes de estimar; la decisión cambia el costo en un orden de magnitud.
- **Migración RQ → Celery** (`09` DD-04): umbral sugerido > 1.000 jobs/día o necesidad de prioridades; registrar la métrica en reportes.
