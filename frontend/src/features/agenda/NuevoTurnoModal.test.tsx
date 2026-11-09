import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { NuevoTurnoModal } from "./NuevoTurnoModal";
import { ApiError } from "../../shared/api/client";
import type { PrestacionAgenda, ProfesionalAgenda } from "../../shared/api/agendaClient";
import { buscarPacientes } from "../../shared/api/pacientesClient";
import { crearTurno, getHuecos } from "../../shared/api/turnosClient";

vi.mock("../../shared/api/pacientesClient", () => ({ buscarPacientes: vi.fn() }));
vi.mock("../../shared/api/turnosClient", () => ({
  crearTurno: vi.fn(),
  getHuecos: vi.fn(),
  accionTurno: vi.fn(),
}));

const PROFESIONAL: ProfesionalAgenda = {
  id: "prof-1",
  nombre: "Dra. Martina",
  especialidad: "Odontopediatría",
  activo: true,
};

const PRESTACION: PrestacionAgenda = {
  id: "prest-1",
  nombre: "Consulta",
  duracion_min: 30,
};

const PACIENTE = { id: "pac-1", nombre: "Paciente Ficticio", telefono: "1145550001" };

function renderModal(onCreado = vi.fn()): { onCreado: ReturnType<typeof vi.fn> } {
  render(
    <NuevoTurnoModal
      abierto
      onCerrar={vi.fn()}
      onCreado={onCreado}
      profesionales={[PROFESIONAL]}
      prestaciones={[PRESTACION]}
      puedeElegirProfesional
      fechaInicial="2030-06-03"
    />,
  );
  return { onCreado };
}

async function elegirPacienteYHorario(): Promise<void> {
  fireEvent.change(screen.getByLabelText(/Buscar por nombre o teléfono/i), {
    target: { value: "Paciente" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Buscar paciente" }));
  const resultado = await screen.findByRole("button", { name: /Paciente Ficticio/ });
  fireEvent.click(resultado);
  fireEvent.change(screen.getByLabelText(/^Profesional/i), { target: { value: "prof-1" } });
  fireEvent.change(screen.getByLabelText(/Prestación/i), { target: { value: "prest-1" } });
  fireEvent.change(screen.getByLabelText("Hora"), { target: { value: "10:30" } });
}

beforeEach(() => {
  vi.mocked(buscarPacientes).mockResolvedValue([PACIENTE]);
  vi.mocked(crearTurno).mockResolvedValue({
    id: "turno-1",
    inicio: "2030-06-03T10:30:00-03:00",
    fin: "2030-06-03T11:00:00-03:00",
    estado: "reservado",
    es_sobreturno: false,
  });
  vi.mocked(getHuecos).mockResolvedValue([]);
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("alta interna de turno", () => {
  it("crea un turno normal sin enviar `fin` y avisa al padre", async () => {
    const { onCreado } = renderModal();
    await elegirPacienteYHorario();

    fireEvent.click(screen.getByRole("button", { name: "Crear turno" }));

    await waitFor(() => expect(onCreado).toHaveBeenCalled());
    expect(crearTurno).toHaveBeenCalledWith({
      profesional_id: "prof-1",
      paciente_id: "pac-1",
      prestacion_id: "prest-1",
      inicio: "2030-06-03T10:30:00-03:00",
      es_sobreturno: false,
      motivo_sobreturno: undefined,
    });
    expect(vi.mocked(crearTurno).mock.calls[0]?.[0]).not.toHaveProperty("fin");
  });

  it("exige motivo cuando es sobreturno", async () => {
    renderModal();
    await elegirPacienteYHorario();
    fireEvent.click(screen.getByRole("checkbox", { name: "Sobreturno" }));

    fireEvent.click(screen.getByRole("button", { name: "Crear turno" }));

    expect(
      await screen.findByText("El sobreturno requiere un motivo de urgencia."),
    ).toBeInTheDocument();
    expect(crearTurno).not.toHaveBeenCalled();
  });

  it("muestra el código RN-TU-01 cuando el backend rechaza por solape", async () => {
    vi.mocked(crearTurno).mockRejectedValue(
      new ApiError({ code: "RN-TU-01", message: "Turno superpuesto" }, 409),
    );
    renderModal();
    await elegirPacienteYHorario();

    fireEvent.click(screen.getByRole("button", { name: "Crear turno" }));

    const alerta = await screen.findByRole("alert");
    expect(alerta).toHaveTextContent("RN-TU-01");
  });

  it("ofrece los huecos del motor y completa la hora", async () => {
    vi.mocked(getHuecos).mockResolvedValue([
      {
        inicio: "2030-06-03T10:00:00-03:00",
        fin: "2030-06-03T10:30:00-03:00",
        profesional_id: "prof-1",
        prestacion_id: "prest-1",
      },
    ]);
    renderModal();
    fireEvent.change(screen.getByLabelText(/^Profesional/i), { target: { value: "prof-1" } });
    fireEvent.change(screen.getByLabelText(/Prestación/i), { target: { value: "prest-1" } });

    fireEvent.click(screen.getByRole("button", { name: "Ver horarios" }));

    const horario = await screen.findByRole("button", { name: "10:00" });
    fireEvent.click(horario);
    expect(screen.getByLabelText("Hora")).toHaveValue("10:00");
    expect(getHuecos).toHaveBeenCalledWith(
      "prof-1",
      "prest-1",
      "2030-06-03T00:00:00-03:00",
      "2030-06-04T00:00:00-03:00",
    );
  });
});
