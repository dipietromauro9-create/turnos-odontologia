import { readAuthState, refrescarAccessToken } from "./auth";
import { apiBaseUrl } from "./base";
import { ApiError, leerError, type DomainErrorEnvelope } from "./errors";

export { ApiError };
export type { DomainErrorEnvelope };

/** Único punto de attach del access token del panel. */
function authHeaders(token: string | null): Record<string, string> {
  return token === null ? {} : { Authorization: `Bearer ${token}` };
}

function esRutaDeAuth(path: string): boolean {
  return path.startsWith("/auth/");
}

async function ejecutar(
  path: string,
  init: RequestInit | undefined,
  token: string | null,
): Promise<Response> {
  return fetch(`${apiBaseUrl()}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(token),
      ...(init?.headers ?? {}),
    },
  });
}

async function leerPayload(response: Response): Promise<unknown> {
  return response.headers.get("content-type")?.includes("application/json") === true
    ? response.json()
    : null;
}

async function respuestaJson<T>(response: Response): Promise<T> {
  const payload = await leerPayload(response);
  if (!response.ok) throw leerError(payload, response.status);
  return payload as T;
}

/** Request autenticada: ante 401 de panel reintenta una sola vez con refresh. */
export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const tokenInicial = readAuthState().token;
  let response = await ejecutar(path, init, tokenInicial);

  if (response.status === 401 && tokenInicial !== null && !esRutaDeAuth(path)) {
    try {
      const renovado = await refrescarAccessToken();
      response = await ejecutar(path, init, renovado);
    } catch {
      /* el refresh ya limpió la sesión; se propaga el 401 original */
    }
  }

  return respuestaJson<T>(response);
}

export async function apiGet<T>(path: string): Promise<T> {
  return apiFetch<T>(path, { method: "GET" });
}

/** Descarga binaria autenticada (CSV); no intenta parsear JSON. */
export async function apiBlob(path: string): Promise<Blob> {
  const tokenInicial = readAuthState().token;
  let response = await ejecutar(path, { method: "GET" }, tokenInicial);

  if (response.status === 401 && tokenInicial !== null && !esRutaDeAuth(path)) {
    try {
      const renovado = await refrescarAccessToken();
      response = await ejecutar(path, { method: "GET" }, renovado);
    } catch {
      /* sesión limpiada por el refresh */
    }
  }

  if (!response.ok) {
    const payload = await leerPayload(response);
    throw leerError(payload, response.status);
  }
  return response.blob();
}
