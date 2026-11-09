# Tokens de estado de turno

Fuente de verdad para colores de la agenda y de cualquier vista que muestre turnos. Los valores se usan a través de variables CSS definidas en `assets/estados.css`; **nunca** escribas el hex directamente en un componente.

## Estados del turno (RN-TU-04)

| Estado | Variable de fondo | Variable de texto | Hex fondo / texto | Cuándo aparece |
|---|---|---|---|---|
| `reservado` | `--turno-reservado-bg` | `--turno-reservado-fg` | `#dbeafe` / `#1e40af` | Turno creado por el turnero o por recepción, aún sin confirmar |
| `confirmado` | `--turno-confirmado-bg` | `--turno-confirmado-fg` | `#dcfce7` / `#166534` | El paciente o recepción confirmó la asistencia |
| `atendido` | `--turno-atendido-bg` | `--turno-atendido-fg` | `#ccfbf1` / `#115e59` | El profesional lo atendió; estado terminal |
| `ausente` | `--turno-ausente-bg` | `--turno-ausente-fg` | `#fef3c7` / `#92400e` | El paciente no asistió; estado terminal |
| `cancelado` | `--turno-cancelado-bg` | `--turno-cancelado-fg` | `#fee2e2` / `#991b1b` | Cancelado por paciente o recepción; terminal y no ocupa el horario |

## Sobreturno (no es un estado)

`es_sobreturno` es un flag independiente del estado. Se muestra con un acento propio y una etiqueta textual "Sobreturno"; no cambia el color de fondo del estado.

| Token | Valor | Uso |
|---|---|---|
| `--turno-sobreturno-borde` | `#7c3aed` | Borde izquierdo de la tarjeta |
| `--turno-sobreturno-fg` | `#5b21b6` | Texto de la etiqueta "Sobreturno" |
| `--turno-sobreturno-bg` | `#ede9fe` | Fondo de la etiqueta |

## Tokens de superficie

| Token | Valor | Uso |
|---|---|---|
| `--agenda-bg` | `#ffffff` | Fondo de la vista |
| `--agenda-superficie` | `#f8fafc` | Fondo de columnas/celdas |
| `--agenda-borde` | `#e2e8f0` | Separadores de día/hora |
| `--agenda-texto` | `#0f172a` | Texto principal |
| `--agenda-texto-suave` | `#475569` | Texto secundario (profesional, prestación) |
| `--agenda-foco` | `#2563eb` | Anillo de foco (accesibilidad) |

## Reglas

1. **Color + texto, nunca color solo.** Cada turno muestra la etiqueta del estado además del color (WCAG 1.4.1). La agenda se imprime y se proyecta.
2. **Contraste**: los pares fondo/texto de la tabla están pensados para AA en texto normal. Si cambiás un hex, verificá el contraste antes de commitear.
3. **Nombres estables**: si el design system de Stitch trae otra paleta, cambiá solo los valores hex en `estados.css`. Los nombres de las variables y las clases `.turno--<estado>` no se tocan, así no hay que reescribir componentes.
4. **Estados terminales** (`atendido`, `ausente`, `cancelado`) no habilitan acciones. El estilo no reemplaza la lógica de RN-TU-04.
5. **Modo oscuro**: no está implementado en v1. Si se agrega, se agregan bloques `@media (prefers-color-scheme: dark)` en `estados.css`, no condicionales en los componentes.
