import { formatearRango } from "./fechas";

interface SemanaSelectorProps {
  readonly inicioSemana: Date;
  readonly onAnterior: () => void;
  readonly onSiguiente: () => void;
}

/** Navegación semanal del turnero público. */
export function SemanaSelector({
  inicioSemana,
  onAnterior,
  onSiguiente,
}: SemanaSelectorProps): React.JSX.Element {
  return (
    <div className="semana-selector" role="group" aria-label="Navegación de semana">
      <button type="button" onClick={onAnterior}>
        ← Semana anterior
      </button>
      <span aria-live="polite">{formatearRango(inicioSemana)}</span>
      <button type="button" onClick={onSiguiente}>
        Semana siguiente →
      </button>
    </div>
  );
}
