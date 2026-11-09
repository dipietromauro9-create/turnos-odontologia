/** Configuración de agenda del dueño: plantilla semanal y bloqueos. */

import { apiFetch } from "./client";

export interface DisponibilidadOut {
  readonly id: string;
  readonly profesional_id: string;
  readonly dia_semana: number;
  readonly hora_desde: string;
  readonly hora_hasta: string;
}

export interface BloqueoOut {
  readonly id: string;
  readonly profesional_id: string | null;
  readonly desde: string;
  readonly hasta: string;
  readonly motivo: string;
}

export interface NuevaDisponibilidad {
  readonly profesional_id: string;
  readonly dia_semana: number;
  readonly hora_desde: string;
  readonly hora_hasta: string;
}

export interface NuevoBloqueo {
  readonly profesional_id: string | null;
  readonly desde: string;
  readonly hasta: string;
  readonly motivo: string;
}

function conProfesional(path: string, profesionalId?: string): string {
  if (profesionalId === undefined || profesionalId.length === 0) return path;
  return `${path}?profesional_id=${encodeURIComponent(profesionalId)}`;
}

export function getDisponibilidad(profesionalId?: string): Promise<readonly DisponibilidadOut[]> {
  return apiFetch<readonly DisponibilidadOut[]>(conProfesional("/disponibilidad", profesionalId), {
    method: "GET",
  });
}

export function crearDisponibilidad(datos: NuevaDisponibilidad): Promise<DisponibilidadOut> {
  return apiFetch<DisponibilidadOut>("/disponibilidad", {
    method: "POST",
    body: JSON.stringify(datos),
  });
}

export function eliminarDisponibilidad(id: string): Promise<void> {
  return apiFetch<void>(`/disponibilidad/${id}`, { method: "DELETE" });
}

export function getBloqueos(profesionalId?: string): Promise<readonly BloqueoOut[]> {
  return apiFetch<readonly BloqueoOut[]>(conProfesional("/bloqueos", profesionalId), {
    method: "GET",
  });
}

export function crearBloqueo(datos: NuevoBloqueo): Promise<BloqueoOut> {
  return apiFetch<BloqueoOut>("/bloqueos", { method: "POST", body: JSON.stringify(datos) });
}

export function eliminarBloqueo(id: string): Promise<void> {
  return apiFetch<void>(`/bloqueos/${id}`, { method: "DELETE" });
}
