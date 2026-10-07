import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TestRouter } from "./routes";

describe("router del shell", () => {
  it("la ruta pública renderiza sin login", () => {
    localStorage.clear();
    render(<TestRouter initialPath="/" />);
    expect(screen.getByRole("heading", { name: "Turnos Odontología" })).toBeInTheDocument();
  });

  it("la ruta privada redirige anónimos al login provisorio", () => {
    localStorage.clear();
    render(<TestRouter initialPath="/app" />);
    expect(screen.getByRole("heading", { name: "Ingresar" })).toBeInTheDocument();
  });
});
