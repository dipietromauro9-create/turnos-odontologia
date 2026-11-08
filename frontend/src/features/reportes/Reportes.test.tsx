import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ReportesPage } from "./ReportesPage";
import { ApiError } from "../../shared/api/client";
import {
  crearExport,
  descargarExport,
  getAusencias,
  getExport,
  getOcupacion,
  getRecordatorios,
  reintentarExport,
  type ExportacionOut,
} from "../../shared/api/reportesClient";

vi.mock("../../shared/api/reportesClient", () => ({
  getOcupacion: vi.fn(),
  getAusencias: vi.fn(),
  getRecordatorios: vi.fn(),
  crearExport: vi.fn(),
  getExport: vi.fn(),
  reintentarExport: vi.fn(),
  descargarExport: vi.fn(),
}));

const OCUPACION = [
  {
    profesional_id: "p1",
    nombre: "Dra. Martina",
    turnos_activos: 2,
    minutos_disponibles: 240,
    minutos_ocupados: 60,
    ocupacion: 0.25,
  },
];
const AUSENCIAS = [
  {
    profesional_id: "p1",
    nombre: "Dra. Martina",
    atendidos: 3,
    ausentes: 1,
    tasa_ausencia: 0.25,
  },
];
const RECORDATORIOS = [
  {
    profesional_id: "p1",
    nombre: "Dra. Martina",
    turnos_confirmados: 4,
    recordatorios_enviados: 3,
    ratio: 0.75,
  },
];

const PENDIENTE: ExportacionOut = {
  id: "e1",
  tipo: "turnos",
  estado: "pendiente",
  desde: null,
  hasta: null,
  error: null,
  creado_en: "2030-06-01T00:00:00-03:00",
  descarga_url: null,
};

beforeEach(() => {
  vi.mocked(getOcupacion).mockResolvedValue(OCUPACION);
  vi.mocked(getAusencias).mockResolvedValue(AUSENCIAS);
  vi.mocked(getRecordatorios).mockResolvedValue(RECORDATORIOS);
  vi.mocked(crearExport).mockResolvedValue(PENDIENTE);
  vi.mocked(getExport).mockResolvedValue({ ...PENDIENTE, estado: "listo", descarga_url: "/export/e1/archivo" });
  vi.mocked(reintentarExport).mockResolvedValue(PENDIENTE);
  vi.mocked(descargarExport).mockResolvedValue(new Blob(["csv"], { type: "text/csv" }));
  Object.defineProperty(URL, "createObjectURL", { value: vi.fn(() => "blob:ficticio"), configurable: true });
  Object.defineProperty(URL, "revokeObjectURL", { value: vi.fn(), configurable: true });
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("reportes", () => {
  it("muestra ocupación, ausencias e IN-03", async () => {
    render(<ReportesPage intervaloPollMs={1} />);

    expect((await screen.findAllByText(/Dra\. Martina/)).length).toBeGreaterThan(0);
    expect(screen.getAllByText("25%").length).toBeGreaterThan(0);
    expect(screen.getByText(/75%/)).toBeInTheDocument();
    expect(getOcupacion).toHaveBeenCalledOnce();
    expect(getAusencias).toHaveBeenCalledOnce();
    expect(getRecordatorios).toHaveBeenCalledOnce();
  });

  it("vuelve a pedir los reportes al cambiar el período", async () => {
    render(<ReportesPage intervaloPollMs={1} />);
    await screen.findAllByText(/Dra\. Martina/);

    fireEvent.change(screen.getByLabelText(/desde/i), { target: { value: "2030-05-01" } });

    await waitFor(() => expect(getOcupacion).toHaveBeenCalledTimes(2));
  });

  it("exporta, consulta el estado y ofrece la descarga", async () => {
    render(<ReportesPage intervaloPollMs={1} />);
    await screen.findAllByText(/Dra\. Martina/);

    fireEvent.click(screen.getByRole("button", { name: /exportar turnos/i }));

    await waitFor(() => expect(crearExport).toHaveBeenCalledWith("turnos", expect.anything()));
    const descargar = await screen.findByRole("button", { name: /descargar/i });
    fireEvent.click(descargar);

    await waitFor(() => expect(descargarExport).toHaveBeenCalledWith("e1"));
  });

  it("muestra el error de un export fallido y permite reintentar", async () => {
    vi.mocked(crearExport).mockResolvedValue({
      ...PENDIENTE,
      estado: "fallido",
      error: "falla ficticia",
    });
    render(<ReportesPage intervaloPollMs={1} />);
    await screen.findAllByText(/Dra\. Martina/);

    fireEvent.click(screen.getByRole("button", { name: /exportar turnos/i }));

    expect(await screen.findByText(/falla ficticia/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /reintentar/i }));
    await waitFor(() => expect(reintentarExport).toHaveBeenCalledWith("e1"));
  });

  it("muestra un estado vacío cuando no hay datos", async () => {
    vi.mocked(getOcupacion).mockResolvedValue([]);
    vi.mocked(getAusencias).mockResolvedValue([]);
    vi.mocked(getRecordatorios).mockResolvedValue([]);
    render(<ReportesPage intervaloPollMs={1} />);

    expect(await screen.findByText(/sin datos en el período/i)).toBeInTheDocument();
  });

  it("muestra el error de red al pedir reportes", async () => {
    vi.mocked(getOcupacion).mockRejectedValue(
      new ApiError({ code: "RN-RP-01", message: "rango inválido" }, 422),
    );
    render(<ReportesPage intervaloPollMs={1} />);

    expect(await screen.findByRole("alert")).toHaveTextContent("rango inválido");
  });

  it("deja de consultar el export después del máximo de intentos", async () => {
    vi.mocked(getExport).mockResolvedValue({ ...PENDIENTE, estado: "procesando" });
    render(<ReportesPage intervaloPollMs={1} />);
    await screen.findAllByText(/Dra\. Martina/);

    fireEvent.click(screen.getByRole("button", { name: /exportar turnos/i }));

    await waitFor(() => expect(getExport).toHaveBeenCalledTimes(60), { timeout: 5000 });
    expect(screen.getByText(/seguimos procesando/i)).toBeInTheDocument();
  });
});
