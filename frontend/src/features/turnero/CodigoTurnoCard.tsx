import { useState } from "react";

import { formatearFechaHora } from "./fechas";

interface CodigoTurnoCardProps {
  readonly codigo: string;
  readonly inicio: string;
}

/** Confirmación de reserva: código destacado y copia al portapapeles. */
export function CodigoTurnoCard({ codigo, inicio }: CodigoTurnoCardProps): React.JSX.Element {
  const [copiado, setCopiado] = useState(false);

  const copiar = (): void => {
    const portapapeles = navigator.clipboard;
    if (portapapeles === undefined) {
      setCopiado(false);
      return;
    }
    void portapapeles.writeText(codigo).then(
      () => setCopiado(true),
      () => setCopiado(false),
    );
  };

  return (
    <section aria-labelledby="titulo-confirmacion" className="confirmacion">
      <h2 id="titulo-confirmacion">¡Turno reservado!</h2>
      <p>{formatearFechaHora(inicio)}</p>
      <p>
        Guardá este código para consultar, cancelar o reprogramar tu turno:
      </p>
      <strong className="codigo">{codigo}</strong>
      <button type="button" onClick={copiar}>
        {copiado ? "Código copiado" : "Copiar código"}
      </button>
    </section>
  );
}
