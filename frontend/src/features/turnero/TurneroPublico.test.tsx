import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { TestRouter } from "../../routes";
import { ApiError } from "../../shared/api/client";
import {
  crearReserva,
  getCatalogo,
  getDisponibilidad,
  type CatalogoPublico,
  type HuecoPublico,
} from "../../shared/api/turneroClient";

vi.mock("../../shared/api/turneroClient", () => ({
  getCatalogo: vi.fn(),
  getDisponibilidad: vi.fn(),
  crearReserva: vi.fn(),
  getMisTurnos: vi.fn(),
  cancelarTurno: vi.fn(),
  reprogramarTurno: vi.fn(),
}));

const CATALOGO: CatalogoPublico = {
  consultorio: { nombre: "Consultorio Sonrisas", slug: "demo" },
  profesionales: [{ id: "prof-1", nombre: "Dra. Martina", especialidad: "Ortodoncia" }],
  prestaciones: [
    { id: "prest-1", nombre: "Consulta", duracion_min: 30, precio_ref: null },
  ],
};

const HUECOS: readonly HuecoPublico[] = [
  {
    inicio: "2030-06-03T09:30:00-03:00",
    fin: "2030-06-03T10:00:00-03:00",
    profesional_id: "prof-1",
    prestacion_id: "prest-1",
  },
  {
    inicio: "2030-06-04T10:00:00-03:00",
    fin: "2030-06-04T10:30:00-03:00",
    profesional_id: "prof-1",
    prestacion_id: "prest-1",
  },
];

function preparar(): void {
  vi.mocked(getCatalogo).mockResolvedValue(CATALOGO);
  vi.mocked(getDisponibilidad).mockResolvedValue(HUECOS);
}

afterEach(() => {
  vi.clearAllMocks();
});

describe("turnero público", () => {
  it("muestra la semana y los huecos libres agrupados por día", async () => {
    preparar();
    render(<TestRouter initialPath="/turnero/demo" />);

    expect(await screen.findByRole("button", { name: "09:30" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "10:00" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: /navegación de semana/i })).toBeInTheDocument();
  });

  it("navega a la semana anterior y vuelve a pedir disponibilidad", async () => {
    preparar();
    render(<TestRouter initialPath="/turnero/demo" />);
    await screen.findByRole("button", { name: "09:30" });

    fireEvent.click(screen.getByRole("button", { name: /semana anterior/i }));

    await waitFor(() => expect(getDisponibilidad).toHaveBeenCalledTimes(2));
  });

  it("abre el modal de reserva y muestra el código al confirmar", async () => {
    preparar();
    vi.mocked(crearReserva).mockResolvedValue({
      codigo_publico: "ABC123XYZ456",
      inicio: "2030-06-03T09:30:00-03:00",
      fin: "2030-06-03T10:00:00-03:00",
      estado: "reservado",
      profesional_id: "prof-1",
      prestacion_id: "prest-1",
      duplicado_advertencia: false,
    });
    render(<TestRouter initialPath="/turnero/demo" />);

    fireEvent.click(await screen.findByRole("button", { name: "09:30" }));
    expect(screen.getByRole("dialog", { name: /confirmar reserva/i })).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/nombre y apellido/i), {
      target: { value: "Ana Ficticia" },
    });
    fireEvent.change(screen.getByLabelText(/teléfono/i), {
      target: { value: "1155550001" },
    });
    fireEvent.click(screen.getByRole("button", { name: /confirmar reserva/i }));

    expect(await screen.findByText("ABC123XYZ456")).toBeInTheDocument();
    expect(crearReserva).toHaveBeenCalledWith(
      "demo",
      expect.objectContaining({ nombre: "Ana Ficticia", telefono: "1155550001" }),
    );
  });

  it("muestra un mensaje amigable cuando el horario se ocupó (409)", async () => {
    preparar();
    vi.mocked(crearReserva).mockRejectedValue(
      new ApiError({ code: "RN-TU-01", message: "ocupado" }, 409),
    );
    render(<TestRouter initialPath="/turnero/demo" />);

    fireEvent.click(await screen.findByRole("button", { name: "09:30" }));
    fireEvent.change(screen.getByLabelText(/nombre y apellido/i), {
      target: { value: "Ana Ficticia" },
    });
    fireEvent.change(screen.getByLabelText(/teléfono/i), {
      target: { value: "1155550001" },
    });
    fireEvent.click(screen.getByRole("button", { name: /confirmar reserva/i }));

    expect(
      await screen.findByRole("alert"),
    ).toHaveTextContent("Ese horario acaba de ocuparse. Elegí otro.");
  });

  it("muestra el estado de carga mientras consulta disponibilidad", async () => {
    vi.mocked(getCatalogo).mockResolvedValue(CATALOGO);
    vi.mocked(getDisponibilidad).mockReturnValue(new Promise(() => undefined));

    render(<TestRouter initialPath="/turnero/demo" />);

    expect(await screen.findByText(/cargando disponibilidad/i)).toBeInTheDocument();
  });

  it("copia el código de la reserva al portapapeles", async () => {
    preparar();
    vi.mocked(crearReserva).mockResolvedValue({
      codigo_publico: "ABC123XYZ456",
      inicio: "2030-06-03T09:30:00-03:00",
      fin: "2030-06-03T10:00:00-03:00",
      estado: "reservado",
      profesional_id: "prof-1",
      prestacion_id: "prest-1",
      duplicado_advertencia: false,
    });
    const escribir = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText: escribir },
      configurable: true,
    });

    render(<TestRouter initialPath="/turnero/demo" />);
    fireEvent.click(await screen.findByRole("button", { name: "09:30" }));
    fireEvent.change(screen.getByLabelText(/nombre y apellido/i), {
      target: { value: "Ana Ficticia" },
    });
    fireEvent.change(screen.getByLabelText(/teléfono/i), {
      target: { value: "1155550001" },
    });
    fireEvent.click(screen.getByRole("button", { name: /confirmar reserva/i }));
    await screen.findByText("ABC123XYZ456");

    fireEvent.click(screen.getByRole("button", { name: /copiar código/i }));

    expect(await screen.findByText("Código copiado")).toBeInTheDocument();
    expect(escribir).toHaveBeenCalledWith("ABC123XYZ456");
  });
});
