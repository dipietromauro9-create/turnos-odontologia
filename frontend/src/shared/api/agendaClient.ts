/** Contrato del agregador de agenda (core/agenda): payload mínimo, sin ficha clínica. */

import { apiGet } from "./client";
import type { EstadoTurno } from "./turneroClient";

export interface RangoAgenda {
  readonly desde: string;
  readonly hasta: string;
}

export interface ProfesionalAgenda {
  readonly id: string;
  readonly nombre: string;
  readonly especialidad: string | null;
  readonly activo: boolean;
}

export interface PrestacionAgenda {
  readonly id: string;
  readonly nombre: string;
  readonly duracion_min: number;
}

export interface PacienteAgenda {
  readonly id: string;
  readonly nombre: string;
}

export interface TurnoAgenda {
  readonly id: string;
  readonly profesional_id: string;
  readonly inicio: string;
  readonly fin: string;
  readonly estado: EstadoTurno;
  readonly es_sobreturno: boolean;
  readonly motivo_sobreturno: string | null;
  readonly motivo_cancelacion: string | null;
  readonly paciente: PacienteAgenda;
  readonly prestacion: PrestacionAgenda;
}

export interface BloqueoAgenda {
  readonly id: string;
  readonly profesional_id: string | null;
  readonly desde: string;
  readonly hasta: string;
  readonly motivo: string;
}

export interface AgendaOut {
  readonly rango: RangoAgenda;
  readonly profesionales: readonly ProfesionalAgenda[];
  readonly prestaciones: readonly PrestacionAgenda[];
  readonly turnos: readonly TurnoAgenda[];
  readonly bloqueos: readonly BloqueoAgenda[];
}

function consulta(base: Record<string, string>, profesionalId?: string): string {
  const params = new URLSearchParams(base);
  if (profesionalId !== undefined && profesionalId.length > 0) {
    params.set("profesional_id", profesionalId);
  }
  return params.toString();
}

export function getAgendaDia(fecha: string, profesionalId?: string): Promise<AgendaOut> {
  return apiGet<AgendaOut>(`/agenda/dia?${consulta({ fecha }, profesionalId)}`);
}

export function getAgendaSemana(desde: string, profesionalId?: string): Promise<AgendaOut> {
  return apiGet<AgendaOut>(`/agenda/semana?${consulta({ desde }, profesionalId)}`);
}
