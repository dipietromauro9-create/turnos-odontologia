import { useState } from "react";

import type { HuecoPublico } from "../../shared/api/turneroClient";
import { formatearFechaHora } from "./fechas";

interface ReservaModalProps {
  readonly hueco: HuecoPublico;
  readonly profesionalNombre: string;
  readonly prestacionNombre: string;
  readonly enviando: boolean;
  readonly error: string | null;
  readonly onCerrar: () => void;
  readonly onConfirmar: (datos: { nombre: string; telefono: string }) => void;
}

/** Formulario mínimo de reserva anónima: nombre y teléfono (RN-PA-01). */
export function ReservaModal({
  hueco,
  profesionalNombre,
  prestacionNombre,
  enviando,
  error,
  onCerrar,
  onConfirmar,
}: ReservaModalProps): React.JSX.Element {
  const [nombre, setNombre] = useState("");
  const [telefono, setTelefono] = useState("");

  return (
    <div
      className="turnero-modal"
      role="dialog"
      aria-modal="true"
      aria-labelledby="titulo-reserva"
    >
      <div className="turnero-modal__caja">
        <h2 id="titulo-reserva">Confirmar reserva</h2>
      <p>
        {prestacionNombre} con {profesionalNombre}
      </p>
      <p>{formatearFechaHora(hueco.inicio)}</p>

      <form
        onSubmit={(evento) => {
          evento.preventDefault();
          onConfirmar({ nombre, telefono });
        }}
      >
        <label>
          Nombre y apellido
          <input
            required
            value={nombre}
            onChange={(evento) => setNombre(evento.target.value)}
          />
        </label>
        <label>
          Teléfono
          <input
            required
            inputMode="tel"
            value={telefono}
            onChange={(evento) => setTelefono(evento.target.value)}
          />
        </label>

        {error === null ? null : (
          <p role="alert" className="error">
            {error}
          </p>
        )}

        <div className="acciones">
          <button type="button" onClick={onCerrar} disabled={enviando}>
            Cancelar
          </button>
          <button type="submit" disabled={enviando}>
            {enviando ? "Reservando…" : "Confirmar reserva"}
          </button>
        </div>
      </form>
      </div>
    </div>
  );
}
