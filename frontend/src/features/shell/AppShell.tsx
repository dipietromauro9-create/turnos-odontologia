import { NavLink, Outlet, useNavigate } from "react-router-dom";

import { logout, useAuthState } from "../../shared/api/auth";

/** Shell mínimo del panel: navegación por rol y logout real. */
export function AppShell(): React.JSX.Element {
  const { usuario } = useAuthState();
  const navigate = useNavigate();

  const salir = (): void => {
    logout().finally(() => navigate("/login", { replace: true }));
  };

  return (
    <div className="panel-shell">
      <header className="panel-barra">
        <strong>Turnos Odontología</strong>
        <nav aria-label="Panel">
          <NavLink to="/app" end>
            Agenda
          </NavLink>
          <NavLink to="/app/recordatorios">Recordatorios</NavLink>
          {usuario?.es_dueno === true ? <NavLink to="/app/reportes">Reportes</NavLink> : null}
        </nav>
        <span className="panel-barra__usuario">{usuario?.nombre ?? ""}</span>
        <button type="button" onClick={salir}>
          Cerrar sesión
        </button>
      </header>
      <Outlet />
    </div>
  );
}
