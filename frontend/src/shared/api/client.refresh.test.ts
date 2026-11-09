import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiGet } from "./client";
import { clearAuthState, readAuthState, writeAuthState } from "./auth";

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const USUARIO = {
  id: "u-1",
  tenant_id: "t-1",
  nombre: "Recepción Ficticia",
  email: "recepcion@demo",
  rol: "recepcion" as const,
  es_dueno: false,
};

beforeEach(() => {
  clearAuthState();
  writeAuthState({ token: "viejo", usuario: USUARIO });
  vi.stubEnv("VITE_API_URL", "http://api-interna:9000");
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  clearAuthState();
});

describe("cliente api con refresh", () => {
  it("refresca una sola vez y repite la request original", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(json(401, { code: "RN-AU-01", message: "vencido" }))
      .mockResolvedValueOnce(json(200, { access_token: "nuevo" }))
      .mockResolvedValueOnce(json(200, { ok: true }));
    vi.stubGlobal("fetch", fetchMock);

    const respuesta = await apiGet<{ ok: boolean }>("/turnos");

    expect(respuesta.ok).toBe(true);
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(String(fetchMock.mock.calls[1]?.[0])).toContain("/auth/refresh");
    const reintento = fetchMock.mock.calls[2]?.[1] as RequestInit;
    expect((reintento.headers as Record<string, string>)["Authorization"]).toBe("Bearer nuevo");
    expect(readAuthState().token).toBe("nuevo");
  });

  it("si el refresh falla limpia la sesión y propaga el 401", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(json(401, { code: "RN-AU-01", message: "vencido" }))
      .mockResolvedValueOnce(json(401, { code: "RN-AU-01", message: "refresh inválido" }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(apiGet("/turnos")).rejects.toMatchObject({ status: 401 });

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(readAuthState().token).toBeNull();
  });

  it("no intenta refrescar una ruta de auth", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(json(401, { code: "RN-AU-01", message: "credenciales" }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      apiGet("/auth/login").then(
        () => null,
        (error: unknown) => error,
      ),
    ).resolves.toMatchObject({ code: "RN-AU-01" });

    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
