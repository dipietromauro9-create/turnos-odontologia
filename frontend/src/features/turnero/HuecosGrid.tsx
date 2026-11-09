import type { HuecoPublico } from "../../shared/api/turneroClient";
import { formatearDia, horaDe } from "./fechas";

interface HuecosGridProps {
  readonly huecos: readonly HuecoPublico[];
  readonly onSeleccionar: (hueco: HuecoPublico) => void;
}

interface GrupoDia {
  readonly dia: string;
  readonly huecos: readonly HuecoPublico[];
}

function agruparPorDia(huecos: readonly HuecoPublico[]): readonly GrupoDia[] {
  const grupos = new Map<string, HuecoPublico[]>();
  for (const hueco of huecos) {
    const dia = hueco.inicio.slice(0, 10);
    const actual = grupos.get(dia);
    if (actual === undefined) {
      grupos.set(dia, [hueco]);
    } else {
      actual.push(hueco);
    }
  }
  return [...grupos.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([dia, items]) => ({ dia, huecos: items }));
}

/** Grilla de huecos agrupada por día; cada botón abre el formulario de reserva. */
export function HuecosGrid({ huecos, onSeleccionar }: HuecosGridProps): React.JSX.Element {
  if (huecos.length === 0) {
    return <p role="status" className="turnero-vacio">No hay horarios disponibles esta semana.</p>;
  }

  return (
    <div className="huecos-grid">
      {agruparPorDia(huecos).map((grupo) => (
        <section key={grupo.dia} aria-label={formatearDia(grupo.huecos[0]?.inicio ?? grupo.dia)}>
          <h3>{formatearDia(grupo.huecos[0]?.inicio ?? grupo.dia)}</h3>
          <ul>
            {grupo.huecos.map((hueco) => (
              <li key={hueco.inicio}>
                <button type="button" onClick={() => onSeleccionar(hueco)}>
                  {horaDe(hueco.inicio)}
                </button>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
