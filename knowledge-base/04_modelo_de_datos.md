# Modelo de Datos

## Dominios

- **Núcleo multi-tenant**: tenant único en v1, `tenant_id` en todo el dominio para la frontera preparada (P0-sys:c).
- **Agenda**: profesionales, prestaciones, disponibilidad, bloqueos, turnos con máquina de estados.
- **Pacientes**: ficha básica + vínculo con turnos.
- **Comunicación**: cola manual de recordatorios (WA manual en v1).
- **Acceso**: usuarios con rol + flag de dueño.

## ERD (Entity Relationship Diagram)

```
Tenant 1───* Usuario 1───1 Profesional 1───* Turno *───1 Paciente
   │            │              │                 │
   │            │              │                 └───1 Prestación
   │            │              │
   │            │              └───* Disponibilidad (semanal)
   │            │              └───* Bloqueo (puntual)
   │            │
   │            └── rol: recepcion | profesional (+ es_dueno)
   │
   ├───* Prestación ───* Turno
   ├───* Paciente ───* Turno
   └───* Recordatorio ───1 Turno
```

## Entidades

### Tenant
- Atributos: `id (uuid, pk)`, `slug (varchar, unique)`, `nombre (varchar)`, `creado_en (timestamptz)`
- Relaciones: 1─* con Usuario, Profesional, Prestación, Paciente, Turno, Recordatorio
- Constraints: `slug` inmutable tras creación
- Índices: `slug` unique

### Usuario
- Atributos: `id (uuid, pk)`, `tenant_id (fk)`, `nombre`, `email (citext)`, `password_hash`, `rol (enum: recepcion, profesional)`, `es_dueno (bool, default false)`, `activo (bool)`, timestamps
- Relaciones: `tenant_id` *─1 Tenant; 1─1 Profesional (solo si `rol=profesional`)
- Constraints: `email` único por tenant; `es_dueno=true` solo si `rol=profesional`
- Índices: `(tenant_id, email)` unique, `(tenant_id, rol)`

### Profesional
- Atributos: `id (uuid, pk)`, `tenant_id (fk)`, `usuario_id (fk, nullable)`, `nombre`, `matricula (nullable)`, `especialidad (nullable)`, `activo (bool)`, timestamps
- Relaciones: *─1 Tenant; 1─1 Usuario; 1─* Turno, Disponibilidad, Bloqueo
- Constraints: `usuario_id` único (un login = un profesional)
- Índices: `(tenant_id, activo)`

### Prestacion
- Atributos: `id (uuid, pk)`, `tenant_id (fk)`, `nombre`, `duracion_min (int)`, `precio_ref (numeric, nullable, informativo v1)`, `activa (bool)`, timestamps
- Relaciones: *─1 Tenant; 1─* Turno
- Constraints: `duracion_min` múltiplo de 5, > 0
- Índices: `(tenant_id, activa)`

### Disponibilidad (plantilla semanal)
- Atributos: `id (uuid, pk)`, `tenant_id (fk)`, `profesional_id (fk)`, `dia_semana (0–6)`, `hora_desde`, `hora_hasta`
- Relaciones: *─1 Profesional
- Constraints: `hora_hasta > hora_desde`; sin filas duplicadas por (profesional, día, rango)
- Índices: `(tenant_id, profesional_id, dia_semana)`

### Bloqueo (cierre puntual: vacaciones, feriados, trámites)
- Atributos: `id (uuid, pk)`, `tenant_id (fk)`, `profesional_id (fk, nullable = todo el consultorio)`, `desde (timestamptz)`, `hasta (timestamptz)`, `motivo`
- Relaciones: *─1 Profesional (nullable)
- Constraints: `hasta > desde`
- Índices: `(tenant_id, profesional_id, desde)`

### Paciente
- Atributos: `id (uuid, pk)`, `tenant_id (fk)`, `nombre`, `telefono (varchar)`, `documento (nullable)`, `fecha_nac (nullable)`, `observaciones (text, ficha básica)`, timestamps
- Relaciones: *─1 Tenant; 1─* Turno
- Constraints: duplicados por (nombre, teléfono) advertidos, no bloqueados (recepción decide)
- Índices: `(tenant_id, telefono)`, `(tenant_id, nombre)` trigram para búsqueda
- Nota: Q-datos:c — borrado físico permitido en v1; documentar como deuda en `10`

### Turno
- Atributos: `id (uuid, pk)`, `tenant_id (fk)`, `profesional_id (fk)`, `paciente_id (fk)`, `prestacion_id (fk)`, `inicio (timestamptz)`, `fin (timestamptz)`, `estado (enum: reservado, confirmado, atendido, cancelado, ausente)`, `codigo_publico (varchar(12), unique, para operar sin login)`, `es_sobreturno (bool)`, `motivo_cancelacion (nullable)`, timestamps
- Relaciones: *─1 Profesional, Paciente, Prestación, Tenant; 1─* Recordatorio
- Constraints:
  - `fin = inicio + duracion(prestacion)` (se valida en servicio, RN-TU-02)
  - **Anti-solape**: `EXCLUDE USING gist (profesional_id WITH =, tsrange(inicio, fin) WITH &&) WHERE (estado NOT IN ('cancelado'))` — la DB es la última línea de defensa (RN-TU-01)
  - Transiciones de estado solo las permitidas por la máquina (RN-TU-04, se valida en servicio)
- Índices: `(tenant_id, profesional_id, inicio)`, `codigo_publico` unique, `(tenant_id, estado, inicio)` para agenda del día

### Recordatorio
- Atributos: `id (uuid, pk)`, `tenant_id (fk)`, `turno_id (fk)`, `canal (enum: whatsapp_manual)`, `texto (generado por plantilla)`, `estado (enum: pendiente, enviado, fallido)`, `enviado_por (fk Usuario, nullable)`, timestamps
- Relaciones: *─1 Turno
- Constraints: un recordatorio `pendiente` por turno y tipo (evita spam)
- Índices: `(tenant_id, estado)` para la cola manual de recepción

## Seed data inicial

- 1 Tenant demo (`slug: demo`, nombre "Consultorio Demo").
- 1 Usuario profesional dueño (`dueno@demo`, rol profesional, `es_dueno=true`) + Profesional vinculado.
- 1 Usuario recepción (`recepcion@demo`).
- Prestaciones base: Consulta (30 min), Limpieza (60 min), Extracción (45 min), Control (20 min), Urgencia (30 min, habilita sobreturno).
- Disponibilidad Lun–Vie 9–13 y 16–20 para el profesional demo.
- 2 pacientes + 3 turnos de ejemplo (uno por estado: reservado, confirmado, atendido).
