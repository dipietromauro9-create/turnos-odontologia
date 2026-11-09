/** Búsqueda de pacientes para el alta interna de turnos (sin datos clínicos). */

import { apiGet } from "./client";

export interface PacienteBusqueda {
  readonly id: string;
  readonly nombre: string;
  readonly telefono: string;
}

export function buscarPacientes(q: string): Promise<readonly PacienteBusqueda[]> {
  const params = new URLSearchParams({ q });
  return apiGet<readonly PacienteBusqueda[]>(`/pacientes?${params.toString()}`);
}
