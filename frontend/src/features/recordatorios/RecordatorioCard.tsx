import type { RecordatorioOut } from "../../shared/api/recordatoriosClient";
import { formatearFechaHora } from "../turnero/fechas";

interface Props {
  readonly fila: RecordatorioOut;
  readonly procesando: boolean;
  readonly onCopiar: (fila: RecordatorioOut) => void;
  readonly onEnviado: (fila: RecordatorioOut) => void;
  readonly onFallido: (fila: RecordatorioOut) => void;
}

/** Tarjeta de la cola: datos del turno, texto copiable y acciones de marcado. */
export function RecordatorioCard({
  fila,
  procesando,
  onCopiar,
  onEnviado,
  onFallido,
}: Props): React.JSX.Element {
  return (
    <li className="recordatorio">
      <p className="recordatorio__datos">
        {fila.paciente} · {fila.profesional} · {formatearFechaHora(fila.inicio)}
      </p>
      <p>
        <span className={`recordatorio__estado recordatorio__estado--${fila.estado}`}>
          {fila.estado}
        </span>
      </p>
      <pre className="recordatorio__texto">{fila.texto}</pre>
      <div className="recordatorio__acciones">
        <button type="button" onClick={() => onCopiar(fila)}>
          Copiar
        </button>
        <button
          type="button"
          className="boton-primario"
          disabled={procesando}
          onClick={() => onEnviado(fila)}
        >
          Marcar enviado
        </button>
        <button type="button" disabled={procesando} onClick={() => onFallido(fila)}>
          Marcar fallido
        </button>
      </div>
    </li>
  );
}
