import { Link } from "react-router-dom";

/** Portada pública: entrada al panel y al turnero del consultorio. */
export function HomePage(): React.JSX.Element {
  return (
    <main className="home-page">
      <section className="home-page__card">
        <p className="home-page__marca">OdontoGrid</p>
        <h1>Turnos Odontología</h1>
        <p className="home-page__ayuda">
          Panel interno para el consultorio y turnero online para pacientes.
        </p>
        <div className="home-page__acciones">
          <Link className="boton-primario" to="/login">
            Ingresar al panel
          </Link>
          <Link to="/turnero/demo">Reservar un turno</Link>
        </div>
      </section>
    </main>
  );
}
