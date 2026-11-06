import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { MisTurnosPage } from "../../pages/turnero/MisTurnosPage";
import { ApiError } from "../../shared/api/client";
import {
  cancelarTurno,
  getMisTurnos,
  reprogramarTurno,
  type TurnoPublicoOut,
} from "../../shared/api/turneroClient";

vi.mock("../../shared/api/turneroClient", () => ({
  getCatalogo: vi.fn(),
  getDisponibilidad: vi.fn(),
  crearReserva: vi.fn(),
  getMisTurnos: vi.fn(),
  cancelarTurno: vi.fn(),
  reprogramarTurno: vi.fn(),
}));

const TURNO: TurnoPublicoOut = {
  codigo_publico: "ABC123XYZ456",
  inicio: "2030-06-03T09:00:00-03:00",
  fin: "2030-06-03T09:30:00-03:00",
  estado: "reservado",
  profesional: { id: "prof-1", nombre: "Dra. Martina", especialidad: "Ortodoncia" },
  prestacion: { id: "prest-1", nombre: "Consulta", duracion_min: 30, precio_ref: null },
};

async function buscarTurno(): Promise<void> {
  fireEvent.change(screen.getByLabelText(/código de turno/i), {
    target: { value: "ABC123XYZ456" },
  });
  fireEvent.click(screen.getByRole("button", { name: /buscar turno/i }));
  await screen.findByText(/09:00/);
}

beforeEach(() => {
  vi.mocked(getMisTurnos).mockResolvedValue(TURNO);
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("mis turnos", () => {
  it("busca por código y muestra el detalle del turno", async () => {
    render(<MisTurnosPage />);
    await buscarTurno();

    expect(screen.getByText(/Dra. Martina/)).toBeInTheDocument();
    expect(screen.getByText(/Consulta/)).toBeInTheDocument();
    expect(screen.getByText(/Estado: reservado/i)).toBeInTheDocument();
    expect(getMisTurnos).toHaveBeenCalledWith("ABC123XYZ456");
  });

  it("muestra un mensaje cuando el código no existe", async () => {
    vi.mocked(getMisTurnos).mockRejectedValue(
      new ApiError({ code: "RN-TU-06", message: "no existe" }, 404),
    );
    render(<MisTurnosPage />);

    fireEvent.change(screen.getByLabelText(/código de turno/i), {
      target: { value: "NOEXISTE123" },
    });
    fireEvent.click(screen.getByRole("button", { name: /buscar turno/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "No encontramos un turno con ese código.",
    );
  });

  it("cancela con motivo y actualiza la vista a cancelado", async () => {
    vi.mocked(cancelarTurno).mockResolvedValue({ ...TURNO, estado: "cancelado" });
    render(<MisTurnosPage />);
    await buscarTurno();

    fireEvent.click(screen.getByRole("button", { name: /cancelar turno/i }));
    expect(screen.getByRole("dialog", { name: /cancelar turno/i })).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/motivo/i), {
      target: { value: "No puedo asistir" },
    });
    fireEvent.click(screen.getByRole("button", { name: /confirmar cancelación/i }));

    expect(await screen.findByText(/Estado: cancelado/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /cancelar turno/i })).not.toBeInTheDocument();
    expect(cancelarTurno).toHaveBeenCalledWith("ABC123XYZ456", "No puedo asistir");
  });

  it("reprograma a un nuevo horario y actualiza la vista", async () => {
    vi.mocked(reprogramarTurno).mockResolvedValue({
      ...TURNO,
      inicio: "2030-06-03T10:00:00-03:00",
      fin: "2030-06-03T10:30:00-03:00",
    });
    render(<MisTurnosPage />);
    await buscarTurno();

    fireEvent.click(screen.getByRole("button", { name: /reprogramar/i }));
    expect(screen.getByRole("dialog", { name: /reprogramar turno/i })).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/nuevo día y hora/i), {
      target: { value: "2030-06-03T10:00" },
    });
    fireEvent.click(screen.getByRole("button", { name: /confirmar cambio/i }));

    expect(await screen.findByText(/10:00/)).toBeInTheDocument();
    expect(reprogramarTurno).toHaveBeenCalledWith("ABC123XYZ456", expect.any(String));
  });

  it("informa cuando el nuevo horario ya no está disponible", async () => {
    vi.mocked(reprogramarTurno).mockRejectedValue(
      new ApiError({ code: "RN-TU-01", message: "ocupado" }, 409),
    );
    render(<MisTurnosPage />);
    await buscarTurno();

    fireEvent.click(screen.getByRole("button", { name: /reprogramar/i }));
    fireEvent.change(screen.getByLabelText(/nuevo día y hora/i), {
      target: { value: "2030-06-03T10:00" },
    });
    fireEvent.click(screen.getByRole("button", { name: /confirmar cambio/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Ese horario ya no está disponible. Elegí otro.",
    );
  });
});
