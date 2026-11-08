import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { RecordatoriosPage } from "./RecordatoriosPage";
import { ApiError } from "../../shared/api/client";
import {
  getRecordatorios,
  marcarEnviado,
  marcarFallido,
  type RecordatorioOut,
} from "../../shared/api/recordatoriosClient";

vi.mock("../../shared/api/recordatoriosClient", () => ({
  getRecordatorios: vi.fn(),
  marcarEnviado: vi.fn(),
  marcarFallido: vi.fn(),
}));

const FILA: RecordatorioOut = {
  id: "rec-1",
  turno_id: "turno-1",
  canal: "whatsapp_manual",
  estado: "pendiente",
  texto: "Hola Paciente Ficticio, te recordamos tu turno con Dra. Martina el 03/06/2030.",
  inicio: "2030-06-03T09:00:00-03:00",
  paciente: "Paciente Ficticio",
  profesional: "Dra. Martina",
  enviado_por: null,
  creado_en: "2030-06-01T09:00:00-03:00",
};

function conPortapapeles(writeText: (texto: string) => Promise<void>): void {
  Object.defineProperty(navigator, "clipboard", {
    value: { writeText },
    configurable: true,
  });
}

beforeEach(() => {
  vi.mocked(getRecordatorios).mockResolvedValue([FILA]);
  conPortapapeles(vi.fn().mockResolvedValue(undefined));
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("cola de recordatorios", () => {
  it("muestra paciente, profesional, fecha y estado", async () => {
    render(<RecordatoriosPage />);

    expect((await screen.findAllByText(/Paciente Ficticio/)).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Dra\. Martina/).length).toBeGreaterThan(0);
    expect(screen.getByText(/lunes, 3 de junio/i)).toBeInTheDocument();
    expect(screen.getByText(/03\/06\/2030/)).toBeInTheDocument();
    expect(screen.getByText(/pendiente/i)).toBeInTheDocument();
  });

  it("copia el texto pre-generado en un clic", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    conPortapapeles(writeText);
    render(<RecordatoriosPage />);

    fireEvent.click(await screen.findByRole("button", { name: /copiar/i }));

    await waitFor(() => expect(writeText).toHaveBeenCalledWith(FILA.texto));
    expect(screen.getByText(/copiado/i)).toBeInTheDocument();
  });

  it("marca enviado, registra el envío y saca el aviso de la cola", async () => {
    vi.mocked(marcarEnviado).mockResolvedValue({ ...FILA, estado: "enviado", enviado_por: "u-1" });
    render(<RecordatoriosPage />);

    fireEvent.click(await screen.findByRole("button", { name: /marcar enviado/i }));

    await waitFor(() => expect(marcarEnviado).toHaveBeenCalledWith("rec-1"));
    expect(await screen.findByText(/no hay recordatorios/i)).toBeInTheDocument();
  });

  it("marca fallido y lo mantiene visible para reintento", async () => {
    vi.mocked(marcarFallido).mockResolvedValue({ ...FILA, estado: "fallido" });
    render(<RecordatoriosPage />);

    fireEvent.click(await screen.findByRole("button", { name: /marcar fallido/i }));

    await waitFor(() => expect(marcarFallido).toHaveBeenCalledWith("rec-1"));
    expect(await screen.findByText("fallido")).toBeInTheDocument();
    expect(screen.getAllByText(/Paciente Ficticio/).length).toBeGreaterThan(0);
  });

  it("muestra el mensaje de la regla cuando el backend rechaza el marcado", async () => {
    vi.mocked(marcarEnviado).mockRejectedValue(
      new ApiError({ code: "RN-CO-03", message: "El recordatorio ya fue enviado" }, 409),
    );
    render(<RecordatoriosPage />);

    fireEvent.click(await screen.findByRole("button", { name: /marcar enviado/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent("ya fue enviado");
  });

  it("muestra un estado vacío explícito", async () => {
    vi.mocked(getRecordatorios).mockResolvedValue([]);
    render(<RecordatoriosPage />);

    expect(await screen.findByText(/no hay recordatorios/i)).toBeInTheDocument();
  });

  it("si el navegador bloquea el portapapeles no rompe la vista", async () => {
    Object.defineProperty(navigator, "clipboard", { value: undefined, configurable: true });
    render(<RecordatoriosPage />);

    fireEvent.click(await screen.findByRole("button", { name: /copiar/i }));

    expect(await screen.findByText(/copiá el texto manualmente/i)).toBeInTheDocument();
  });
});
