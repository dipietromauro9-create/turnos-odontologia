/** URL base única del backend; falla temprano si el entorno no la define. */
export function apiBaseUrl(): string {
  const base = import.meta.env["VITE_API_URL"];
  if (typeof base !== "string" || base.length === 0) {
    throw new Error("Falta VITE_API_URL: definir la URL base del backend en el entorno");
  }
  return base.replace(/\/$/, "");
}
