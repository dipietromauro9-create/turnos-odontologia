import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";

import { cargarIdentidad, clearAuthState, useAuthState } from "../../shared/api/auth";

function mensajeDeError(error: unknown): string {
  return error instanceof Error ? error.message : "No pudimos cargar la sesión.";
}

/**
 * Guard de sesión: exige token y completa la identidad con `/auth/me`
 * cuando el storage solo trae el access (token inyectado en dev o v1 migrada).
 */
export function SessionGate({ children }: { readonly children: React.ReactNode }): React.JSX.Element {
  const { token, usuario } = useAuthState();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (token === null || usuario !== null) return;
    cargarIdentidad().catch((fallo: unknown) => {
      clearAuthState();
      setError(mensajeDeError(fallo));
    });
  }, [token, usuario]);

  if (token === null) return <Navigate to="/login" replace />;
  if (usuario === null) {
    return (
      <p role="status" className="agenda-cargando">
        {error ?? "Cargando sesión…"}
      </p>
    );
  }
  return <>{children}</>;
}
