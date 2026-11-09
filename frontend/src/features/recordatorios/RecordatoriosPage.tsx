import { useEffect, useState } from "react";

import { ApiError } from "../../shared/api/client";
import {
  getRecordatorios,
  marcarEnviado,
  marcarFallido,
  type RecordatorioOut,
} from "../../shared/api/recordatoriosClient";
import { RecordatorioCard } from "./RecordatorioCard";

function mensajeDeError(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  return "No pudimos completar la operación. Intentá de nuevo.";
}

/** Cola manual de recepción: copiar el mensaje y marcar enviado/fallido. */
export function RecordatoriosPage(): React.JSX.Element {
  const [filas, setFilas] = useState<readonly RecordatorioOut[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [copiado, setCopiado] = useState<string | null>(null);
  const [procesando, setProcesando] = useState<string | null>(null);

  useEffect(() => {
    getRecordatorios().then(
      (data) => {
        setFilas(data);
        setCargando(false);
      },
      (fallo: unknown) => {
        setError(mensajeDeError(fallo));
        setCargando(false);
      },
    );
  }, []);

  const copiar = (fila: RecordatorioOut): void => {
    setAviso(null);
    setCopiado(null);
    if (navigator.clipboard === undefined) {
      setAviso("Copiá el texto manualmente.");
      return;
    }
    navigator.clipboard.writeText(fila.texto).then(
      () => setCopiado(fila.id),
      () => setAviso("Copiá el texto manualmente."),
    );
  };

  const enviado = (fila: RecordatorioOut): void => {
    setProcesando(fila.id);
    setError(null);
    marcarEnviado(fila.id).then(
      () => {
        setFilas((previas) => previas.filter((item) => item.id !== fila.id));
        setProcesando(null);
      },
      (fallo: unknown) => {
        setError(mensajeDeError(fallo));
        setProcesando(null);
      },
    );
  };

  const fallido = (fila: RecordatorioOut): void => {
    setProcesando(fila.id);
    setError(null);
    marcarFallido(fila.id).then(
      (actualizada) => {
        setFilas((previas) =>
          previas.map((item) => (item.id === actualizada.id ? actualizada : item)),
        );
        setProcesando(null);
      },
      (fallo: unknown) => {
        setError(mensajeDeError(fallo));
        setProcesando(null);
      },
    );
  };

  return (
    <main className="recordatorios">
      <h1>Recordatorios</h1>
      <p className="recordatorios__resumen">
        {filas.length === 0 ? "Cola vacía" : `${filas.length} en cola`}
      </p>

      {error === null ? null : (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {aviso === null ? null : <p role="status">{aviso}</p>}
      {copiado === null ? null : <p role="status">Texto copiado</p>}

      {cargando ? (
        <p>Cargando…</p>
      ) : filas.length === 0 ? (
        <p>No hay recordatorios pendientes.</p>
      ) : (
        <ul>
          {filas.map((fila) => (
            <RecordatorioCard
              key={fila.id}
              fila={fila}
              procesando={procesando === fila.id}
              onCopiar={copiar}
              onEnviado={enviado}
              onFallido={fallido}
            />
          ))}
        </ul>
      )}
    </main>
  );
}
