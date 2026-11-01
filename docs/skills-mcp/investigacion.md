# Ficha de investigación — Skill propia + MCP (Parte 1)

**Proyecto:** turnos-odontologia · **Fecha:** 2026-11-01
**Integrantes:** Mauro Di Pietro y Franco Sampieri

---

## 1. Necesidad detectada

Verificado en el repo: `frontend/src/features/` está **vacío** (solo existen `pages/HomePage.tsx` y `pages/LoginPage.tsx`), `frontend/package.json` **no incluye** Tailwind ni librería de componentes, y `CHANGES.md` no define colores por estado ni vista por defecto.

Consecuencia: el primer change de interfaz arranca **sin decisiones visuales ni sistema de estilos**, y esas decisiones se tomarían sobre la marcha dentro de un change que ya carga complejidad funcional (RBAC de vistas, transiciones, mensajes por código `RN-XX-NN`).

**Necesidad:** fijar las decisiones visuales de la agenda **antes de implementar**, sin depender de funcionalidad inexistente (C-02 va 3/21 tareas) y dejando los artefactos versionados.

---

## 2. Change elegido

**C-10 `agenda-panel`** — FASE 4, pendiente, governance MEDIO, dependencias C-07 y C-08.

Es el change pendiente con alcance predominantemente de interfaz que puede **prepararse** sin código previo. `CHANGES.md` ya autoriza el patrón para C-06 ("crear contra el contrato de `04_modelo_de_datos.md`"); acá el contrato son los estados de `Turno` (RN-TU-04), la matriz RBAC (`03_actores_y_roles.md`) y los códigos de error (RN-GL-01).

**Alcance de esta preparación:** proposal + design + specs + tasks + artefactos de diseño. La implementación sigue gateada en **GATE 6**.

---

## 3. Skill creadora y diseño de la skill propia

**Skill creadora: `skill-creator`** (Anthropic, Apache 2.0), copia local en `.opencode/skills/skill-creator/`. Aporta el ciclo definir → borrador → prompts de prueba → evaluar (cualitativo + benchmark) → reescribir → optimizar la descripción para el *triggering*, con utilidades como `quick_validate.py`, `run_eval.py` e `improve_description.py`.

**Skill propia: `pantalla-a-componente`** (a crear en `.opencode/skills/pantalla-a-componente/`).

| Aspecto | Diseño |
|---|---|
| Entrada | `projectId` + `screenId` de Stitch, o los artefactos ya exportados en `docs/design/` |
| Salida | componentes en `frontend/src/features/agenda/`, tokens de color por estado, 4 estados de UI, casos Vitest |
| Reglas duras | R2 (sin `any`, PascalCase), R9 (sin datos de pacientes en prompts ni fixtures) |
| Restricción | el proyecto no tiene Tailwind → el HTML de Stitch es **insumo de diseño, no código final** |
| Anti-alucinación | debe citar el `screenId` usado y no inventar pantallas inexistentes |
| Estructura | `SKILL.md` + `references/tokens-estado.md` + `assets/plantilla-componente.tsx` |
| Evaluación | 3 prompts: pantalla con datos, vacía y con los 5 estados. Métricas: `tsc --noEmit` OK, cero `any`, cubre los 4 estados |

**Repetibilidad:** se re-ejecuta al cambiar el diseño de la agenda o al sumar otras features con UI (C-09 turnero, C-11 recordatorios).

---

## 4. Comparación de los dos MCP y elección justificada

| Criterio | **Stitch (Google)** | **Postgres** |
|---|---|---|
| Tipo | servidor **remoto** (`https://stitch.googleapis.com/mcp`) | ejecutable **local** (stdio) |
| Qué resuelve | genera/edita pantallas; devuelve HTML + captura | inspecciona esquema y ejecuta consultas |
| Estado | beta | ⚠️ el de referencia oficial (`@modelcontextprotocol/server-postgres`) está **archivado** desde 2025-05-29, sin soporte |
| Alternativa mantenida | — | `@microsoft/postgres-mcp`; `postgres-mcp` (crystaldba) |
| Aporte a C-10 | **directo:** decisiones visuales y componentes | **indirecto:** solo el agregador opcional `GET /agenda/dia\|/semana` |
| Aporte a otros changes | C-09, C-11 | C-07 (verificar `EXCLUDE`), C-08 (performance de huecos) |
| Requisitos | cuenta Google + API key | base levantada + credenciales + rol read-only |
| Riesgo | beta: la API puede cambiar | escritura accidental si el rol no es read-only |

