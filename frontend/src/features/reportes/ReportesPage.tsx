import { useEffect, useMemo, useState } from "react";

import { ApiError } from "../../shared/api/client";
import {
  crearExport,
  descargarExport,
  getAusencias,
  getExport,
  getOcupacion,
  getRecordatorios,
  reintentarExport,
  type AusenciaOut,
  type ExportacionOut,
  type OcupacionOut,
  type RecordatoriosOut,
  type TipoExport,
} from "../../shared/api/reportesClient";

export const MAX_INTENTOS = 60;

function mensajeDeError(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  return "No pudimos completar la operación. Intentá de nuevo.";
}

function porcentaje(valor: number): string {
  return `${Math.round(valor * 100)}%`;
}

function guardarArchivo(blob: Blob, nombre: string): void {
  if (typeof URL.createObjectURL !== "function") {
    return;
  }
  const url = URL.createObjectURL(blob);
  const enlace = document.createElement("a");
  enlace.href = url;
  enlace.download = nombre;
  enlace.click();
  URL.revokeObjectURL(url);
}

function fechaLocal(diasAtras: number): string {
  const fecha = new Date();
  fecha.setDate(fecha.getDate() - diasAtras);
  return fecha.toISOString().slice(0, 10);
}

interface Props {
  readonly intervaloPollMs?: number;
}

