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
    <li>
      <p>
        {fila.paciente} · {fila.profesional} · {formatearFechaHora(fila.inicio)}
      </p>
      <p>
        <span className={fila.estado}>{fila.estado}</span>
      </p>
      <pre>{fila.texto}</pre>
      <button type="button" onClick={() => onCopiar(fila)}>
        Copiar
      </button>
      <button type="button" disabled={procesando} onClick={() => onEnviado(fila)}>
        Marcar enviado
      </button>
      <button type="button" disabled={procesando} onClick={() => onFallido(fila)}>
        Marcar fallido
      </button>
    </li>
  );
}
