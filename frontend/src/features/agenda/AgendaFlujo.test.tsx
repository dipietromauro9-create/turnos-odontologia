import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { TestRouter } from "../../routes";
import { clearAuthState } from "../../shared/api/auth";
import type { AgendaOut } from "../../shared/api/agendaClient";
import { accionTurno, crearTurno } from "../../shared/api/turnosClient";
import { buscarPacientes } from "../../shared/api/pacientesClient";
import { getAgendaDia, getAgendaSemana } from "../../shared/api/agendaClient";

vi.mock("../../shared/api/agendaClient", () => ({
  getAgendaDia: vi.fn(),
  getAgendaSemana: vi.fn(),
}));
vi.mock("../../shared/api/turnosClient", () => ({
  accionTurno: vi.fn(),
  crearTurno: vi.fn(),
  getHuecos: vi.fn(),
}));
vi.mock("../../shared/api/pacientesClient", () => ({ buscarPacientes: vi.fn() }));
vi.mock("../../shared/api/configAgendaClient", () => ({
  getDisponibilidad: vi.fn().mockResolvedValue([]),
  getBloqueos: vi.fn().mockResolvedValue([]),
  crearDisponibilidad: vi.fn(),
  eliminarDisponibilidad: vi.fn(),
  crearBloqueo: vi.fn(),
  eliminarBloqueo: vi.fn(),
}));

const AGENDA: AgendaOut = {
  rango: { desde: "2030-06-03T00:00:00-03:00", hasta: "2030-06-10T00:00:00-03:00" },
  profesionales: [
    { id: "prof-1", nombre: "Dra. Martina", especialidad: "Odontopediatría", activo: true },
  ],
  prestaciones: [{ id: "prest-1", nombre: "Consulta", duracion_min: 30 }],
  turnos: [
    {
      id: "turno-1",
      profesional_id: "prof-1",
      inicio: "2030-06-03T09:00:00-03:00",
      fin: "2030-06-03T09:30:00-03:00",
      estado: "confirmado",
      es_sobreturno: false,
      motivo_sobreturno: null,
      motivo_cancelacion: null,
      paciente: { id: "pac-1", nombre: "Paciente Ficticio" },
      prestacion: { id: "prest-1", nombre: "Consulta", duracion_min: 30 },
    },
  ],
  bloqueos: [],
};

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

beforeEach(() => {
  clearAuthState();
  vi.stubEnv("VITE_API_URL", "http://api-interna:9000");
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValueOnce(json(200, { access_token: "access-1" }))
      .mockResolvedValueOnce(
        json(200, {
          id: "u-1",
          tenant_id: "t-1",
          nombre: "Recepción Ficticia",
          email: "recepcion@demo",
          rol: "recepcion",
          es_dueno: false,
        }),
      ),
  );
  vi.mocked(getAgendaDia).mockResolvedValue(AGENDA);
  vi.mocked(getAgendaSemana).mockResolvedValue(AGENDA);
  vi.mocked(buscarPacientes).mockResolvedValue([
    { id: "pac-1", nombre: "Paciente Ficticio", telefono: "1145550001" },
  ]);
  vi.mocked(crearTurno).mockResolvedValue({
    id: "turno-2",
    inicio: "2030-06-03T10:00:00-03:00",
    fin: "2030-06-03T10:30:00-03:00",
    estado: "reservado",
    es_sobreturno: false,
  });
  vi.mocked(accionTurno).mockResolvedValue({
    id: "turno-1",
    inicio: "2030-06-03T09:00:00-03:00",
    fin: "2030-06-03T09:30:00-03:00",
    estado: "atendido",
    es_sobreturno: false,
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  vi.clearAllMocks();
  clearAuthState();
});

describe("flujo completo del panel", () => {
  it("login → agenda → alta de turno → confirmar/atender", async () => {
    render(<TestRouter initialPath="/login" />);

    fireEvent.change(screen.getByLabelText(/Email/i), {
      target: { value: "recepcion@demo" },
    });
    fireEvent.change(screen.getByLabelText(/Contraseña/i), {
      target: { value: "clave-ficticia" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Ingresar" }));

    expect(await screen.findByRole("heading", { name: "Dra. Martina" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Nuevo turno" }));
    const modal = screen.getByRole("dialog");
    fireEvent.change(within(modal).getByLabelText(/Buscar por nombre o teléfono/i), {
      target: { value: "Paciente" },
    });
    fireEvent.click(within(modal).getByRole("button", { name: "Buscar paciente" }));
    fireEvent.click(await within(modal).findByRole("button", { name: /Paciente Ficticio/ }));
    fireEvent.change(within(modal).getByLabelText(/^Profesional/i), {
      target: { value: "prof-1" },
    });
    fireEvent.change(within(modal).getByLabelText(/Prestación/i), {
      target: { value: "prest-1" },
    });
    fireEvent.change(within(modal).getByLabelText("Hora"), { target: { value: "10:00" } });
    fireEvent.click(within(modal).getByRole("button", { name: "Crear turno" }));

    await waitFor(() => expect(crearTurno).toHaveBeenCalledTimes(1));
    const alta = vi.mocked(crearTurno).mock.calls[0]?.[0];
    expect(alta).toMatchObject({
      profesional_id: "prof-1",
      paciente_id: "pac-1",
      prestacion_id: "prest-1",
      es_sobreturno: false,
    });
    expect(alta?.inicio).toContain("T10:00:00-03:00");
    expect(alta).not.toHaveProperty("fin");

    fireEvent.click(await screen.findByRole("button", { name: "Atender" }));
    await waitFor(() =>
      expect(accionTurno).toHaveBeenCalledWith("turno-1", "atender"),
    );
  });
});
