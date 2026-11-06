import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { ApiError } from "../../shared/api/client";
import {
  crearReserva,
  getCatalogo,
  getDisponibilidad,
  type CatalogoPublico,
  type HuecoPublico,
  type ReservaPublicaOut,
} from "../../shared/api/turneroClient";
import { CodigoTurnoCard } from "./CodigoTurnoCard";
import { HuecosGrid } from "./HuecosGrid";
import { ReservaModal } from "./ReservaModal";
import { SemanaSelector } from "./SemanaSelector";
import { inicioDeSemana, sumarSemanas } from "./fechas";

function mensajeDeError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === "RN-TU-01") {
      return "Ese horario acaba de ocuparse. Elegí otro.";
    }
    return error.message;
  }
  return "No pudimos completar la operación. Intentá de nuevo.";
}

/** Página pública de reserva: catálogo, semana navegable y formulario anónimo. */
export function TurneroPublicoPage(): React.JSX.Element {
  const { slug } = useParams<{ slug: string }>();
  const [catalogo, setCatalogo] = useState<CatalogoPublico | null>(null);
  const [profesionalId, setProfesionalId] = useState("");
  const [prestacionId, setPrestacionId] = useState("");
  const [inicioSemana, setInicioSemana] = useState<Date>(() => inicioDeSemana(new Date()));
  const [huecos, setHuecos] = useState<readonly HuecoPublico[]>([]);
  const [seleccionado, setSeleccionado] = useState<HuecoPublico | null>(null);
  const [reserva, setReserva] = useState<ReservaPublicaOut | null>(null);
  const [cargando, setCargando] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [errorReserva, setErrorReserva] = useState<string | null>(null);

  useEffect(() => {
    if (slug === undefined) return;
    let vigente = true;
    getCatalogo(slug).then(
      (data) => {
        if (!vigente) return;
        setCatalogo(data);
        setProfesionalId(data.profesionales[0]?.id ?? "");
        setPrestacionId(data.prestaciones[0]?.id ?? "");
      },
      (fallo: unknown) => {
        if (vigente) setError(mensajeDeError(fallo));
      },
    );
    return () => {
      vigente = false;
    };
  }, [slug]);

  useEffect(() => {
    if (slug === undefined || profesionalId === "" || prestacionId === "") return;
    let vigente = true;
    setCargando(true);
    setError(null);
    getDisponibilidad(slug, {
      profesional_id: profesionalId,
      prestacion_id: prestacionId,
      desde: inicioSemana.toISOString(),
      hasta: sumarSemanas(inicioSemana, 1).toISOString(),
    }).then(
      (data) => {
        if (!vigente) return;
        setHuecos(data);
        setCargando(false);
      },
      (fallo: unknown) => {
        if (!vigente) return;
        setError(mensajeDeError(fallo));
        setCargando(false);
      },
    );
    return () => {
      vigente = false;
    };
  }, [slug, profesionalId, prestacionId, inicioSemana]);

  if (slug === undefined) {
    return (
      <main>
        <p role="alert">Falta el consultorio en la URL.</p>
      </main>
    );
  }

  if (reserva !== null) {
    return (
      <main>
        <CodigoTurnoCard codigo={reserva.codigo_publico} inicio={reserva.inicio} />
      </main>
    );
  }

  const profesional = catalogo?.profesionales.find((p) => p.id === profesionalId);
  const prestacion = catalogo?.prestaciones.find((p) => p.id === prestacionId);

  const confirmar = (datos: { nombre: string; telefono: string }): void => {
    if (seleccionado === null) return;
    setEnviando(true);
    setErrorReserva(null);
    crearReserva(slug, {
      nombre: datos.nombre,
      telefono: datos.telefono,
      profesional_id: seleccionado.profesional_id,
      prestacion_id: seleccionado.prestacion_id,
      inicio: seleccionado.inicio,
    }).then(
      (data) => {
        setReserva(data);
        setHuecos((previos) => previos.filter((h) => h.inicio !== seleccionado.inicio));
        setSeleccionado(null);
        setEnviando(false);
      },
      (fallo: unknown) => {
        setErrorReserva(mensajeDeError(fallo));
        setEnviando(false);
      },
    );
  };

  return (
    <main>
      <h1>Reservar turno</h1>
      {catalogo === null ? null : (
        <p>
          {catalogo.consultorio.nombre} · {catalogo.consultorio.slug}
        </p>
      )}

      {catalogo !== null && catalogo.profesionales.length > 0 ? (
        <label>
          Profesional
          <select value={profesionalId} onChange={(e) => setProfesionalId(e.target.value)}>
            {catalogo.profesionales.map((p) => (
              <option key={p.id} value={p.id}>
                {p.nombre}
              </option>
            ))}
          </select>
        </label>
      ) : null}

      {catalogo !== null && catalogo.prestaciones.length > 0 ? (
        <label>
          Prestación
          <select value={prestacionId} onChange={(e) => setPrestacionId(e.target.value)}>
            {catalogo.prestaciones.map((p) => (
              <option key={p.id} value={p.id}>
                {p.nombre}
              </option>
            ))}
          </select>
        </label>
      ) : null}

      <SemanaSelector
        inicioSemana={inicioSemana}
        onAnterior={() => setInicioSemana((actual) => sumarSemanas(actual, -1))}
        onSiguiente={() => setInicioSemana((actual) => sumarSemanas(actual, 1))}
      />

      {cargando ? <p role="status">Cargando disponibilidad…</p> : null}
      {error === null ? null : (
        <p role="alert" className="error">
          {error}
        </p>
      )}

      <HuecosGrid
        huecos={huecos}
        onSeleccionar={(hueco) => {
          setErrorReserva(null);
          setSeleccionado(hueco);
        }}
      />

      {seleccionado === null ? null : (
        <ReservaModal
          hueco={seleccionado}
          profesionalNombre={profesional?.nombre ?? "Profesional"}
          prestacionNombre={prestacion?.nombre ?? "Prestación"}
          enviando={enviando}
          error={errorReserva}
          onCerrar={() => {
            setErrorReserva(null);
            setSeleccionado(null);
          }}
          onConfirmar={confirmar}
        />
      )}
    </main>
  );
}
