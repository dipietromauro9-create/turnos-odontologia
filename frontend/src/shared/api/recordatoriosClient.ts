import { apiFetch, apiGet } from "./client";

/** Contratos de la cola de recordatorios; espejo estricto del backend. */

export type EstadoRecordatorio = "pendiente" | "enviado" | "fallido";

export interface RecordatorioOut {
  readonly id: string;
  readonly turno_id: string;
  readonly canal: "whatsapp_manual";
  readonly estado: EstadoRecordatorio;
  readonly texto: string;
  readonly inicio: string;
  readonly paciente: string;
  readonly profesional: string;
  readonly enviado_por: string | null;
  readonly creado_en: string;
}

export async function getRecordatorios(): Promise<readonly RecordatorioOut[]> {
  return apiGet<readonly RecordatorioOut[]>("/recordatorios/pendientes");
}

export async function marcarEnviado(id: string): Promise<RecordatorioOut> {
  return apiFetch<RecordatorioOut>(`/recordatorios/${id}/enviado`, { method: "POST" });
}

export async function marcarFallido(id: string): Promise<RecordatorioOut> {
  return apiFetch<RecordatorioOut>(`/recordatorios/${id}/fallido`, { method: "POST" });
}
