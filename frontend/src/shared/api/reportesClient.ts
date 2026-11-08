import { apiBlob, apiFetch, apiGet } from "./client";

/** Contratos de reportes y exportación; espejo estricto del backend. */

export interface ReportesFiltros {
  readonly desde: string;
  readonly hasta: string;
  readonly profesional_id?: string;
}

export interface OcupacionOut {
  readonly profesional_id: string;
  readonly nombre: string;
  readonly turnos_activos: number;
  readonly minutos_disponibles: number;
  readonly minutos_ocupados: number;
  readonly ocupacion: number;
}

export interface AusenciaOut {
  readonly profesional_id: string;
  readonly nombre: string;
  readonly atendidos: number;
  readonly ausentes: number;
  readonly tasa_ausencia: number;
}

export interface RecordatoriosOut {
  readonly profesional_id: string;
  readonly nombre: string;
  readonly turnos_confirmados: number;
  readonly recordatorios_enviados: number;
  readonly ratio: number;
}

export type TipoExport = "turnos" | "pacientes";
export type EstadoExport = "pendiente" | "procesando" | "listo" | "fallido";

export interface ExportacionOut {
  readonly id: string;
  readonly tipo: TipoExport;
  readonly estado: EstadoExport;
  readonly desde: string | null;
  readonly hasta: string | null;
  readonly error: string | null;
  readonly creado_en: string;
  readonly descarga_url: string | null;
}

function query(filtros: ReportesFiltros): string {
  const params = new URLSearchParams({ desde: filtros.desde, hasta: filtros.hasta });
  if (filtros.profesional_id !== undefined) {
    params.set("profesional_id", filtros.profesional_id);
  }
  return params.toString();
}

export async function getOcupacion(
  filtros: ReportesFiltros,
): Promise<readonly OcupacionOut[]> {
  return apiGet<readonly OcupacionOut[]>(`/reportes/ocupacion?${query(filtros)}`);
}

export async function getAusencias(
  filtros: ReportesFiltros,
): Promise<readonly AusenciaOut[]> {
  return apiGet<readonly AusenciaOut[]>(`/reportes/ausencias?${query(filtros)}`);
}

export async function getRecordatorios(
  filtros: ReportesFiltros,
): Promise<readonly RecordatoriosOut[]> {
  return apiGet<readonly RecordatoriosOut[]>(`/reportes/recordatorios?${query(filtros)}`);
}

export async function crearExport(
  tipo: TipoExport,
  filtros: Pick<ReportesFiltros, "desde" | "hasta">,
): Promise<ExportacionOut> {
  return apiFetch<ExportacionOut>(`/export/${tipo}.csv`, {
    method: "POST",
    body: JSON.stringify({ desde: filtros.desde, hasta: filtros.hasta }),
  });
}

export async function getExport(id: string): Promise<ExportacionOut> {
  return apiGet<ExportacionOut>(`/export/${id}`);
}

export async function reintentarExport(id: string): Promise<ExportacionOut> {
  return apiFetch<ExportacionOut>(`/export/${id}/reintentar`, { method: "POST" });
}

export async function descargarExport(id: string): Promise<Blob> {
  return apiBlob(`/export/${id}/archivo`);
}
