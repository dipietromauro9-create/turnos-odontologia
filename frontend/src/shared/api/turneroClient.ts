import { apiFetch, apiGet } from "./client";

/** Contratos públicos del turnero; espejo estricto de los schemas del backend. */

export interface ConsultorioPublico {
  readonly nombre: string;
  readonly slug: string;
}

export interface ProfesionalPublico {
  readonly id: string;
  readonly nombre: string;
  readonly especialidad: string | null;
}

export interface PrestacionPublica {
  readonly id: string;
  readonly nombre: string;
  readonly duracion_min: number;
  readonly precio_ref: string | null;
}

export interface CatalogoPublico {
  readonly consultorio: ConsultorioPublico;
  readonly profesionales: readonly ProfesionalPublico[];
  readonly prestaciones: readonly PrestacionPublica[];
}

export interface HuecoPublico {
  readonly inicio: string;
  readonly fin: string;
  readonly profesional_id: string;
  readonly prestacion_id: string;
}

export type EstadoTurno = "reservado" | "confirmado" | "atendido" | "cancelado" | "ausente";

export interface ReservaPublicaCreate {
  readonly nombre: string;
  readonly telefono: string;
  readonly profesional_id: string;
  readonly prestacion_id: string;
  readonly inicio: string;
}

export interface ReservaPublicaOut {
  readonly codigo_publico: string;
  readonly inicio: string;
  readonly fin: string;
  readonly estado: EstadoTurno;
  readonly profesional_id: string;
  readonly prestacion_id: string;
  readonly duplicado_advertencia: boolean;
}

export interface TurnoPublicoOut {
  readonly codigo_publico: string;
  readonly inicio: string;
  readonly fin: string;
  readonly estado: EstadoTurno;
  readonly profesional: ProfesionalPublico;
  readonly prestacion: PrestacionPublica;
}

export interface DisponibilidadParams {
  readonly profesional_id: string;
  readonly prestacion_id: string;
  readonly desde: string;
  readonly hasta: string;
}

function query(params: Record<string, string>): string {
  return new URLSearchParams(params).toString();
}

function slugPath(slug: string): string {
  return `/turnero/${encodeURIComponent(slug)}`;
}

export async function getCatalogo(slug: string): Promise<CatalogoPublico> {
  return apiGet<CatalogoPublico>(`${slugPath(slug)}/catalogo`);
}

export async function getDisponibilidad(
  slug: string,
  params: DisponibilidadParams,
): Promise<readonly HuecoPublico[]> {
  return apiGet<readonly HuecoPublico[]>(
    `${slugPath(slug)}/disponibilidad?${query({ ...params })}`,
  );
}

export async function crearReserva(
  slug: string,
  datos: ReservaPublicaCreate,
): Promise<ReservaPublicaOut> {
  return apiFetch<ReservaPublicaOut>(`${slugPath(slug)}/reservas`, {
    method: "POST",
    body: JSON.stringify(datos),
  });
}

export async function getMisTurnos(codigo: string): Promise<TurnoPublicoOut> {
  return apiGet<TurnoPublicoOut>(`/turnero/mis-turnos?${query({ codigo })}`);
}

export async function cancelarTurno(
  codigo: string,
  motivo: string | null,
): Promise<TurnoPublicoOut> {
  return apiFetch<TurnoPublicoOut>("/turnero/mis-turnos/cancelar", {
    method: "POST",
    body: JSON.stringify({ codigo, motivo_cancelacion: motivo }),
  });
}

export async function reprogramarTurno(
  codigo: string,
  nuevoInicio: string,
): Promise<TurnoPublicoOut> {
  return apiFetch<TurnoPublicoOut>("/turnero/mis-turnos/reprogramar", {
    method: "POST",
    body: JSON.stringify({ codigo, nuevo_inicio: nuevoInicio }),
  });
}
