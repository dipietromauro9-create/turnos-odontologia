/** Fechas de la agenda en calendario local (la API resuelve el rango en TZ del consultorio). */

import { formatearDia } from "../turnero/fechas";

export type VistaAgenda = "dia" | "semana";

export const OFFSET_CONSULTORIO = "-03:00";

export function fechaISO(fecha: Date): string {
  const anio = fecha.getFullYear();
  const mes = String(fecha.getMonth() + 1).padStart(2, "0");
  const dia = String(fecha.getDate()).padStart(2, "0");
  return `${anio}-${mes}-${dia}`;
}

export function sumarDias(fecha: Date, dias: number): Date {
  const copia = new Date(fecha.getFullYear(), fecha.getMonth(), fecha.getDate());
  copia.setDate(copia.getDate() + dias);
  return copia;
}

export function inicioSemana(fecha: Date): Date {
  const dia = fecha.getDay();
  const desplazamiento = dia === 0 ? -6 : 1 - dia;
  return sumarDias(fecha, desplazamiento);
}

/** Inicio ISO con el offset fijo del consultorio (Argentina, sin DST). */
export function inicioLocal(fecha: string, hora: string): string {
  return `${fecha}T${hora}:00${OFFSET_CONSULTORIO}`;
}

export function tituloPeriodo(desde: string, hasta: string, vista: VistaAgenda): string {
  if (vista === "dia") return formatearDia(desde);
  const ultimo = sumarDias(new Date(`${hasta.slice(0, 10)}T12:00:00`), -1);
  return `${formatearDia(desde)} – ${formatearDia(fechaISO(ultimo))}`;
}

export function rangoDelDia(fecha: string): { desde: string; hasta: string } {
  const base = new Date(`${fecha}T12:00:00`);
  return {
    desde: `${fecha}T00:00:00${OFFSET_CONSULTORIO}`,
    hasta: `${fechaISO(sumarDias(base, 1))}T00:00:00${OFFSET_CONSULTORIO}`,
  };
}
