import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ConfiguracionAgenda } from "./ConfiguracionAgenda";
import type { ProfesionalAgenda } from "../../shared/api/agendaClient";
import {
  crearBloqueo,
  crearDisponibilidad,
  eliminarBloqueo,
  eliminarDisponibilidad,
  getBloqueos,
  getDisponibilidad,
} from "../../shared/api/configAgendaClient";

vi.mock("../../shared/api/configAgendaClient", () => ({
  getDisponibilidad: vi.fn(),
  getBloqueos: vi.fn(),
  crearDisponibilidad: vi.fn(),
  eliminarDisponibilidad: vi.fn(),
  crearBloqueo: vi.fn(),
  eliminarBloqueo: vi.fn(),
}));

const PROFESIONAL: ProfesionalAgenda = {
  id: "prof-1",
  nombre: "Dra. Martina",
  especialidad: "Odontopediatría",
  activo: true,
};

beforeEach(() => {
  vi.mocked(getDisponibilidad).mockResolvedValue([
    {
      id: "disp-1",
      profesional_id: "prof-1",
      dia_semana: 0,
      hora_desde: "09:00:00",
      hora_hasta: "13:00:00",
    },
  ]);
  vi.mocked(getBloqueos).mockResolvedValue([
    {
      id: "bloq-1",
      profesional_id: null,
      desde: "2030-06-03T12:00:00-03:00",
      hasta: "2030-06-03T13:00:00-03:00",
      motivo: "Cierre ficticio",
    },
  ]);
  vi.mocked(crearDisponibilidad).mockResolvedValue({
    id: "disp-2",
    profesional_id: "prof-1",
    dia_semana: 0,
    hora_desde: "14:00:00",
    hora_hasta: "18:00:00",
  });
  vi.mocked(crearBloqueo).mockResolvedValue({
    id: "bloq-2",
    profesional_id: null,
    desde: "2030-06-04T09:00:00-03:00",
    hasta: "2030-06-04T10:00:00-03:00",
    motivo: "Feriado ficticio",
  });
  vi.mocked(eliminarDisponibilidad).mockResolvedValue(undefined);
  vi.mocked(eliminarBloqueo).mockResolvedValue(undefined);
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("configuración de agenda del dueño", () => {
  it("lista la plantilla y los bloqueos existentes", async () => {
    render(<ConfiguracionAgenda profesionales={[PROFESIONAL]} />);

    expect(await screen.findByText(/Lunes 09:00–13:00/)).toBeInTheDocument();
    expect(screen.getByText(/Cierre ficticio/)).toBeInTheDocument();
  });

  it("agrega una franja semanal", async () => {
    render(<ConfiguracionAgenda profesionales={[PROFESIONAL]} />);
    await screen.findByText(/Lunes 09:00–13:00/);

    fireEvent.change(screen.getByLabelText("Profesional de la franja"), {
      target: { value: "prof-1" },
    });
    fireEvent.change(screen.getByLabelText("Hora desde"), { target: { value: "14:00" } });
    fireEvent.change(screen.getByLabelText("Hora hasta"), { target: { value: "18:00" } });
    fireEvent.click(screen.getByRole("button", { name: "Agregar franja" }));

    await waitFor(() =>
      expect(crearDisponibilidad).toHaveBeenCalledWith({
        profesional_id: "prof-1",
        dia_semana: 0,
        hora_desde: "14:00:00",
        hora_hasta: "18:00:00",
      }),
    );
  });

  it("agrega un bloqueo global con offset del consultorio", async () => {
    render(<ConfiguracionAgenda profesionales={[PROFESIONAL]} />);
    await screen.findByText(/Cierre ficticio/);

    fireEvent.change(screen.getByLabelText("Desde"), {
      target: { value: "2030-06-04T09:00" },
    });
    fireEvent.change(screen.getByLabelText("Hasta"), {
      target: { value: "2030-06-04T10:00" },
    });
    fireEvent.change(screen.getByLabelText("Motivo"), {
      target: { value: "Feriado ficticio" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Agregar bloqueo" }));

    await waitFor(() =>
      expect(crearBloqueo).toHaveBeenCalledWith({
        profesional_id: null,
        desde: "2030-06-04T09:00:00-03:00",
        hasta: "2030-06-04T10:00:00-03:00",
        motivo: "Feriado ficticio",
      }),
    );
  });

  it("elimina una franja y un bloqueo", async () => {
    render(<ConfiguracionAgenda profesionales={[PROFESIONAL]} />);
    await screen.findByText(/Cierre ficticio/);

    fireEvent.click(screen.getByRole("button", { name: "Eliminar franja" }));
    fireEvent.click(screen.getByRole("button", { name: "Eliminar bloqueo" }));

    await waitFor(() => {
      expect(eliminarDisponibilidad).toHaveBeenCalledWith("disp-1");
      expect(eliminarBloqueo).toHaveBeenCalledWith("bloq-1");
    });
  });
});
