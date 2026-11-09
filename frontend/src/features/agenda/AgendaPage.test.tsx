import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AgendaPage } from "./AgendaPage";
import { ApiError } from "../../shared/api/client";
import { clearAuthState, writeAuthState, type UsuarioSesion } from "../../shared/api/auth";
import type { AgendaOut } from "../../shared/api/agendaClient";
import { accionTurno } from "../../shared/api/turnosClient";
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

const RECEPCION: UsuarioSesion = {
  id: "u-1",
  tenant_id: "t-1",
  nombre: "Recepción Ficticia",
  email: "recepcion@demo",
  rol: "recepcion",
  es_dueno: false,
};

const PROFESIONAL: UsuarioSesion = {
  ...RECEPCION,
  id: "u-2",
  nombre: "Profesional Ficticio",
  rol: "profesional",
  es_dueno: false,
};

const DUENO: UsuarioSesion = { ...PROFESIONAL, nombre: "Dueña Ficticia", es_dueno: true };

const AGENDA: AgendaOut = {
  rango: {
    desde: "2030-06-03T00:00:00-03:00",
    hasta: "2030-06-10T00:00:00-03:00",
  },
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

beforeEach(() => {
  clearAuthState();
  writeAuthState({ token: "access", usuario: RECEPCION });
  vi.mocked(getAgendaDia).mockResolvedValue(AGENDA);
  vi.mocked(getAgendaSemana).mockResolvedValue(AGENDA);
  vi.mocked(accionTurno).mockResolvedValue({
    id: "turno-1",
    inicio: "2030-06-03T09:00:00-03:00",
    fin: "2030-06-03T09:30:00-03:00",
    estado: "atendido",
    es_sobreturno: false,
  });
});

afterEach(() => {
  vi.clearAllMocks();
  clearAuthState();
});

describe("agenda interna", () => {
  it("muestra la columna, la tarjeta y la etiqueta textual del estado", async () => {
    render(<AgendaPage />);

    expect(await screen.findByRole("heading", { name: "Dra. Martina" })).toBeInTheDocument();
    expect(screen.getByText("Paciente Ficticio")).toBeInTheDocument();
    expect(screen.getByText("Confirmado")).toBeInTheDocument();
    expect(screen.getByText("09:00–09:30")).toBeInTheDocument();
  });

  it("muestra el estado vacío cuando no hay turnos", async () => {
    vi.mocked(getAgendaSemana).mockResolvedValue({ ...AGENDA, turnos: [] });
    render(<AgendaPage />);

    expect(await screen.findByText("No hay turnos en el período.")).toBeInTheDocument();
    expect(screen.getAllByText("Sin turnos").length).toBeGreaterThan(0);
  });

  it("muestra el error con su código RN", async () => {
    vi.mocked(getAgendaSemana).mockRejectedValue(
      new ApiError({ code: "RN-AG-01", message: "El profesional no existe" }, 404),
    );
    render(<AgendaPage />);

    const alerta = await screen.findByRole("alert");
    expect(alerta).toHaveTextContent("RN-AG-01");
  });

  it("la recepción ve el selector de profesional", async () => {
    render(<AgendaPage />);
    await screen.findByRole("heading", { name: "Dra. Martina" });

    expect(screen.getByLabelText("Profesional")).toBeInTheDocument();
  });

  it("el profesional sin flag no ve el selector de otros profesionales", async () => {
    writeAuthState({ token: "access", usuario: PROFESIONAL });
    render(<AgendaPage />);
    await screen.findByRole("heading", { name: "Dra. Martina" });

    expect(screen.queryByLabelText("Profesional")).toBeNull();
  });

  it("muestra configuración de agenda solo al dueño", async () => {
    writeAuthState({ token: "access", usuario: DUENO });
    const { unmount } = render(<AgendaPage />);
    expect(
      await screen.findByRole("region", { name: "Configuración de agenda" }),
    ).toBeInTheDocument();
    unmount();

    writeAuthState({ token: "access", usuario: RECEPCION });
    render(<AgendaPage />);
    await screen.findByRole("heading", { name: "Dra. Martina" });
    expect(screen.queryByRole("region", { name: "Configuración de agenda" })).toBeNull();
  });

  it("ante un 422 RN-TU-04 muestra el código y recarga la agenda", async () => {
    vi.mocked(accionTurno).mockRejectedValue(
      new ApiError({ code: "RN-TU-04", message: "Transición inválida" }, 422),
    );
    render(<AgendaPage />);
    await screen.findByRole("heading", { name: "Dra. Martina" });

    fireEvent.click(screen.getByRole("button", { name: "Atender" }));

    const alerta = await screen.findByRole("alert");
    expect(alerta).toHaveTextContent("RN-TU-04");
    await waitFor(() => expect(getAgendaSemana).toHaveBeenCalledTimes(2));
  });
});
