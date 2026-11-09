import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { LoginPage } from "./LoginPage";
import { clearAuthState, readAuthState } from "../../shared/api/auth";

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function renderLogin(): void {
  render(
    <MemoryRouter initialEntries={["/login"]}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/app" element={<p>Panel listo</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  clearAuthState();
  vi.stubEnv("VITE_API_URL", "http://api-interna:9000");
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  clearAuthState();
});

describe("login del panel", () => {
  it("guarda el access y la identidad y entra al panel", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(json(200, { access_token: "access-1", token_type: "bearer", expires_in: 900 }))
      .mockResolvedValueOnce(
        json(200, {
          id: "u-1",
          tenant_id: "t-1",
          nombre: "Recepción Ficticia",
          email: "recepcion@demo",
          rol: "recepcion",
          es_dueno: false,
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    renderLogin();
    fireEvent.change(screen.getByLabelText(/Email/i), {
      target: { value: "recepcion@demo" },
    });
    fireEvent.change(screen.getByLabelText(/Contraseña/i), {
      target: { value: "clave-ficticia" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Ingresar" }));

    expect(await screen.findByText("Panel listo")).toBeInTheDocument();
    expect(readAuthState().token).toBe("access-1");
    expect(readAuthState().usuario?.rol).toBe("recepcion");
  });

  it("muestra el código de regla y no intenta refresh con credenciales inválidas", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        json(401, { code: "RN-AU-01", message: "Credenciales inválidas" }),
      );
    vi.stubGlobal("fetch", fetchMock);

    renderLogin();
    fireEvent.change(screen.getByLabelText(/Email/i), { target: { value: "mal@demo" } });
    fireEvent.change(screen.getByLabelText(/Contraseña/i), { target: { value: "mal" } });
    fireEvent.click(screen.getByRole("button", { name: "Ingresar" }));

    const alerta = await screen.findByRole("alert");
    expect(alerta).toHaveTextContent("RN-AU-01");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(readAuthState().token).toBeNull();
  });
});
