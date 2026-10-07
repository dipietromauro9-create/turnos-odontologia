# Actores y Roles

## Actores del sistema

| Actor | Descripción | Cómo interactúa |
|---|---|---|
| Paciente | Persona que reserva atención; no requiere cuenta (reserva con nombre + teléfono/documento) | Turnero público (`/turnero/:slug`): ve disponibilidad, reserva, cancela y reprograma con su código de turno |
| Profesional | Odontólogo que atiende y gestiona su agenda | Panel (`/app`): agenda propia, fichas de sus pacientes, confirmación de estados |
| Profesional dueño | Profesional con permisos extra de gestión | Panel: todo lo del profesional + reportes, prestaciones, horarios, usuarios, exportación |
| Recepción | Personal que agenda, confirma y envía recordatorios | Panel: agenda de todos los profesionales, cola de recordatorios, pacientes |

**Suposición**: en v1 el dueño es un flag (`es_dueno`) sobre el rol profesional, no un rol separado (P3:a). Si escala a clínicas, se promueve a rol propio sin migrar datos.

## RBAC — Matriz de permisos

Recursos × roles (C=crear, R=leer, U=actualizar, D=eliminar; `—` = sin acceso):

| Recurso | Paciente (link/código) | Recepción | Profesional | Profesional dueño |
|---|---|---|---|---|
| Disponibilidad | R (solo lectura pública) | R | R | R |
| Turnos propios (reservar/cancelar/reprogramar) | CUD con código | CRUD todos | CRUD todos | CRUD todos |
| Transiciones de estado (confirmar, ausencia) | — | U | U (propios) | U |
| Pacientes (ficha básica) | R propia con código | CRUD | CRUD (sus pacientes) | CRUD |
| Agenda de profesionales | — | R (todos) | R (propia) | R (todos) |
| Profesionales / usuarios | — | — | — | CRUD |
| Prestaciones / horarios | — | R | R | CRUD |
| Recordatorios (cola manual) | — | R,U (marcar enviado) | R | R |
| Reportes | — | — | R propios | R todos |
| Export CSV | — | — | — | R |

Reglas transversales:
- El paciente solo opera sobre sus turnos mediante código único por turno (sin login).
- Un profesional nunca ve fichas de pacientes de otro profesional salvo que sea dueño.
- La recepción no configura prestaciones, horarios ni usuarios.

## Rutas públicas

Sin autenticación:

- `GET /turnero/:slug` — disponibilidad del consultorio (solo huecos, sin datos personales).
- `POST /turnero/:slug/reservas` — crear reserva (nombre + teléfono + prestación + horario).
- `GET /turnero/mis-turnos?codigo=` — ver turno propio con código.
- `POST /turnero/mis-turnos/cancelar · /reprogramar` — con código.
- `GET /health` — estado del sistema (para Docker/orquestador).
