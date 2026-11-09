import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AppShell } from "./AppShell";
import { clearAuthState, readAuthState, writeAuthState, type UsuarioSesion } from "../../shared/api/auth";

const RECEPCION: UsuarioSesion = {
  id: "u-1",
  tenant_id: "t-1",
  nombre: "Recepción Ficticia",
  email: "recepcion@demo",
  rol: "recepcion",
  es_dueno: false,
};

const DUENO: UsuarioSesion = {
  ...RECEPCION,
  id: "u-2",
  nombre: "Dueña Ficticia",
  rol: "profesional",
  es_dueno: true,
};

function renderShell(usuario: UsuarioSesion): void {
  writeAuthState({ token: "access", usuario });
  render(
    <MemoryRouter initialEntries={["/app"]}>
      <Routes>
        <Route path="/app" element={<AppShell />}>
          <Route index element={<p>Agenda lista</p>} />
        </Route>
        <Route path="/login" element={<p>Login</p>} />
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

describe("shell del panel", () => {
  it("la recepción no ve secciones exclusivas del dueño", () => {
    renderShell(RECEPCION);

    expect(screen.getByRole("link", { name: "Agenda" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Recordatorios" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Reportes" })).toBeNull();
  });

  it("el dueño ve reportes", () => {
    renderShell(DUENO);

    expect(screen.getByRole("link", { name: "Reportes" })).toBeInTheDocument();
  });

  it("el logout invalida la sesión y vuelve al login", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    renderShell(RECEPCION);

    fireEvent.click(screen.getByRole("button", { name: "Cerrar sesión" }));

    expect(await screen.findByText("Login")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "http://api-interna:9000/auth/logout",
      expect.objectContaining({ method: "POST", credentials: "include" }),
    );
    expect(readAuthState().token).toBeNull();
  });
});
