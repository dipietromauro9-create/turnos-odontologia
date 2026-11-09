import { Suspense } from "react";
import {
  BrowserRouter,
  MemoryRouter,
  Navigate,
  Outlet,
  Route,
  Routes,
} from "react-router-dom";

import { useAuthState } from "./shared/api/auth";
import { LoginPage } from "./features/auth/LoginPage";
import { SessionGate } from "./features/auth/SessionGate";
import { AgendaPage } from "./features/agenda/AgendaPage";
import { RecordatoriosPage } from "./features/recordatorios/RecordatoriosPage";
import { ReportesPage } from "./features/reportes/ReportesPage";
import { AppShell } from "./features/shell/AppShell";
import { TurneroPublicoPage } from "./features/turnero/TurneroPublicoPage";
import { MisTurnosPage } from "./pages/turnero/MisTurnosPage";
import { HomePage } from "./pages/HomePage";

/** Rama pública: renderiza sin login (turnero y login del panel). */
export function PublicRoute(): React.JSX.Element {
  return <Outlet />;
}

/** Rama privada: sin sesión redirige al login; con token completa la identidad. */
export function PrivateRoute(): React.JSX.Element {
  const { token } = useAuthState();
  if (token === null) {
    return <Navigate to="/login" replace />;
  }
  return (
    <SessionGate>
      <Outlet />
    </SessionGate>
  );
}

/** Árbol de rutas único: lo usan prod (BrowserRouter) y tests (MemoryRouter). */
export function RouteTree(): React.JSX.Element {
  return (
    <Routes>
      <Route element={<PublicRoute />}>
        <Route path="/" element={<HomePage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/turnero/:slug" element={<TurneroPublicoPage />} />
        <Route path="/turnero/mis-turnos" element={<MisTurnosPage />} />
      </Route>
      <Route element={<PrivateRoute />}>
        <Route path="/app" element={<AppShell />}>
          <Route index element={<AgendaPage />} />
          <Route path="recordatorios" element={<RecordatoriosPage />} />
          <Route path="reportes" element={<ReportesPage />} />
        </Route>
      </Route>
    </Routes>
  );
}

/** Router de producción. */
export function AppRoutes(): React.JSX.Element {
  return (
    <Suspense fallback={<p>Cargando…</p>}>
      <BrowserRouter>
        <RouteTree />
      </BrowserRouter>
    </Suspense>
  );
}

/** Router en memoria para tests (misma tabla de rutas, sin historial real). */
export function TestRouter({ initialPath }: { initialPath: string }): React.JSX.Element {
  return (
    <MemoryRouter initialEntries={[initialPath]}>
      <RouteTree />
    </MemoryRouter>
  );
}
