import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";

import { ApiError } from "../../shared/api/client";
import { login, useAuthState } from "../../shared/api/auth";

function mensajeDeError(error: unknown): string {
  if (error instanceof ApiError) return `${error.message} (${error.code})`;
  return "No pudimos iniciar sesión. Intentá de nuevo.";
}

/** Login real del panel: access token + identidad (rol y es_dueno). */
export function LoginPage(): React.JSX.Element {
  const { token } = useAuthState();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  if (token !== null) return <Navigate to="/app" replace />;

  const enviar = (evento: React.FormEvent<HTMLFormElement>): void => {
    evento.preventDefault();
    setEnviando(true);
    setError(null);
    login(email, password).then(
      () => navigate("/app", { replace: true }),
      (fallo: unknown) => {
        setError(mensajeDeError(fallo));
        setEnviando(false);
      },
    );
  };

  return (
    <main className="login-page">
      <h1>Ingresar</h1>
      <form onSubmit={enviar} aria-label="Inicio de sesión">
        <label>
          Email
          <input
            type="email"
            name="email"
            autoComplete="username"
            value={email}
            onChange={(evento) => setEmail(evento.target.value)}
            required
          />
        </label>
        <label>
          Contraseña
          <input
            type="password"
            name="password"
            autoComplete="current-password"
            value={password}
            onChange={(evento) => setPassword(evento.target.value)}
            required
          />
        </label>
        {error === null ? null : (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        <button type="submit" disabled={enviando} className="boton-primario">
          {enviando ? "Ingresando…" : "Ingresar"}
        </button>
      </form>
    </main>
  );
}