**Elección: Stitch.** C-10 casi no tiene superficie de base de datos: el 90 % de su trabajo es decidir y construir pantallas. Postgres aportaría valor real en **C-07** (comprobar que el `EXCLUDE USING gist` existe y qué estados filtra) y en **C-08** (una semana de huecos en < 1 s), no acá. Se descarta `davideast/stitch-mcp` por ser un CLI de un tercero, experimental y no oficial. Postgres queda como candidato para la Fase 3.

---

## 5. Pasos de instalación y configuración

1. API key: `stitch.withgoogle.com/settings` → **API Keys** → *Create API Key*.
2. `opencode.json` en la raíz (ya creado):

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "stitch": {
      "type": "remote",
      "url": "https://stitch.googleapis.com/mcp",
      "enabled": true,
      "timeout": 180000,
      "headers": { "X-Goog-Api-Key": "{env:STITCH_API_KEY}" }
    }
  }
}
```

3. `export STITCH_API_KEY="..."` (o persistir en `~/.bashrc`).
4. Reiniciar OpenCode; verificar con `opencode mcp list` y una llamada a `list_projects`.

**Verificaciones ejecutadas el 2026-11-01:**

| Prueba | Resultado |
|---|---|
| `tools/list` sin credencial | HTTP 200, **16 herramientas** |
| `tools/call list_projects` sin credencial | **HTTP 401** |
| `opencode mcp list` sin key | "connected": **no valida la credencial** |
| `{file:...}` a archivo inexistente | **OpenCode no arranca** (config inválida) |
| `{env:...}` sin definir | arranca; las llamadas devuelven 401 |

**Decisión derivada:** `{env:}` y no `{file:}`, para que un compañero pueda clonar y arrancar sin la key (degrada a 401 en lugar de romper el inicio). La key es **personal**: cada integrante genera la suya.

---

## 6. Archivos de la fundación a actualizar

| Archivo | Cambio previsto |
|---|---|
| `opencode.json` | **nuevo** — MCP Stitch remoto (ya creado y verificado) |
| `.opencode/skills/pantalla-a-componente/` | **nueva** — skill propia |
| `AGENTS.md` + `CLAUDE.md` | fila en la tabla de skills + setup del MCP (mantener ambos sincronizados) |
| `CHANGES.md` | C-10: artefactos de diseño y decisión de estilos |
| `knowledge-base/09_decisiones_y_supuestos.md` | nueva DD: solución de estilos (CSS puro vs Tailwind) |
| `docs/design/` | **nuevo** — HTML, PNG y `DESIGN.md` exportados de Stitch |
| `.env.example` | documenta `STITCH_API_KEY` (aclarando que OpenCode no lo lee) |

---

## 7. Fuentes consultadas (2026-11-01)

- OpenCode — MCP servers: https://opencode.ai/docs/mcp-servers/
- OpenCode — Config, variables `{env:}` / `{file:}`: https://opencode.ai/docs/config/
- Stitch — MCP setup: https://stitch.withgoogle.com/docs/mcp/setup
- Stitch — MCP guide: https://stitch.withgoogle.com/docs/mcp/guide/
- Google Labs — Stitch Agent Skills: https://github.com/google-labs-code/stitch-skills
- Anthropic — `skill-creator`: https://github.com/anthropics/skills/tree/main/skills/skill-creator
- Microsoft — `postgres-mcp`: https://github.com/microsoft/postgres-mcp
- crystaldba — Postgres MCP Pro: https://github.com/crystaldba/postgres-mcp
- MCP — PostgreSQL server archivado: https://github.com/modelcontextprotocol/servers/issues/1688
- `davideast/stitch-mcp` (descartado): https://github.com/davideast/stitch-mcp

---

## Pendientes / no verificado

1. **La página oficial de Stitch no pudo leerse por `fetch`** (renderiza con JavaScript). Se contrastó con un espejo no oficial y con `google-labs-code/stitch-skills`; falta confirmarla en navegador.
2. **La doc oficial no lista OpenCode** (documenta Cursor, Antigravity, VS Code, Claude Code y Gemini CLI); la config se armó combinando el esquema de OpenCode con el snippet de `google-labs-code/stitch-skills`.
3. **Sin API key disponible:** no se ejecutó aún una llamada autenticada de punta a punta.
4. **Reporte de foro** según el cual `generate_screen_from_text` exige OAuth y falla con API key; no confirmado en documentación oficial.
5. **Decisión de estilos pendiente** (CSS puro vs Tailwind); agregar Tailwind requiere aviso previo por la regla U3.
6. **Estado del MCP oficial de Postgres:** verificado como archivado a la fecha; re-verificar antes de presentar.
