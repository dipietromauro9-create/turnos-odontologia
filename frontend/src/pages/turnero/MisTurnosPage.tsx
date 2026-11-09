import { useState } from "react";
import type { FormEvent } from "react";

import { CancelarModal } from "../../features/turnero/CancelarModal";
import { ReprogramarModal } from "../../features/turnero/ReprogramarModal";
import { formatearFechaHora } from "../../features/turnero/fechas";
import { ApiError } from "../../shared/api/client";
import {
  cancelarTurno,
  getMisTurnos,
  reprogramarTurno,
  type TurnoPublicoOut,
} from "../../shared/api/turneroClient";

type Modal = "cancelar" | "reprogramar" | null;

function mensajeDeError(error: unknown, contexto: "buscar" | "accion"): string {
  if (error instanceof ApiError) {
    if (contexto === "buscar" && error.status === 404) {
      return "No encontramos un turno con ese código.";
    }
    if (error.code === "RN-TU-01") {
      return "Ese horario ya no está disponible. Elegí otro.";
    }
    if (error.code === "RN-TU-04") {
      return "Ese turno ya no se puede modificar.";
    }
    return error.message;
  }
  return "No pudimos completar la operación. Intentá de nuevo.";
}

/** Autogestión del paciente por código: consulta, cancelación y reprogramación. */
export function MisTurnosPage(): React.JSX.Element {
  const [codigo, setCodigo] = useState("");
  const [turno, setTurno] = useState<TurnoPublicoOut | null>(null);
  const [buscando, setBuscando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [modal, setModal] = useState<Modal>(null);
  const [enviando, setEnviando] = useState(false);
  const [errorAccion, setErrorAccion] = useState<string | null>(null);

  const buscar = (evento: FormEvent<HTMLFormElement>): void => {
    evento.preventDefault();
    setBuscando(true);
    setError(null);
    setTurno(null);
    getMisTurnos(codigo.trim()).then(
      (data) => {
        setTurno(data);
        setBuscando(false);
      },
      (fallo: unknown) => {
        setError(mensajeDeError(fallo, "buscar"));
        setBuscando(false);
      },
    );
  };

  const confirmarCancelacion = (motivo: string | null): void => {
    if (turno === null) return;
    setEnviando(true);
    setErrorAccion(null);
    cancelarTurno(turno.codigo_publico, motivo).then(
      (data) => {
        setTurno(data);
        setModal(null);
        setEnviando(false);
      },
      (fallo: unknown) => {
        setErrorAccion(mensajeDeError(fallo, "accion"));
        setEnviando(false);
      },
    );
  };

  const confirmarReprogramacion = (nuevoInicio: string): void => {
    if (turno === null) return;
    setEnviando(true);
    setErrorAccion(null);
    reprogramarTurno(turno.codigo_publico, nuevoInicio).then(
      (data) => {
        setTurno(data);
        setModal(null);
        setEnviando(false);
      },
      (fallo: unknown) => {
        setErrorAccion(mensajeDeError(fallo, "accion"));
        setEnviando(false);
      },
    );
  };

  return (
    <main className="turnero-publico mis-turnos">
      <h1>Mis turnos</h1>

      <form onSubmit={buscar}>
        <label>
          Código de turno
          <input
            required
            value={codigo}
            onChange={(evento) => setCodigo(evento.target.value)}
          />
        </label>
        <button type="submit" disabled={buscando}>
          {buscando ? "Buscando…" : "Buscar turno"}
        </button>
      </form>

      {error === null ? null : (
        <p role="alert" className="error">
          {error}
        </p>
      )}

      {turno === null ? null : (
        <section aria-labelledby="titulo-turno">
          <h2 id="titulo-turno">Tu turno</h2>
          <p>{formatearFechaHora(turno.inicio)}</p>
          <p>
            {turno.prestacion.nombre} con {turno.profesional.nombre}
          </p>
          <p className="turno-estado" data-estado={turno.estado}>
            Estado: {turno.estado}
          </p>

          {turno.estado === "cancelado" ? null : (
            <div className="acciones">
              <button
                type="button"
                onClick={() => {
                  setModal("cancelar");
                  setErrorAccion(null);
                }}
              >
                Cancelar turno
              </button>
              <button
                type="button"
                onClick={() => {
                  setModal("reprogramar");
                  setErrorAccion(null);
                }}
              >
                Reprogramar
              </button>
            </div>
          )}
        </section>
      )}

      {modal === "cancelar" ? (
        <CancelarModal
          enviando={enviando}
          error={errorAccion}
          onCerrar={() => setModal(null)}
          onConfirmar={confirmarCancelacion}
        />
      ) : null}

      {modal === "reprogramar" ? (
        <ReprogramarModal
          enviando={enviando}
          error={errorAccion}
          onCerrar={() => setModal(null)}
          onConfirmar={confirmarReprogramacion}
        />
      ) : null}
    </main>
  );
}
