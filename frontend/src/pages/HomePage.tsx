import { Link } from "react-router-dom";

/** Portada pública: entrada al panel y al turnero del consultorio. */
export function HomePage(): React.JSX.Element {
  return (
    <main>
      <h1>Turnos Odontología</h1>
      <p>Panel interno y turnero online del consultorio.</p>
      <p>
        <Link to="/login">Ingresar al panel</Link>
      </p>
    </main>
  );
}
