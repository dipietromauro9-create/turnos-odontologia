# Visión y Objetivos

## Propósito del sistema

**turnos-odontologia** es un sistema web de gestión de turnos para consultorios odontológicos chicos (1–3 profesionales) en Argentina, que elimina la coordinación manual por WhatsApp/papel uniendo agenda multi-profesional, turnero online 24/7 y ficha básica del paciente en un solo flujo.

El Discovery (18 competidores relevados, ver `discovery/market-research.md`) probó que el hueco real está en el núcleo AR-first completo (turnos + Mercado Pago + ARCA + obras sociales); la v1 ataca la base —agenda y captación sin fricción— y deja las integraciones de pago/fiscales para etapas posteriores documentadas.

## Objetivos por actor

| Actor | Objetivo principal | Objetivos secundarios |
|---|---|---|
| Paciente | Reservar/cancelar/reprogramar sin llamar ni escribir | Recibir recordatorio y llegar con la info clara del turno |
| Profesional (odontólogo/dueño) | Ver su agenda del día y la ficha del paciente antes de atender | Medir ocupación y ausencias; configurar prestaciones y horarios |
| Recepción | Cargar y confirmar turnos sin solapamientos ni huecos perdidos | Enviar recordatorios; registrar cancelaciones y ausentes |

## Alcance v1.0

- Agenda multi-profesional con vistas día/semana, duración variable por prestación, bloqueos, sobreturnos explícitos y prevención de solapamientos.
- Turnero online 24/7 con link público; reserva, cancelación y reprogramación por el paciente.
- Confirmación de turnos con máquina de estados explícita (reservado → confirmado → atendido / cancelado / ausente).
- Recordatorios por WhatsApp en modalidad manual/semiautomática: el sistema genera el mensaje, la recepción lo envía y actualiza el estado.
- Ficha básica del paciente (datos + motivo de consulta + observaciones).
- 3 roles: paciente, profesional (incluye permisos de dueño: reportes y configuración), recepción.
- Reportes básicos: ocupación, ausencias, turnos por profesional.
- Frontera multi-tenant preparada: `tenant_id` en el modelo desde día 1, sin infra multi-tenant real.
- Exportación CSV de turnos y pacientes desde el día uno.

## Fuera de alcance

Explícitamente NO en v1.0 (ver `knowledge-base/11_post_mvp_e_integraciones.md`):

- Cobros y señas con Mercado Pago; caja y reportes de ingresos.
- Factura electrónica ARCA.
- Obras sociales / prepagas y liquidaciones.
- Odontograma gráfico (FDI), periodontograma, imágenes/RX, laboratorio.
- Lista de espera con reasignación automática de huecos.
- WhatsApp API oficial / bot automático.
- Multi-sede, auditoría formal (decisión Q-datos:c — ver riesgo en `10_preguntas_abiertas.md`), API pública, app móvil, portal del paciente, firma digital.

## Métricas de éxito

- Ausentismo mensual del consultorio piloto: reducción ≥ 30% vs. línea base (efecto recordatorios + confirmación).
- Huecos por solapamiento o doble reserva: 0 (regla anti-solape verificada).
- Tiempo de recepción por turno gestionado: −50% vs. coordinación por WhatsApp manual.
- Adopción del turnero: ≥ 60% de las reservas entran por el link online al tercer mes.
- Disponibilidad del turnero público: ≥ 99% mensual.
