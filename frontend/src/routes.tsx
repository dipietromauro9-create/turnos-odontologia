import { Suspense } from "react";
import {
  BrowserRouter,
  MemoryRouter,
  Navigate,
  Outlet,
  Route,
  Routes,
} from "react-router-dom";

import { readAuthState } from "./shared/api/auth";
import { HomePage } from "./pages/HomePage";
import { LoginPage } from "./pages/LoginPage";

/** Rama pública: renderiza sin login (las páginas del turnero caen acá en C-09). */
export function PublicRoute(): React.JSX.Element {
  return <Outlet />;
}

/** Rama privada: anónimo redirige al login provisorio (panel real en C-10). */
export function PrivateRoute(): React.JSX.Element {
  const { token } = readAuthState();
  if (token === null) {
    return <Navigate to="/login" replace />;
  }
  return <Outlet />;
}

/** Árbol de rutas único: lo usan prod (BrowserRouter) y tests (MemoryRouter). */
export function RouteTree(): React.JSX.Element {
  return (
    <Routes>
      <Route element={<PublicRoute />}>
        <Route path="/" element={<HomePage />} />
        <Route path="/login" element={<LoginPage />} />
      </Route>
      <Route element={<PrivateRoute />}>
        <Route path="/app" element={<HomePage />} />
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
