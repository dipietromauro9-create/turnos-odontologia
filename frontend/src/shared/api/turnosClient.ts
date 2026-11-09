/** Escrituras de turnos desde el panel: el cliente nunca calcula `fin` (RN-TU-02). */

import { apiFetch } from "./client";
import type { EstadoTurno } from "./turneroClient";

export interface TurnoOut {
  readonly id: string;
  readonly inicio: string;
  readonly fin: string;
  readonly estado: EstadoTurno;
  readonly es_sobreturno: boolean;
}

export interface CrearTurnoInput {
  readonly profesional_id: string;
  readonly paciente_id: string;
  readonly prestacion_id: string;
  readonly inicio: string;
  readonly es_sobreturno: boolean;
  readonly motivo_sobreturno?: string;
}

export type AccionTurno = "confirmar" | "atender" | "registrar-ausencia" | "cancelar";

export interface HuecoOut {
  readonly inicio: string;
  readonly fin: string;
  readonly profesional_id: string;
  readonly prestacion_id: string;
}

export function crearTurno(input: CrearTurnoInput): Promise<TurnoOut> {
  const cuerpo = {
    profesional_id: input.profesional_id,
    paciente_id: input.paciente_id,
    prestacion_id: input.prestacion_id,
    inicio: input.inicio,
    es_sobreturno: input.es_sobreturno,
    motivo_sobreturno: input.es_sobreturno ? input.motivo_sobreturno : undefined,
  };
  return apiFetch<TurnoOut>("/turnos", { method: "POST", body: JSON.stringify(cuerpo) });
}

export function accionTurno(id: string, accion: AccionTurno): Promise<TurnoOut> {
  return apiFetch<TurnoOut>(`/turnos/${id}/${accion}`, { method: "POST" });
}

export function getHuecos(
  profesionalId: string,
  prestacionId: string,
  desde: string,
  hasta: string,
): Promise<readonly HuecoOut[]> {
  const params = new URLSearchParams({
    profesional_id: profesionalId,
    prestacion_id: prestacionId,
    desde,
    hasta,
  });
  return apiFetch<readonly HuecoOut[]>(`/disponibilidad/huecos?${params.toString()}`, {
    method: "GET",
  });
}
