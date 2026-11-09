# Pantalla: Agenda semanal multi-profesional

Diseño generado en Stitch y exportado como insumo para la skill `pantalla-a-componente`.

| Campo | Valor |
|---|---|
| Proyecto Stitch | `14272644653178061065` (`turnos-odontologia`) |
| Screen ID | `583dff22e2694257a60010f10a833229` |
| Título | Agenda Semanal Multi-Profesional - OdontoGrid |
| Design system | OdontoGrid Clinical OS (`assets/0813ac9037e544cc80665af1bbfe9f7f`) |
| Device | DESKTOP (2560×2048) |
| Estado | `COMPLETE` |
| Generado | 2026-11-09 |

## Archivos

| Archivo | Uso |
|---|---|
| `583dff22e2694257a60010f10a833229.html` | Referencia visual y estructural. **No copiar al proyecto.** |
| `583dff22e2694257a60010f10a833229.png` | Captura para revisión humana |
| `DESIGN.md` | Tokens y guías del design system (DTCG) |
| `prompt.txt` | Prompt exacto usado para generar la pantalla |

## Notas para la implementación

- Los estados ya coinciden con RN-TU-04: reservado (azul), confirmado (verde), atendido (teal), ausente (ámbar), cancelado (rojo tachado) y sobreturno (violeta con etiqueta).
- Stitch usa textos de estado algo más claros que `assets/estados.css`. Se mantienen los fondos y acentos del diseño, y los textos más oscuros del token set por contraste AA. Si se decide adoptar los hex exactos de `DESIGN.md`, se cambian **solo los valores** de las variables, nunca sus nombres.
- El HTML incluye un shell con sidebar y top bar que excede el alcance de C-10. La implementación toma la grilla, la tarjeta de turno, la leyenda de estados y los filtros por profesional; el shell completo se decide en C-10.
- Datos de la pantalla: ficticios (R9).

## Implementado (C-10)

| Pieza | Dónde |
|---|---|
| Agregador día/semana | `backend/app/domain/agenda/panel/` (`GET /agenda/dia`, `GET /agenda/semana`) |
| Sesión real del panel | `frontend/src/features/auth/` (login, refresh, `/auth/me`, logout) |
| Shell mínimo | `frontend/src/features/shell/AppShell.tsx` (navegación por rol, sin sidebar de Stitch) |
| Agenda día/semana | `frontend/src/features/agenda/AgendaPage.tsx` y `TurnoCard.tsx` |
| Alta interna y sobreturno | `frontend/src/features/agenda/NuevoTurnoModal.tsx` |
| Configuración del dueño | `frontend/src/features/agenda/ConfiguracionAgenda.tsx` |
| Tokens de estado | `frontend/src/features/agenda/estados.css` |

El shell completo del mockup (sidebar, top bar con buscador global y métricas de ocupación) queda fuera del alcance de C-10; la navegación implementada es la mínima para operar agenda, recordatorios y reportes según el rol.

