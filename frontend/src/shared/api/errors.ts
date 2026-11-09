/** Sobre de error de dominio del backend (RN-GL-01) y su excepción tipada. */

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

export function isDomainEnvelope(payload: unknown): payload is DomainErrorEnvelope {
  if (typeof payload !== "object" || payload === null) return false;
  const record = payload as Record<string, unknown>;
  return typeof record["code"] === "string" && typeof record["message"] === "string";
}

export function leerError(payload: unknown, status: number): ApiError {
  if (isDomainEnvelope(payload)) return new ApiError(payload, status);
  return new ApiError({ code: "NETWORK_ERROR", message: `Fallo HTTP ${status}` }, status);
}
