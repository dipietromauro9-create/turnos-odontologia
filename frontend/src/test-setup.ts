import "@testing-library/jest-dom/vitest";
import { JSDOM } from "jsdom";

/**
 * Shim de test-env solamente: Node ≥22 expone un `localStorage` global
 * experimental (undefined sin flag) que oculta el de jsdom porque vitest no
 * lo incluye en su lista de claves a poblar. En navegadores reales existe
 * siempre, así que acá reinstalamos el Storage real de jsdom.
 */
function localStorageRoto(): boolean {
  try {
    return typeof globalThis.localStorage === "undefined" || globalThis.localStorage === null;
  } catch {
    return true;
  }
}

if (localStorageRoto()) {
  const dom = new JSDOM("", { url: "http://localhost:5173/" });
  Object.defineProperty(globalThis, "localStorage", {
    value: dom.window.localStorage,
    configurable: true,
    writable: true,
  });
}
