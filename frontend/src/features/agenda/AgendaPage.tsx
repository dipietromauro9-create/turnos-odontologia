import { useEffect, useMemo, useState } from "react";

import { ApiError } from "../../shared/api/client";
import { useAuthState } from "../../shared/api/auth";
import {
  getAgendaDia,
  getAgendaSemana,
  type AgendaOut,
  type TurnoAgenda,
} from "../../shared/api/agendaClient";
import { accionTurno, type AccionTurno } from "../../shared/api/turnosClient";
import { ConfiguracionAgenda } from "./ConfiguracionAgenda";
import { NuevoTurnoModal } from "./NuevoTurnoModal";
import { TurnoCard } from "./TurnoCard";
import {
  fechaISO,
  inicioSemana,
  sumarDias,
  tituloPeriodo,
  type VistaAgenda,
} from "./fechas";
import "./estados.css";

function mensajeDeError(error: unknown): string {
  if (error instanceof ApiError) return `${error.message} (${error.code})`;
  return "No pudimos cargar la agenda. Intentá de nuevo.";
}

/** Agenda interna día/semana: columnas por profesional, estados y acciones (US-005). */
export function AgendaPage(): React.JSX.Element {
  const { usuario } = useAuthState();
  const [vista, setVista] = useState<VistaAgenda>("semana");
  const [ancla, setAncla] = useState<Date>(() => new Date());
  const [profesionalId, setProfesionalId] = useState("");
  const [datos, setDatos] = useState<AgendaOut | null>(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [recarga, setRecarga] = useState(0);
  const [procesando, setProcesando] = useState<string | null>(null);
  const [mostrarNuevo, setMostrarNuevo] = useState(false);

  const puedeElegirProfesional =
    usuario?.rol === "recepcion" || usuario?.es_dueno === true;

  useEffect(() => {
    let vivo = true;
    setCargando(true);
    setError(null);
    const pedido =
      vista === "dia"
        ? getAgendaDia(fechaISO(ancla), profesionalId === "" ? undefined : profesionalId)
        : getAgendaSemana(
            fechaISO(inicioSemana(ancla)),
            profesionalId === "" ? undefined : profesionalId,
          );
    pedido.then(
      (agenda) => {
        if (!vivo) return;
        setDatos(agenda);
        setCargando(false);
      },
      (fallo: unknown) => {
        if (!vivo) return;
        setError(mensajeDeError(fallo));
        setCargando(false);
      },
    );
    return () => {
      vivo = false;
    };
  }, [vista, ancla, profesionalId, recarga]);

  const columnas = useMemo(() => datos?.profesionales ?? [], [datos]);

  const mover = (direccion: number): void => {
    setAncla((actual) => sumarDias(actual, direccion * (vista === "dia" ? 1 : 7)));
  };

  const aplicarAccion = (turno: TurnoAgenda, accion: AccionTurno): void => {
    setProcesando(turno.id);
    setError(null);
    accionTurno(turno.id, accion).then(
      () => {
        setProcesando(null);
        setRecarga((valor) => valor + 1);
      },
      (fallo: unknown) => {
        setError(mensajeDeError(fallo));
        setProcesando(null);
        setRecarga((valor) => valor + 1);
      },
    );
  };

  const creado = (): void => {
    setMostrarNuevo(false);
    setRecarga((valor) => valor + 1);
  };

  return (
    <main>
      <h1>Agenda</h1>

      <div className="agenda-toolbar" role="toolbar" aria-label="Controles de agenda">
        <button type="button" aria-pressed={vista === "dia"} onClick={() => setVista("dia")}>
          Día
        </button>
        <button type="button" aria-pressed={vista === "semana"} onClick={() => setVista("semana")}>
          Semana
        </button>
        <button type="button" onClick={() => mover(-1)}>
          Período anterior
        </button>
        <button type="button" onClick={() => setAncla(new Date())}>
          Hoy
        </button>
        <button type="button" onClick={() => mover(1)}>
          Período siguiente
        </button>
        <span className="agenda-periodo" aria-live="polite">
          {datos === null ? "" : tituloPeriodo(datos.rango.desde, datos.rango.hasta, vista)}
        </span>
        {puedeElegirProfesional ? (
          <label>
            Profesional
            <select value={profesionalId} onChange={(e) => setProfesionalId(e.target.value)}>
              <option value="">Todos</option>
              {columnas.map((profesional) => (
                <option key={profesional.id} value={profesional.id}>
                  {profesional.nombre}
                </option>
              ))}
            </select>
          </label>
        ) : null}
        <button type="button" className="boton-primario" onClick={() => setMostrarNuevo(true)}>
          Nuevo turno
        </button>
      </div>

      {error === null ? null : (
        <p role="alert" className="agenda-error">
          {error}
        </p>
      )}

      {cargando ? (
        <p role="status" className="agenda-cargando">
          Cargando agenda…
        </p>
      ) : null}

      {!cargando && datos !== null && datos.turnos.length === 0 ? (
        <p role="status" className="agenda-vacia">
          No hay turnos en el período.
        </p>
      ) : null}

      {datos === null ? null : (
        <>
          <div className="agenda-grilla">
            {columnas.map((profesional) => {
              const turnos = datos.turnos.filter(
                (turno) => turno.profesional_id === profesional.id,
              );
              return (
                <section
                  key={profesional.id}
                  className="agenda-columna"
                  aria-label={`Agenda de ${profesional.nombre}`}
                >
                  <h2>{profesional.nombre}</h2>
                  <p className="turno__detalle">{profesional.especialidad ?? ""}</p>
                  {turnos.length === 0 ? (
                    <p className="agenda-vacia">Sin turnos</p>
                  ) : (
                    turnos.map((turno) => (
                      <TurnoCard
                        key={turno.id}
                        turno={turno}
                        procesando={procesando === turno.id}
                        onAccion={aplicarAccion}
                      />
                    ))
                  )}
                </section>
              );
            })}
          </div>

          {datos.bloqueos.length === 0 ? null : (
            <section className="agenda-bloqueos" aria-label="Bloqueos">
              <h2>Bloqueos</h2>
              <ul>
                {datos.bloqueos.map((bloqueo) => (
                  <li key={bloqueo.id}>
                    {bloqueo.motivo}: {bloqueo.desde.slice(0, 16)}–{bloqueo.hasta.slice(0, 16)}
                  </li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}

      {datos === null ? null : (
        <NuevoTurnoModal
          abierto={mostrarNuevo}
          onCerrar={() => setMostrarNuevo(false)}
          onCreado={creado}
          profesionales={datos.profesionales}
          prestaciones={datos.prestaciones}
          puedeElegirProfesional={puedeElegirProfesional}
          fechaInicial={fechaISO(ancla)}
        />
      )}

      {usuario?.es_dueno === true ? (
        <ConfiguracionAgenda profesionales={datos?.profesionales ?? []} />
      ) : null}
    </main>
  );
}
