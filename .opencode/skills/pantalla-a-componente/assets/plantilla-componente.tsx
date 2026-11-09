// Fuente de diseño: Stitch <projectId>/<screenId> — docs/design/<feature>/<screenId>.html
// Esqueleto de partida: adaptá nombres y props al dominio de la feature.
// Reglas: sin `any` (R2), sin datos reales de pacientes (R9), colores solo por tokens CSS.

import { horaDe } from "../turnero/fechas";

export type EstadoTurno = "reservado" | "confirmado" | "atendido" | "ausente" | "cancelado";

export type AccionTurno = "confirmar" | "atender" | "registrar-ausencia" | "cancelar";

export interface TurnoVista {
  readonly id: string;
  readonly paciente: string;
  readonly profesional: string;
  readonly prestacion: string;
  /** ISO 8601 con offset; se muestra tal como lo envía el backend. */
  readonly inicio: string;
  readonly fin: string;
  readonly estado: EstadoTurno;
  readonly esSobreturno: boolean;
}

interface Props {
  readonly turno: TurnoVista;
  /** Si no se pasa, la tarjeta es de solo lectura y no renderiza acciones. */
  readonly onAccion?: (turno: TurnoVista, accion: AccionTurno) => void;
}

const ETIQUETA_ESTADO: Record<EstadoTurno, string> = {
  reservado: "Reservado",
  confirmado: "Confirmado",
  atendido: "Atendido",
  ausente: "Ausente",
  cancelado: "Cancelado",
};

/** RN-TU-04: los estados terminales no tienen salida. */
const ACCIONES_POR_ESTADO: Record<EstadoTurno, readonly AccionTurno[]> = {
  reservado: ["confirmar", "cancelar"],
  confirmado: ["atender", "registrar-ausencia", "cancelar"],
  atendido: [],
  ausente: [],
  cancelado: [],
};

const ETIQUETA_ACCION: Record<AccionTurno, string> = {
  confirmar: "Confirmar",
  atender: "Atender",
  "registrar-ausencia": "Registrar ausencia",
  cancelar: "Cancelar",
};

export function TurnoCard({ turno, onAccion }: Props): React.JSX.Element {
  const etiqueta = ETIQUETA_ESTADO[turno.estado];
  const acciones = ACCIONES_POR_ESTADO[turno.estado];
  const clases = ["turno", `turno--${turno.estado}`];
  if (turno.esSobreturno) clases.push("turno--sobreturno");

  return (
    <article
      className={clases.join(" ")}
      aria-label={`Turno de ${turno.paciente}, ${etiqueta}`}
    >
      <header>
        <span className="turno__hora">
          {horaDe(turno.inicio)}–{horaDe(turno.fin)}
        </span>
        <span className="turno__etiqueta-estado">{etiqueta}</span>
        {turno.esSobreturno ? (
          <span className="turno__etiqueta-sobreturno">Sobreturno</span>
        ) : null}
      </header>
      <p className="turno__paciente">{turno.paciente}</p>
      <p className="turno__detalle">
        {turno.prestacion} · {turno.profesional}
      </p>
      {onAccion !== undefined && acciones.length > 0 ? (
        <footer>
          {acciones.map((accion) => (
            <button key={accion} type="button" onClick={() => onAccion(turno, accion)}>
              {ETIQUETA_ACCION[accion]}
            </button>
          ))}
        </footer>
      ) : null}
    </article>
  );
}
