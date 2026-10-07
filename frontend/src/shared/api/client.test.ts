import { describe, expect, it, vi, afterEach } from "vitest";

import { ApiError, apiGet } from "./client";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

function mockFetchOnce(status: number, body: unknown): void {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(JSON.stringify(body), {
        status,
        headers: { "Content-Type": "application/json" },
      }),
    ),
  );
}

describe("cliente api", () => {
  it("propaga el code RN-XX-NN del backend en fallos", async () => {
    vi.stubEnv("VITE_API_URL", "http://localhost:8000");
    mockFetchOnce(400, { code: "RN-TU-01", message: "solape" });
    const error = await apiGet("/turnos").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).code).toBe("RN-TU-01");
  });

  it("apunta a la URL base del entorno sin hosts hardcodeados", async () => {
    vi.stubEnv("VITE_API_URL", "http://api-interna:9000");
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "ok" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    await apiGet("/health");
    expect(fetchMock).toHaveBeenCalledOnce();
    const url = String(fetchMock.mock.calls[0]?.[0] ?? "");
    expect(url.startsWith("http://api-interna:9000")).toBe(true);
  });
});
