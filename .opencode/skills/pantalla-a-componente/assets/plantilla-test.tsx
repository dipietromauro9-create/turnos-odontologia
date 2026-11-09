// Fuente de diseño: Stitch <projectId>/<screenId> — docs/design/<feature>/<screenId>.html
// Casos base: datos, sobreturno, transiciones válidas, estado terminal. Datos ficticios (R9).

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { TurnoCard, type TurnoVista } from "./TurnoCard";

const TURNO: TurnoVista = {
  id: "turno-1",
  paciente: "Paciente Ficticio",
  profesional: "Dra. Martina",
  prestacion: "Consulta",
  inicio: "2030-06-03T09:00:00-03:00",
  fin: "2030-06-03T09:30:00-03:00",
  estado: "confirmado",
  esSobreturno: false,
};

describe("TurnoCard", () => {
  it("muestra los datos y la etiqueta textual del estado", () => {
    render(<TurnoCard turno={TURNO} />);

    expect(screen.getByText(/Paciente Ficticio/)).toBeInTheDocument();
    expect(screen.getByText("Confirmado")).toBeInTheDocument();
    expect(screen.getByText(/09:00/)).toBeInTheDocument();
  });

  it("marca el sobreturno de forma explícita, no solo por color", () => {
    render(<TurnoCard turno={{ ...TURNO, esSobreturno: true }} />);

    expect(screen.getByText("Sobreturno")).toBeInTheDocument();
  });

  it("solo ofrece las transiciones válidas del estado", () => {
    render(<TurnoCard turno={TURNO} onAccion={vi.fn()} />);

    expect(screen.getByRole("button", { name: "Atender" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Registrar ausencia" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cancelar" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Confirmar" })).toBeNull();
  });

  it("no ofrece acciones en un estado terminal", () => {
    render(<TurnoCard turno={{ ...TURNO, estado: "atendido" }} onAccion={vi.fn()} />);

    expect(screen.queryByRole("button")).toBeNull();
  });

  it("propaga la acción elegida con el turno", () => {
    const onAccion = vi.fn();
    render(<TurnoCard turno={{ ...TURNO, estado: "reservado" }} onAccion={onAccion} />);

    fireEvent.click(screen.getByRole("button", { name: "Confirmar" }));

    expect(onAccion).toHaveBeenCalledWith(
      expect.objectContaining({ id: "turno-1" }),
      "confirmar",
    );
  });
});

// A nivel de página/vista, agregá además:
// - vacío: role="status" con "No hay turnos" (no renderiza tarjetas)
// - cargando: indicador visible y el vacío NO aparece antes de terminar
// - error: muestra el código RN-XX-NN y no deja datos viejos en pantalla
