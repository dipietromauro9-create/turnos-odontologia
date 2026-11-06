# Design — c-09-turnero-publico

## Context

El sistema cuenta con el núcleo de datos, autenticación, agenda, pacientes y la máquina de estados de turnos (C-01 a C-07), junto al motor de cálculo de huecos determinista en < 1 s (C-08). Sin embargo, todos los endpoints hasta ahora requieren credenciales JWT de usuario interno (recepción, profesional o dueño). Se necesita exponer un canal público web accesible para pacientes sin cuenta que permita reservar, consultar disponibilidad, y autogestionar citas mediante un código de gestión alfanumérico seguro.

## UI Mockups

Decision: no (project policy). La política del proyecto para diseño visual está establecida en `off` (registrada en `design-system/README.md` y `.active-orchestrator-state.json`). La interfaz se implementará directamente con componentes React y estilos estándar de la aplicación.

## Goals / Non-Goals

**Goals:**
- Exponer endpoints públicos bajo `/turnero` sin requerir autenticación JWT.
- Resolver el consultorio a través del `slug` en la URL pública (`/turnero/{slug}/...`).
- Garantizar reserva atómica con cálculo de fin en backend (RN-TU-02), búsqueda/alta de paciente (RN-PA-01) y prevención anti-solape (RN-TU-01).
- Permitir consulta, cancelación y reprogramación atómica utilizando el `codigo_publico` (RN-TU-05, RN-TU-06, RN-TU-07).
- Proteger endpoints públicos con rate limiting (10 req/min por IP) y serialización estricta sin PII (RN-AG-04).
- Proveer vistas web en React: navegación de grilla semanal, formulario de reserva con emisión de código, y pantalla de autogestión de turnos.

**Non-Goals:**
- Pasarela de pago o cobro de señas (Mercado Pago queda para etapas posteriores del roadmap).
- Creación de cuentas o contraseñas para pacientes (el paciente solo se identifica por teléfono y código de turno).
- Integración automatizada con WhatsApp API oficial (la notificación manual de WhatsApp pertenece a C-11).

## Decisions

### 1. Resolución de Tenant en rutas públicas por Slug
En lugar de depender de la sesión autenticada (`get_current_user`), las rutas públicas de turnero resolverán el `Tenant` activo consultando `Tenant.slug` y verificando que `activo == True`. Las operaciones de base de datos se ejecutan con `tenant_session(tenant.id)` garantizando el aislamiento multi-tenant estricto (R3).

*Alternativas consideradas*:
- Subdominios por tenant: agrega complejidad de DNS y despliegue local innecesaria en esta etapa.
- Header `X-Tenant-ID`: filtra detalles internos de base de datos al navegador del paciente y no es amigable para enlaces compartibles por WhatsApp o redes.

### 2. Transaccionalidad de Reserva y Reprogramación con defensa anti-solape
Para evitar reservas duplicadas bajo concurrencia, `POST /turnero/{slug}/reservas` y `POST /turnero/mis-turnos/reprogramar` validan primero la ausencia de bloqueos e intersecciones con el motor de disponibilidad y confían en la restricción `EXCLUDE USING gist` de PostgreSQL ante condiciones de carrera. Ante conflicto, el backend captura la excepción y retorna `HTTP 409` con código de error de negocio `RN-TU-01`. En la reprogramación, la transacción se ejecuta con `SELECT ... FOR UPDATE` sobre la fila del turno original; si el destino no es válido, la transacción hace rollback dejando el turno intacto (RN-TU-07).

### 3. Rate Limiting por IP para endpoints públicos
Se implementa un middleware / dependency de limitación de tasa (10 solicitudes por minuto por dirección IP) respaldado en Redis (con fallback en memoria para entornos de pruebas) aplicado exclusivamente al router público `/turnero`. Al superar el límite, responde `HTTP 429 Too Many Requests`.

### 4. Arquitectura Frontend del Turnero
Se crean dos páginas principales en `frontend/src/pages/turnero/`:
- `TurneroPublicoPage.tsx` (`/turnero/:slug`): consulta catálogo y huecos libres del consultorio, navegación semanal (`SemanaSelector`), grilla de horarios (`HuecosGrid`) y modal de confirmación con nombre/teléfono (`ReservaModal`). Al confirmar, muestra la tarjeta de código de turno (`CodigoTurnoCard`) con botón de copiar al portapapeles.
- `MisTurnosPage.tsx` (`/turnero/mis-turnos`): formulario de búsqueda por código alfanumérico, estado de la cita, modal de cancelación con motivo opcional y selector de nuevo horario para reprogramación.

Todas las llamadas de API se tipan con TypeScript estricto sin `any` (R2) y se conectan a través de `frontend/src/shared/api/publicClient.ts`.

## Risks / Trade-offs

- **[Concurrencia en la reserva simultánea del mismo hueco]** → Mitigación: Doble validación en servicio + constraint `EXCLUDE` a nivel de base de datos con manejo de error 409 `RN-TU-01`.
- **[Ataques de spam o scraping de disponibilidad]** → Mitigación: Rate limiting por IP (10 req/min) y respuestas que contienen exclusivamente timestamps e identificadores de catálogo, sin nombres de otros pacientes.
- **[Uso de teléfono homónimo de otro paciente]** → Mitigación: Reutilización de paciente con flag de advertencia interna (`duplicado_advertencia: true`) según RN-PA-01 para revisión posterior de recepción.

## Migration Plan

No se requieren migraciones de base de datos. El cambio reutiliza el esquema consolidado hasta la revisión `0006_turno`.
