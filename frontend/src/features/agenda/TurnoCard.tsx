import { horaDe } from "../turnero/fechas";
import type { TurnoAgenda } from "../../shared/api/agendaClient";
import type { AccionTurno } from "../../shared/api/turnosClient";

const ETIQUETA_ESTADO: Record<TurnoAgenda["estado"], string> = {
  reservado: "Reservado",
  confirmado: "Confirmado",
  atendido: "Atendido",
  ausente: "Ausente",
  cancelado: "Cancelado",
};

/** RN-TU-04: los estados terminales no tienen salida. */
const ACCIONES_POR_ESTADO: Record<TurnoAgenda["estado"], readonly AccionTurno[]> = {
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

interface Props {
  readonly turno: TurnoAgenda;
  readonly procesando?: boolean;
  readonly onAccion?: (turno: TurnoAgenda, accion: AccionTurno) => void;
}

/** Tarjeta de turno: estado con etiqueta textual y acciones válidas (RN-TU-04). */
export function TurnoCard({ turno, procesando = false, onAccion }: Props): React.JSX.Element {
  const etiqueta = ETIQUETA_ESTADO[turno.estado];
  const acciones = ACCIONES_POR_ESTADO[turno.estado];
  const clases = ["turno", `turno--${turno.estado}`];
  if (turno.es_sobreturno) clases.push("turno--sobreturno");

  return (
    <article className={clases.join(" ")} aria-label={`Turno de ${turno.paciente.nombre}, ${etiqueta}`}>
      <header>
        <span className="turno__hora">
          {horaDe(turno.inicio)}–{horaDe(turno.fin)}
        </span>
        <span className="turno__etiqueta-estado">{etiqueta}</span>
        {turno.es_sobreturno ? (
          <span className="turno__etiqueta-sobreturno">Sobreturno</span>
        ) : null}
      </header>
      <p className="turno__paciente">{turno.paciente.nombre}</p>
      <p className="turno__detalle">{turno.prestacion.nombre}</p>
      {onAccion !== undefined && acciones.length > 0 ? (
        <footer>
          {acciones.map((accion) => (
            <button
              key={accion}
              type="button"
              disabled={procesando}
              onClick={() => onAccion(turno, accion)}
            >
              {ETIQUETA_ACCION[accion]}
            </button>
          ))}
        </footer>
      ) : null}
    </article>
  );
}
