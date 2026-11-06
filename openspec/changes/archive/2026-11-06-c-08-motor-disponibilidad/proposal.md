# Proposal

## Why

C-07 ya garantiza que un turno puntual sea válido, pero todavía no existe una forma de enumerar los horarios que un paciente podría reservar. Sin un motor de huecos, el turnero de C-09 no puede ofrecer alternativas y el panel de C-10 no puede mostrar la agenda real: la plantilla semanal, los bloqueos y los turnos activos existen por separado, pero nadie los combina.

## What Changes

- Agregar un motor de cálculo de huecos reservables que combine la plantilla semanal del profesional, los bloqueos personales y de consultorio, y los turnos activos, respetando RN-AG-01 y RN-AG-02.
- Enumerar huecos con inicio estrictamente futuro y granularidad igual a `duracion_min` de la prestación seleccionada; la grilla se ancla al inicio de cada franja disponible y no inventa horarios fuera de plantilla.
- Exponer un endpoint interno `GET /disponibilidad/huecos?profesional_id=&prestacion_id=&desde=&hasta=` con paginación por rango, alcance tenant y RBAC de panel. Se conserva intacto el `GET /disponibilidad` de C-06, que lista la plantilla semanal.
- Devolver exclusivamente huecos: sin nombre, teléfono, documento ni cualquier otro dato de pacientes (RN-AG-04). El envoltorio público por slug y la reserva quedan para C-09.
- No agregar tablas, columnas ni migración Alembic: C-08 es una capa de lectura sobre el esquema existente (head `0006_turno`). Tampoco se agregan dependencias ni código de frontend.

## Capabilities

### New Capabilities

- `core/huecos`: cálculo determinista y de solo lectura de horarios reservables a partir de disponibilidad, bloqueos, turnos activos y duración de prestación, más su endpoint interno tenant-scoped y libre de datos de pacientes.

### Modified Capabilities

<!-- Ninguna. El contrato de plantilla semanal, bloqueos, turnos, prestaciones y profesionales no cambia. -->

## Impact

- Código previsto: `backend/app/domain/huecos/` (cálculo puro, repositorio de lectura, servicio y router), registro del router en `backend/app/main.py` y pruebas nuevas en `backend/tests/`. No se modifica `backend/app/domain/agenda/`, que sigue sin referenciar `Turno` por su guarda de arquitectura.
- API: una ruta interna nueva `GET /disponibilidad/huecos`; ninguna ruta existente cambia de contrato. La ruta no es pública y nunca acepta el `codigo_publico` como autenticación.
- Base de datos: sin migración nueva; se reutilizan `ix_turno_tenant_profesional_inicio`, `ix_bloqueo_tenant_profesional_desde` e `ix_disponibilidad_tenant_profesional_dia`. Si la prueba de performance semanal no cumple con esos índices, se evaluará una revisión `0007` como cambio separado.
- Aguas abajo: C-09 reutiliza el servicio para el turnero por slug y C-10 para el panel; el contrato interno devuelve solo huecos.
- **Gobernanza ALTA**: estos artefactos son solo planificación. No se implementa código en esta fase y `apply` requiere una instrucción explícita posterior.
