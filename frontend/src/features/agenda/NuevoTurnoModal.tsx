import { useEffect, useState } from "react";

import { ApiError } from "../../shared/api/client";
import type { PrestacionAgenda, ProfesionalAgenda } from "../../shared/api/agendaClient";
import { buscarPacientes, type PacienteBusqueda } from "../../shared/api/pacientesClient";
import { crearTurno, getHuecos, type HuecoOut } from "../../shared/api/turnosClient";
import { horaDe } from "../turnero/fechas";
import { inicioLocal, rangoDelDia } from "./fechas";

function mensajeDeError(error: unknown): string {
  if (error instanceof ApiError) return `${error.message} (${error.code})`;
  return "No pudimos completar la operación. Intentá de nuevo.";
}

interface Props {
  readonly abierto: boolean;
  readonly onCerrar: () => void;
  readonly onCreado: () => void;
  readonly profesionales: readonly ProfesionalAgenda[];
  readonly prestaciones: readonly PrestacionAgenda[];
  readonly puedeElegirProfesional: boolean;
  readonly fechaInicial: string;
}

/** Alta interna de turno: normal o sobreturno con motivo explícito (RN-TU-01/04/05). */
export function NuevoTurnoModal({
  abierto,
  onCerrar,
  onCreado,
  profesionales,
  prestaciones,
  puedeElegirProfesional,
  fechaInicial,
}: Props): React.JSX.Element | null {
  const [busqueda, setBusqueda] = useState("");
  const [resultados, setResultados] = useState<readonly PacienteBusqueda[]>([]);
  const [paciente, setPaciente] = useState<PacienteBusqueda | null>(null);
  const [profesionalId, setProfesionalId] = useState("");
  const [prestacionId, setPrestacionId] = useState("");
  const [fecha, setFecha] = useState(fechaInicial);
  const [hora, setHora] = useState("");
  const [sobreturno, setSobreturno] = useState(false);
  const [motivo, setMotivo] = useState("");
  const [huecos, setHuecos] = useState<readonly HuecoOut[]>([]);
  const [cargandoHuecos, setCargandoHuecos] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    if (!abierto) return;
    setFecha(fechaInicial);
    if (!puedeElegirProfesional && profesionales.length === 1) {
      setProfesionalId(profesionales[0]?.id ?? "");
    }
  }, [abierto, fechaInicial, puedeElegirProfesional, profesionales]);

  if (!abierto) return null;

  const buscar = (): void => {
    setError(null);
    buscarPacientes(busqueda).then(setResultados, (fallo: unknown) => {
      setError(mensajeDeError(fallo));
    });
  };

  const verHorarios = (): void => {
    setError(null);
    if (profesionalId === "" || prestacionId === "" || fecha === "") {
      setError("Elegí profesional, prestación y fecha para ver los horarios.");
      return;
    }
    const rango = rangoDelDia(fecha);
    setCargandoHuecos(true);
    getHuecos(profesionalId, prestacionId, rango.desde, rango.hasta).then(
      (disponibles) => {
        setHuecos(disponibles);
        setCargandoHuecos(false);
      },
      (fallo: unknown) => {
        setError(mensajeDeError(fallo));
        setCargandoHuecos(false);
      },
    );
  };

  const crear = (evento: React.FormEvent<HTMLFormElement>): void => {
    evento.preventDefault();
    setError(null);
    if (paciente === null) {
      setError("Elegí un paciente.");
      return;
    }
    if (profesionalId === "" || prestacionId === "" || hora === "") {
      setError("Elegí profesional, prestación y horario.");
      return;
    }
    if (sobreturno && motivo.trim() === "") {
      setError("El sobreturno requiere un motivo de urgencia.");
      return;
    }

    setEnviando(true);
    crearTurno({
      profesional_id: profesionalId,
      paciente_id: paciente.id,
      prestacion_id: prestacionId,
      inicio: inicioLocal(fecha, hora),
      es_sobreturno: sobreturno,
      motivo_sobreturno: sobreturno ? motivo : undefined,
    }).then(
      () => {
        setEnviando(false);
        onCreado();
      },
      (fallo: unknown) => {
        setError(mensajeDeError(fallo));
        setEnviando(false);
      },
    );
  };

  return (
    <section role="dialog" aria-modal="true" aria-label="Nuevo turno" className="modal">
      <div className="modal__caja">
        <h2>Nuevo turno</h2>
        <form onSubmit={crear}>
        <fieldset>
          <legend>Paciente</legend>
          <label>
            Buscar por nombre o teléfono
            <input
              type="search"
              value={busqueda}
              onChange={(evento) => setBusqueda(evento.target.value)}
            />
          </label>
          <button type="button" onClick={buscar}>
            Buscar paciente
          </button>
          {paciente === null ? null : <p role="status">Paciente: {paciente.nombre}</p>}
          <ul>
            {resultados.map((fila) => (
              <li key={fila.id}>
                <button
                  type="button"
                  onClick={() => {
                    setPaciente(fila);
                    setResultados([]);
                  }}
                >
                  {fila.nombre} · {fila.telefono}
                </button>
              </li>
            ))}
          </ul>
        </fieldset>

        <label>
          Profesional
          <select
            value={profesionalId}
            disabled={!puedeElegirProfesional}
            onChange={(evento) => setProfesionalId(evento.target.value)}
          >
            <option value="">Elegí un profesional</option>
            {profesionales.map((fila) => (
              <option key={fila.id} value={fila.id}>
                {fila.nombre}
              </option>
            ))}
          </select>
        </label>

        <label>
          Prestación
          <select value={prestacionId} onChange={(evento) => setPrestacionId(evento.target.value)}>
            <option value="">Elegí una prestación</option>
            {prestaciones.map((fila) => (
              <option key={fila.id} value={fila.id}>
                {fila.nombre} ({fila.duracion_min} min)
              </option>
            ))}
          </select>
        </label>

        <label>
          Fecha
          <input type="date" value={fecha} onChange={(evento) => setFecha(evento.target.value)} />
        </label>

        <label>
          Hora
          <input type="time" value={hora} onChange={(evento) => setHora(evento.target.value)} />
        </label>
        <button type="button" onClick={verHorarios} disabled={cargandoHuecos}>
          {cargandoHuecos ? "Buscando horarios…" : "Ver horarios"}
        </button>
        <ul aria-label="Horarios disponibles">
          {huecos.map((hueco) => (
            <li key={hueco.inicio}>
              <button type="button" onClick={() => setHora(horaDe(hueco.inicio))}>
                {horaDe(hueco.inicio)}
              </button>
            </li>
          ))}
        </ul>

        <label>
          <input
            type="checkbox"
            checked={sobreturno}
            onChange={(evento) => setSobreturno(evento.target.checked)}
          />
          Sobreturno
        </label>
        {sobreturno ? (
          <label>
            Motivo del sobreturno
            <textarea value={motivo} onChange={(evento) => setMotivo(evento.target.value)} />
          </label>
        ) : null}

        {error === null ? null : (
          <p role="alert" className="error">
            {error}
          </p>
        )}

        <button type="submit" disabled={enviando}>
          {enviando ? "Creando…" : "Crear turno"}
        </button>
        <button type="button" onClick={onCerrar}>
          Cancelar
        </button>
      </form>
      </div>
    </section>
  );
}
