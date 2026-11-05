# Proposal

## Why

Los catálogos, las fichas de pacientes y la disponibilidad ya existen, pero todavía no hay un servicio que reserve un turno, impida solapamientos concurrentes y mantenga sus estados de forma transaccional. C-07 conecta C-04, C-05 y C-06 y deja el contrato que consumirán el motor de huecos, el turnero y el panel.

## What Changes

- Agregar `Turno`, su migración `0006` sobre `0005_disponibilidad_bloqueo`, duración congelada y código público aleatorio de 12 caracteres; PostgreSQL será la última defensa anti-solape mediante `EXCLUDE` sobre un rango con zona horaria.
- Implementar un único servicio de creación, confirmación, atención, ausencia, cancelación y reprogramación, con alcance de tenant y de profesional. La creación normal valida un horario futuro dentro de la plantilla y fuera de bloqueos; un sobreturno de urgencia puede quedar fuera de plantilla, pero no de bloqueos ni sobre otro turno.
- Exponer rutas internas autenticadas `GET/POST /turnos`, `GET/PATCH /turnos/{id}` y acciones `confirmar`, `atender`, `cancelar`, `registrar-ausencia`, `reprogramar`. `PATCH` solo transiciona estado; no habrá borrado físico de turnos.
- Aplicar las tres decisiones del usuario: reprogramar conserva **id, código, estado y duración**; paciente/profesional/prestación de un turno son inmutables; un profesional accede a una ficha si la creó, ya atendió a ese paciente o tiene otro turno reservado/confirmado con él. Cancelado/ausente por sí solos no habilitan la ficha.
- Ampliar el seed con tres turnos ficticios e idempotentes y completar las pruebas de congelación de duración, concurrencia, estados, rollback y frontera pública.
- Reconciliar durante la implementación las referencias contradictorias de la KB y del roadmap con las decisiones aprobadas: reprogramar no cancela y crea otra fila, editar no cambia referencias y cancelar conserva el registro.

## Capabilities

### New Capabilities

- `core/turnos`: persistencia de turnos, anti-solape, duración, sobreturnos, máquina de estados, reprogramación atómica, API interna y seed.

### Modified Capabilities

- `core/pacientes`: reemplazar la pertenencia provisional por creador de C-05 por la pertenencia asistencial aprobada, de forma coherente en lectura, edición, búsqueda, duplicados y reutilización.

## Impact

- Código previsto: `backend/app/db/models/turno.py`, `backend/alembic/versions/0006_turno.py`, `backend/app/domain/turnos/`, alcance del dominio de pacientes, registro de routers y seed. `app/domain/agenda` permanece sin importar ni escribir `Turno`, como exige su guarda existente.
- No se cambian el core de autenticación, la política multi-tenant, las dependencias de Python ni el frontend. C-08 conserva la enumeración de huecos; C-09 las rutas públicas por código; C-10 el panel. El código se genera aquí, pero no autentica rutas públicas todavía.
- Las once especificaciones principales existentes y los 409 tests verdes de C-06 son la referencia de regresión, no evidencia de pruebas ejecutadas en esta propuesta. La implementación tendrá TDD estricto y PostgreSQL real.
- **Gobernanza CRÍTICA**: estos artefactos son una propuesta revisable. Se requiere una nueva instrucción explícita de aprobación para iniciar `apply`; esta fase no modifica código de producción, tests, la KB principal ni la demo local.
