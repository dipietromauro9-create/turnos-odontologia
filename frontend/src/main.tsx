import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { AppRoutes } from "./routes";
import "./shared/styles/panel.css";
import "./shared/styles/publico.css";

const rootElement = document.getElementById("root");
if (rootElement === null) {
  throw new Error("Falta el elemento #root en index.html");
}

createRoot(rootElement).render(
  <StrictMode>
    <AppRoutes />
  </StrictMode>,
);
