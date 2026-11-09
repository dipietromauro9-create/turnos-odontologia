# Artefactos de diseño (Stitch)

Acá se versionan las pantallas exportadas antes de convertirlas en componentes con la skill `pantalla-a-componente`.

## Convención

```
docs/design/
└── <feature>/
    ├── <screenId>.html   # HTML exportado (insumo de diseño, no código final)
    ├── <screenId>.png    # Captura de referencia
    └── DESIGN.md         # Opcional: design system exportado de Stitch
```

- `<feature>` usa el mismo nombre que `frontend/src/features/` (`agenda`, `turnero`, `recordatorios`, `reportes`).
- `<screenId>` es el identificador real de Stitch, no un nombre inventado. Se usa para auditar que el componente corresponde a una pantalla existente.
- El HTML de Stitch trae estilos embebidos: se conserva como referencia, pero **no se copia** al proyecto. El código final es React + TypeScript + CSS puro.

## Cómo exportar

Con el MCP de Stitch configurado:

1. `list_screens` para ubicar la pantalla y obtener el `name` de sus archivos.
2. `download_file` para bajar el HTML y la captura PNG.
3. Guardarlos acá con la convención de arriba.
4. Si el proyecto tiene design system, descargar también el `DESIGN.md` (o generarlo desde Stitch).

## Regla dura

**R9**: nunca exportar ni versionar pantallas con datos reales de pacientes. Si la pantalla de Stitch tiene datos de ejemplo, reemplazarlos por ficticios antes de guardar el HTML y la captura.
