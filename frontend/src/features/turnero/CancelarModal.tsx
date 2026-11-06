import { useState } from "react";

interface CancelarModalProps {
  readonly enviando: boolean;
  readonly error: string | null;
  readonly onCerrar: () => void;
  readonly onConfirmar: (motivo: string | null) => void;
}

/** Cancelación con motivo opcional (RN-TU-05). */
export function CancelarModal({
  enviando,
  error,
  onCerrar,
  onConfirmar,
}: CancelarModalProps): React.JSX.Element {
  const [motivo, setMotivo] = useState("");

  return (
    <div role="dialog" aria-modal="true" aria-labelledby="titulo-cancelar">
      <h2 id="titulo-cancelar">Cancelar turno</h2>
      <form
        onSubmit={(evento) => {
          evento.preventDefault();
          onConfirmar(motivo.trim() === "" ? null : motivo.trim());
        }}
      >
        <label>
          Motivo (opcional)
          <textarea value={motivo} onChange={(evento) => setMotivo(evento.target.value)} />
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
            {enviando ? "Cancelando…" : "Confirmar cancelación"}
          </button>
        </div>
      </form>
    </div>
  );
}