/** Reportes de gestión y exportación CSV (US-012, US-013). */
export function ReportesPage({ intervaloPollMs = 2000 }: Props): React.JSX.Element {
  const [desde, setDesde] = useState(fechaLocal(30));
  const [hasta, setHasta] = useState(fechaLocal(0));
  const [profesionalId, setProfesionalId] = useState("");
  const [ocupacion, setOcupacion] = useState<readonly OcupacionOut[]>([]);
  const [ausencias, setAusencias] = useState<readonly AusenciaOut[]>([]);
  const [recordatorios, setRecordatorios] = useState<readonly RecordatoriosOut[]>([]);
  const [profesionales, setProfesionales] = useState<readonly OcupacionOut[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [job, setJob] = useState<ExportacionOut | null>(null);
  const [intentos, setIntentos] = useState(0);
  const [exportError, setExportError] = useState<string | null>(null);

  const filtros = useMemo(
    () => ({
      desde: `${desde}T00:00:00-03:00`,
      hasta: `${hasta}T23:59:59-03:00`,
      ...(profesionalId === "" ? {} : { profesional_id: profesionalId }),
    }),
    [desde, hasta, profesionalId],
  );

  useEffect(() => {
    setCargando(true);
    setError(null);
    Promise.all([
      getOcupacion(filtros),
      getAusencias(filtros),
      getRecordatorios(filtros),
    ]).then(
      ([datosOcupacion, datosAusencias, datosRecordatorios]) => {
        setOcupacion(datosOcupacion);
        setAusencias(datosAusencias);
        setRecordatorios(datosRecordatorios);
        setCargando(false);
      },
      (fallo: unknown) => {
        setError(mensajeDeError(fallo));
        setCargando(false);
      },
    );
  }, [filtros]);

  useEffect(() => {
    if (profesionalId === "" && ocupacion.length > 0) {
      setProfesionales(ocupacion);
    }
  }, [ocupacion, profesionalId]);

  useEffect(() => {
    if (job === null || job.estado === "listo" || job.estado === "fallido") {
      return;
    }
    if (intentos >= MAX_INTENTOS) {
      return;
    }
    const timer = setTimeout(() => {
      getExport(job.id).then(
        (actual) => {
          setJob(actual);
          setIntentos((previos) => previos + 1);
        },
        (fallo: unknown) => {
          setExportError(mensajeDeError(fallo));
          setIntentos(MAX_INTENTOS);
        },
      );
    }, intervaloPollMs);
    return () => clearTimeout(timer);
  }, [job, intentos, intervaloPollMs]);

  const exportar = (tipo: TipoExport): void => {
    setExportError(null);
    setIntentos(0);
    setJob(null);
    crearExport(tipo, { desde: filtros.desde, hasta: filtros.hasta }).then(
      (nuevo) => {
        setJob(nuevo);
        setIntentos(0);
      },
      (fallo: unknown) => setExportError(mensajeDeError(fallo)),
    );
  };

  const reintentar = (): void => {
    if (job === null) {
      return;
    }
    setExportError(null);
    reintentarExport(job.id).then(
      (nuevo) => {
        setJob(nuevo);
        setIntentos(0);
      },
      (fallo: unknown) => setExportError(mensajeDeError(fallo)),
    );
  };

  const descargar = (): void => {
    if (job === null) {
      return;
    }
    descargarExport(job.id).then(
      (blob) => guardarArchivo(blob, `${job.tipo}-${job.id}.csv`),
      (fallo: unknown) => setExportError(mensajeDeError(fallo)),
    );
  };

  const vacio =
    !cargando &&
    ocupacion.length === 0 &&
    ausencias.length === 0 &&
    recordatorios.length === 0;

  return (
    <main className="reportes">
      <h1>Reportes</h1>

      <section className="reportes__filtros" aria-label="Filtros">
        <label>
          Desde
          <input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} />
        </label>
        <label>
          Hasta
          <input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} />
        </label>
        <label>
          Profesional
          <select
            value={profesionalId}
            onChange={(e) => setProfesionalId(e.target.value)}
          >
            <option value="">Todos</option>
            {profesionales.map((fila) => (
              <option key={fila.profesional_id} value={fila.profesional_id}>
                {fila.nombre}
              </option>
            ))}
          </select>
        </label>
      </section>

      {error === null ? null : (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {exportError === null ? null : (
        <p role="alert" className="error">
          {exportError}
        </p>
      )}

      {cargando ? (
        <p>Cargando…</p>
      ) : vacio ? (
        <p>Sin datos en el período.</p>
      ) : (
        <>
          <section aria-labelledby="titulo-ocupacion">
            <h2 id="titulo-ocupacion">Ocupación</h2>
            <table>
              <thead>
                <tr>
                  <th>Profesional</th>
                  <th>Turnos activos</th>
                  <th>Minutos ocupados</th>
                  <th>Minutos disponibles</th>
                  <th>Ocupación</th>
                </tr>
              </thead>
              <tbody>
                {ocupacion.map((fila) => (
                  <tr key={fila.profesional_id}>
                    <td>{fila.nombre}</td>
                    <td>{fila.turnos_activos}</td>
                    <td>{fila.minutos_ocupados}</td>
                    <td>{fila.minutos_disponibles}</td>
                    <td>{porcentaje(fila.ocupacion)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <section aria-labelledby="titulo-ausencias">
            <h2 id="titulo-ausencias">Ausencias</h2>
            <table>
              <thead>
                <tr>
                  <th>Profesional</th>
                  <th>Atendidos</th>
                  <th>Ausentes</th>
                  <th>Tasa</th>
                </tr>
              </thead>
              <tbody>
                {ausencias.map((fila) => (
                  <tr key={fila.profesional_id}>
                    <td>{fila.nombre}</td>
                    <td>{fila.atendidos}</td>
                    <td>{fila.ausentes}</td>
                    <td>{porcentaje(fila.tasa_ausencia)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <section aria-labelledby="titulo-in03">
            <h2 id="titulo-in03">Recordatorios (IN-03)</h2>
            <ul>
              {recordatorios.map((fila) => (
                <li key={fila.profesional_id}>
                  {fila.nombre}: {fila.recordatorios_enviados} enviados /{" "}
                  {fila.turnos_confirmados} confirmados · {porcentaje(fila.ratio)}
                </li>
              ))}
            </ul>
          </section>
        </>
      )}

      <section aria-labelledby="titulo-export">
        <h2 id="titulo-export">Exportar datos</h2>
        <button type="button" className="boton-primario" onClick={() => exportar("turnos")}>
          Exportar turnos
        </button>
        <button type="button" onClick={() => exportar("pacientes")}>
          Exportar pacientes
        </button>

        {job === null ? null : (
          <div>
            <p>Estado: {job.estado}</p>
            {job.estado === "fallido" ? (
              <p>
                {job.error}
                <button type="button" onClick={reintentar}>
                  Reintentar
                </button>
              </p>
            ) : null}
            {job.estado === "listo" ? (
              <button type="button" className="boton-primario" onClick={descargar}>
                Descargar
              </button>
            ) : null}
            {job.estado === "procesando" && intentos >= MAX_INTENTOS ? (
              <p>Seguimos procesando; probá de nuevo en unos minutos.</p>
            ) : null}
          </div>
        )}
      </section>
    </main>
  );
}
