# Proposal

## Why

Los consultorios odontológicos pierden turnos por cancelaciones tardías, sufren ausentismo y saturan la atención presencial o telefónica. Los pacientes necesitan una vía directa, ágil y disponible 24/7 para consultar horarios libres y agendar citas desde su navegador sin tener que registrarse con usuario/contraseña, así como consultar o gestionar su turno (cancelar o reprogramar) de forma autónoma usando un código de gestión único.

## What Changes

- **Backend: Router público de turnero (`/turnero`)**:
  - `GET /turnero/{slug}/disponibilidad`: consulta de huecos reservables del tenant resuelto por slug, consumiendo el motor de `core/huecos`, sin exponer PII (RN-AG-04).
  - `GET /turnero/{slug}/catalogo`: lista pública de profesionales y prestaciones activas para filtros del turnero.
  - `POST /turnero/{slug}/reservas`: reserva anónima por `nombre` + `telefono`; busca/crea paciente con alerta de homónimo (RN-PA-01), calcula `fin` en backend (RN-TU-02), valida anti-solape (RN-TU-01) y emite `codigo_publico` alfanumérico seguro en estado `reservado`.
  - `GET /turnero/mis-turnos?codigo=`: consulta de estado y detalles del turno propio sin exponer PII de terceros (RN-TU-06; 404 genérico ante código inexistente).
  - `POST /turnero/mis-turnos/cancelar`: cancelación autónoma del paciente con código y motivo opcional, liberando el hueco (RN-TU-05).
  - `POST /turnero/mis-turnos/reprogramar`: reprogramación atómica del turno a un nuevo hueco válido; si el destino no está disponible, el original queda intacto (RN-TU-07).
  - Rate limiting defensivo (10 req/min por IP) en rutas públicas no autenticadas.
- **Frontend: Experiencia de Turnero Público y Mis Turnos**:
  - Rutas públicas en React Router: `/turnero/:slug` (grilla semanal y reserva) y `/turnero/mis-turnos` (gestión por código).
  - Componentes de selección semanal de fechas, filtrado por profesional/prestación, selección de hueco y formulario de reserva con copia rápida del código generado.
  - Vistas de consulta, cancelación y reprogramación de turnos.
- **Sin cambios en el esquema de base de datos**: No se requieren migraciones nuevas (se utilizan las tablas y constraints de migraciones `0001` a `0006`).

## Capabilities

### New Capabilities
- `publico/turnero`: Experiencia pública completa de reserva 24/7 sin cuenta, consulta de disponibilidad por slug de consultorio, reserva atómica con código de gestión, y autogestión de turnos (cancelación y reprogramación).

### Modified Capabilities
<!-- Ninguna especificación existente cambia sus requerimientos de contrato; este change consume core/huecos, core/turnos, core/pacientes y core/tenancy -->

## Impact

- **APIs**: Nuevo router público `/turnero` en FastAPI, sin requerir cabecera JWT pero protegido por rate limiting y validación estricta de tenant/slug.
- **Frontend**: Nuevas páginas y componentes en `frontend/src/pages/turnero/` y `frontend/src/features/turnero/` bajo `PublicRoute`.
- **Dependencias**: Sin nuevas dependencias de backend ni frontend.
