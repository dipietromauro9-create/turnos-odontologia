import { useState } from "react";

interface ReprogramarModalProps {
  readonly enviando: boolean;
  readonly error: string | null;
  readonly onCerrar: () => void;
  readonly onConfirmar: (nuevoInicio: string) => void;
}

/** Reprogramación atómica a un nuevo horario (RN-TU-07). */
export function ReprogramarModal({
  enviando,
  error,
  onCerrar,
  onConfirmar,
}: ReprogramarModalProps): React.JSX.Element {
  const [nuevoInicio, setNuevoInicio] = useState("");

  return (
    <div
      className="turnero-modal"
      role="dialog"
      aria-modal="true"
      aria-labelledby="titulo-reprogramar"
    >
      <div className="turnero-modal__caja">
        <h2 id="titulo-reprogramar">Reprogramar turno</h2>
      <form
        onSubmit={(evento) => {
          evento.preventDefault();
          onConfirmar(new Date(nuevoInicio).toISOString());
        }}
      >
        <label>
          Nuevo día y hora
          <input
            required
            type="datetime-local"
            value={nuevoInicio}
            onChange={(evento) => setNuevoInicio(evento.target.value)}
          />
        </label>

        {error === null ? null : (
          <p role="alert" className="error">
            {error}
          </p>
        )}

        <div className="acciones">
          <button type="button" onClick={onCerrar} disabled={enviando}>
            Volver
          </button>
          <button type="submit" disabled={enviando}>
            {enviando ? "Reprogramando…" : "Confirmar cambio"}
          </button>
        </div>
      </form>
      </div>
    </div>
  );
}
