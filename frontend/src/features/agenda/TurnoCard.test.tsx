import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { TurnoCard } from "./TurnoCard";
import type { TurnoAgenda } from "../../shared/api/agendaClient";

const TURNO: TurnoAgenda = {
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
};

describe("TurnoCard", () => {
  it("muestra datos, etiqueta textual de estado y hora", () => {
    render(<TurnoCard turno={TURNO} />);

    expect(screen.getByText("Paciente Ficticio")).toBeInTheDocument();
    expect(screen.getByText("Confirmado")).toBeInTheDocument();
    expect(screen.getByText("Consulta")).toBeInTheDocument();
    expect(screen.getByText("09:00–09:30")).toBeInTheDocument();
  });

  it("marca el sobreturno de forma explícita", () => {
    render(<TurnoCard turno={{ ...TURNO, es_sobreturno: true }} />);

    expect(screen.getByText("Sobreturno")).toBeInTheDocument();
  });

  it("solo ofrece las acciones válidas del estado", () => {
    render(<TurnoCard turno={TURNO} onAccion={vi.fn()} />);

    expect(screen.getByRole("button", { name: "Atender" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Registrar ausencia" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cancelar" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Confirmar" })).toBeNull();
  });

  it("un estado terminal no ofrece acciones", () => {
    render(<TurnoCard turno={{ ...TURNO, estado: "atendido" }} onAccion={vi.fn()} />);

    expect(screen.queryByRole("button")).toBeNull();
  });

  it("propaga la acción con el turno", () => {
    const onAccion = vi.fn();
    render(<TurnoCard turno={{ ...TURNO, estado: "reservado" }} onAccion={onAccion} />);

    fireEvent.click(screen.getByRole("button", { name: "Confirmar" }));

    expect(onAccion).toHaveBeenCalledWith(expect.objectContaining({ id: "turno-1" }), "confirmar");
  });
});
