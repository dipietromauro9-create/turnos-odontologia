/** Utilidades de fecha del turnero: la hora se muestra tal como la envía el backend. */

export function inicioDeSemana(base: Date): Date {
  const copia = new Date(base.getFullYear(), base.getMonth(), base.getDate());
  const dia = copia.getDay();
  const desplazamiento = dia === 0 ? -6 : 1 - dia;
  copia.setDate(copia.getDate() + desplazamiento);
  return copia;
}

export function sumarSemanas(fecha: Date, semanas: number): Date {
  const copia = new Date(fecha.getFullYear(), fecha.getMonth(), fecha.getDate());
  copia.setDate(copia.getDate() + semanas * 7);
  return copia;
}

export function formatearRango(desde: Date): string {
  const hasta = sumarSemanas(desde, 1);
  hasta.setDate(hasta.getDate() - 1);
  return `${desde.toLocaleDateString("es-AR")} – ${hasta.toLocaleDateString("es-AR")}`;
}

export function fechaDe(iso: string): Date {
  const partes = iso.slice(0, 10).split("-");
  const anio = Number(partes[0] ?? "1970");
  const mes = Number(partes[1] ?? "1");
  const dia = Number(partes[2] ?? "1");
  return new Date(anio, mes - 1, dia);
}

export function formatearDia(iso: string): string {
  return fechaDe(iso).toLocaleDateString("es-AR", {
    weekday: "long",
    day: "numeric",
    month: "long",
  });
}

export function horaDe(iso: string): string {
  return iso.slice(11, 16);
}

export function formatearFechaHora(iso: string): string {
  return `${formatearDia(iso)} · ${horaDe(iso)}`;
}
