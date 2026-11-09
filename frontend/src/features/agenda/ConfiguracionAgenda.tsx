import { useEffect, useState } from "react";

import { ApiError } from "../../shared/api/client";
import type { ProfesionalAgenda } from "../../shared/api/agendaClient";
import {
  crearBloqueo,
  crearDisponibilidad,
  eliminarBloqueo,
  eliminarDisponibilidad,
  getBloqueos,
  getDisponibilidad,
  type BloqueoOut,
  type DisponibilidadOut,
} from "../../shared/api/configAgendaClient";
import { OFFSET_CONSULTORIO } from "./fechas";

const DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"];

function mensajeDeError(error: unknown): string {
  if (error instanceof ApiError) return `${error.message} (${error.code})`;
  return "No pudimos completar la operación. Intentá de nuevo.";
}

function isoLocal(valor: string): string {
  return valor.length === 0 ? "" : `${valor}:00${OFFSET_CONSULTORIO}`;
}

interface Props {
  readonly profesionales: readonly ProfesionalAgenda[];
}

/** Plantilla semanal y bloqueos: la UI solo se muestra al dueño (RN-AU-02). */
export function ConfiguracionAgenda({ profesionales }: Props): React.JSX.Element {
  const [disponibilidad, setDisponibilidad] = useState<readonly DisponibilidadOut[]>([]);
  const [bloqueos, setBloqueos] = useState<readonly BloqueoOut[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);

  const [profesionalDispo, setProfesionalDispo] = useState("");
  const [diaSemana, setDiaSemana] = useState("0");
  const [horaDesde, setHoraDesde] = useState("09:00");
  const [horaHasta, setHoraHasta] = useState("13:00");

  const [profesionalBloqueo, setProfesionalBloqueo] = useState("");
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  const [motivo, setMotivo] = useState("");

  const cargar = (): void => {
    getDisponibilidad().then(setDisponibilidad, (fallo: unknown) => {
      setError(mensajeDeError(fallo));
    });
    getBloqueos().then(setBloqueos, (fallo: unknown) => {
      setError(mensajeDeError(fallo));
    });
  };

  useEffect(cargar, []);

  const agregarFranja = (evento: React.FormEvent<HTMLFormElement>): void => {
    evento.preventDefault();
    setError(null);
    setAviso(null);
    crearDisponibilidad({
      profesional_id: profesionalDispo,
      dia_semana: Number(diaSemana),
      hora_desde: `${horaDesde}:00`,
      hora_hasta: `${horaHasta}:00`,
    }).then(
      () => {
        setAviso("Franja agregada");
        cargar();
      },
      (fallo: unknown) => setError(mensajeDeError(fallo)),
    );
  };

  const agregarBloqueo = (evento: React.FormEvent<HTMLFormElement>): void => {
    evento.preventDefault();
    setError(null);
    setAviso(null);
    crearBloqueo({
      profesional_id: profesionalBloqueo === "" ? null : profesionalBloqueo,
      desde: isoLocal(desde),
      hasta: isoLocal(hasta),
      motivo,
    }).then(
      () => {
        setAviso("Bloqueo agregado");
        cargar();
      },
      (fallo: unknown) => setError(mensajeDeError(fallo)),
    );
  };

  const borrarFranja = (id: string): void => {
    eliminarDisponibilidad(id).then(cargar, (fallo: unknown) => setError(mensajeDeError(fallo)));
  };

  const borrarBloqueo = (id: string): void => {
    eliminarBloqueo(id).then(cargar, (fallo: unknown) => setError(mensajeDeError(fallo)));
  };

  return (
    <section className="config-agenda" aria-label="Configuración de agenda">
      <h2>Configuración de agenda</h2>
      {error === null ? null : (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {aviso === null ? null : <p role="status">{aviso}</p>}

      <h3>Disponibilidad semanal</h3>
      <ul>
        {disponibilidad.map((franja) => (
          <li key={franja.id}>
            {DIAS[franja.dia_semana] ?? franja.dia_semana} {franja.hora_desde.slice(0, 5)}–
            {franja.hora_hasta.slice(0, 5)}
            <button type="button" onClick={() => borrarFranja(franja.id)}>
              Eliminar franja
            </button>
          </li>
        ))}
      </ul>
      <form onSubmit={agregarFranja} aria-label="Agregar franja">
        <select
          aria-label="Profesional de la franja"
          value={profesionalDispo}
          onChange={(e) => setProfesionalDispo(e.target.value)}
          required
        >
          <option value="">Profesional</option>
          {profesionales.map((fila) => (
            <option key={fila.id} value={fila.id}>
              {fila.nombre}
            </option>
          ))}
        </select>
        <select
          aria-label="Día de la semana"
          value={diaSemana}
          onChange={(e) => setDiaSemana(e.target.value)}
        >
          {DIAS.map((nombre, indice) => (
            <option key={nombre} value={String(indice)}>
              {nombre}
            </option>
          ))}
        </select>
        <input
          type="time"
          aria-label="Hora desde"
          value={horaDesde}
          onChange={(e) => setHoraDesde(e.target.value)}
          required
        />
        <input
          type="time"
          aria-label="Hora hasta"
          value={horaHasta}
          onChange={(e) => setHoraHasta(e.target.value)}
          required
        />
        <button type="submit">Agregar franja</button>
      </form>

      <h3>Bloqueos</h3>
      <ul>
        {bloqueos.map((bloqueo) => (
          <li key={bloqueo.id}>
            {bloqueo.motivo}: {bloqueo.desde.slice(0, 16)}–{bloqueo.hasta.slice(0, 16)}
            <button type="button" onClick={() => borrarBloqueo(bloqueo.id)}>
              Eliminar bloqueo
            </button>
          </li>
        ))}
      </ul>
      <form onSubmit={agregarBloqueo} aria-label="Agregar bloqueo">
        <select
          aria-label="Profesional del bloqueo"
          value={profesionalBloqueo}
          onChange={(e) => setProfesionalBloqueo(e.target.value)}
        >
          <option value="">Todo el consultorio</option>
          {profesionales.map((fila) => (
            <option key={fila.id} value={fila.id}>
              {fila.nombre}
            </option>
          ))}
        </select>
        <input
          type="datetime-local"
          aria-label="Desde"
          value={desde}
          onChange={(e) => setDesde(e.target.value)}
          required
        />
        <input
          type="datetime-local"
          aria-label="Hasta"
          value={hasta}
          onChange={(e) => setHasta(e.target.value)}
          required
        />
        <input
          type="text"
          aria-label="Motivo"
          placeholder="Motivo"
          value={motivo}
          onChange={(e) => setMotivo(e.target.value)}
          required
        />
        <button type="submit">Agregar bloqueo</button>
      </form>
    </section>
  );
}
