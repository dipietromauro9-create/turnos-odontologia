import { readAuthState } from "./auth";

/** Sobre de error de dominio del backend (RN-GL-01). */
export interface DomainErrorEnvelope {
  readonly code: string;
  readonly message: string;
  readonly details?: Record<string, unknown>;
}

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly details?: Record<string, unknown>;

  constructor(envelope: DomainErrorEnvelope, status: number) {
    super(envelope.message);
    this.name = "ApiError";
    this.code = envelope.code;
    this.status = status;
    this.details = envelope.details;
  }
}

function apiBaseUrl(): string {
  const base = import.meta.env["VITE_API_URL"];
  if (typeof base !== "string" || base.length === 0) {
    throw new Error("Falta VITE_API_URL: definir la URL base del backend en el entorno");
  }
  return base.replace(/\/$/, "");
}

/** Único punto de attach de auth (C-03 completa JWT/codigo_publico acá). */
function authHeaders(): Record<string, string> {
  const { token } = readAuthState();
  return token === null ? {} : { Authorization: `Bearer ${token}` };
}

function isDomainEnvelope(payload: unknown): payload is DomainErrorEnvelope {
  if (typeof payload !== "object" || payload === null) return false;
  const record = payload as Record<string, unknown>;
  return typeof record["code"] === "string" && typeof record["message"] === "string";
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl()}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
      ...(init?.headers ?? {}),
    },
  });
  const payload: unknown =
    response.headers.get("content-type")?.includes("application/json") === true
      ? await response.json()
      : null;
  if (!response.ok) {
    if (isDomainEnvelope(payload)) {
      throw new ApiError(payload, response.status);
    }
    throw new ApiError({ code: "NETWORK_ERROR", message: `Fallo HTTP ${response.status}` }, response.status);
  }
  return payload as T;
}

export async function apiGet<T>(path: string): Promise<T> {
  return apiFetch<T>(path, { method: "GET" });
}
