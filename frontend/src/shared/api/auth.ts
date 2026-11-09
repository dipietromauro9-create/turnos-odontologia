/** Sesión del panel: storage versionado, login, me, refresh y logout. */

import { useSyncExternalStore } from "react";

import { apiBaseUrl } from "./base";
import { leerError } from "./errors";

export type Rol = "recepcion" | "profesional";

export interface UsuarioSesion {
  readonly id: string;
  readonly tenant_id: string;
  readonly nombre: string;
  readonly email: string;
  readonly rol: Rol;
  readonly es_dueno: boolean;
}

export interface AuthState {
  readonly token: string | null;
  readonly usuario: UsuarioSesion | null;
}

interface TokenOut {
  readonly access_token: string;
}

/** Storage key versionada: v2 agrega la identidad (rol/es_dueno) junto al access. */
const STORAGE_KEY = "turnos-odontologia/auth/v2";
const VACIO: AuthState = { token: null, usuario: null };

const listeners = new Set<() => void>();
let cache: { raw: string | null; state: AuthState } | null = null;

function leerCrudo(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

function parsearUsuario(valor: unknown): UsuarioSesion | null {
  if (typeof valor !== "object" || valor === null) return null;
  const fila = valor as Record<string, unknown>;
  const rol = fila["rol"];
  if (rol !== "recepcion" && rol !== "profesional") return null;
  if (
    typeof fila["id"] !== "string" ||
    typeof fila["tenant_id"] !== "string" ||
    typeof fila["nombre"] !== "string" ||
    typeof fila["email"] !== "string" ||
    typeof fila["es_dueno"] !== "boolean"
  ) {
    return null;
  }
  return {
    id: fila["id"],
    tenant_id: fila["tenant_id"],
    nombre: fila["nombre"],
    email: fila["email"],
    rol,
    es_dueno: fila["es_dueno"],
  };
}

function parsear(raw: string | null): AuthState {
  if (raw === null) return VACIO;
  try {
    const dato: unknown = JSON.parse(raw);
    if (typeof dato !== "object" || dato === null) return VACIO;
    const fila = dato as Record<string, unknown>;
    const token = typeof fila["token"] === "string" ? fila["token"] : null;
    return { token, usuario: parsearUsuario(fila["usuario"]) };
  } catch {
    return VACIO;
  }
}

function notificar(): void {
  for (const listener of listeners) listener();
}

export function readAuthState(): AuthState {
  const raw = leerCrudo();
  if (cache === null || cache.raw !== raw) cache = { raw, state: parsear(raw) };
  return cache.state;
}

export function writeAuthState(state: AuthState): void {
  const raw = JSON.stringify(state);
  try {
    localStorage.setItem(STORAGE_KEY, raw);
  } catch {
    /* storage lleno o bloqueado: la sesión dura lo que dure la pestaña */
  }
  cache = { raw, state };
  notificar();
}

export function clearAuthState(): void {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* noop */
  }
  cache = { raw: null, state: VACIO };
  notificar();
}

export function suscribirAuth(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** Estado reactivo del shell; el cliente HTTP muta el mismo storage. */
export function useAuthState(): AuthState {
  return useSyncExternalStore(suscribirAuth, readAuthState, readAuthState);
}

async function leerPayload(response: Response): Promise<unknown> {
  const tipo = response.headers.get("content-type");
  return tipo?.includes("application/json") === true ? response.json() : null;
}

async function pedirToken(email: string, password: string): Promise<string> {
  const response = await fetch(`${apiBaseUrl()}/auth/login`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  const payload = await leerPayload(response);
  if (!response.ok) throw leerError(payload, response.status);
  const access = (payload as TokenOut | null)?.access_token;
  if (typeof access !== "string" || access.length === 0) {
    throw new Error("La respuesta de login no trajo un access token");
  }
  return access;
}

async function pedirMe(token: string): Promise<UsuarioSesion> {
  const response = await fetch(`${apiBaseUrl()}/auth/me`, {
    method: "GET",
    headers: { Authorization: `Bearer ${token}` },
  });
  const payload = await leerPayload(response);
  if (!response.ok) throw leerError(payload, response.status);
  const usuario = parsearUsuario(payload);
  if (usuario === null) throw new Error("La respuesta de /auth/me no es válida");
  return usuario;
}

/** Login completo: token + identidad; deja la sesión lista para el shell. */
export async function login(email: string, password: string): Promise<UsuarioSesion> {
  const token = await pedirToken(email, password);
  const usuario = await pedirMe(token);
  writeAuthState({ token, usuario });
  return usuario;
}

/** Carga la identidad de un access existente (bootstrap de /auth/me). */
export async function cargarIdentidad(): Promise<UsuarioSesion> {
  const { token } = readAuthState();
  if (token === null) throw new Error("No hay sesión");
  const usuario = await pedirMe(token);
  writeAuthState({ token, usuario });
  return usuario;
}

export async function logout(): Promise<void> {
  try {
    await fetch(`${apiBaseUrl()}/auth/logout`, {
      method: "POST",
      credentials: "include",
    });
  } finally {
    clearAuthState();
  }
}

let refrescoEnCurso: Promise<string> | null = null;

/** Renueva el access una sola vez; si falla, limpia la sesión. */
export function refrescarAccessToken(): Promise<string> {
  if (refrescoEnCurso === null) {
    refrescoEnCurso = (async () => {
      const response = await fetch(`${apiBaseUrl()}/auth/refresh`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
      });
      const payload = await leerPayload(response);
      if (!response.ok) {
        clearAuthState();
        throw leerError(payload, response.status);
      }
      const access = (payload as TokenOut | null)?.access_token;
      if (typeof access !== "string" || access.length === 0) {
        clearAuthState();
        throw new Error("La respuesta de refresh no trajo un access token");
      }
      const { usuario } = readAuthState();
      writeAuthState({ token: access, usuario });
      return access;
    })().finally(() => {
      refrescoEnCurso = null;
    });
  }
  return refrescoEnCurso;
}

export { STORAGE_KEY };
