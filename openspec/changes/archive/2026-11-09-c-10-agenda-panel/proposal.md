# Proposal

## Why

C-10 es el último change del MVP y el único que convierte el panel en un producto usable. Hoy el shell es un placeholder sin sesión real, `GET /turnos` devuelve solo IDs (no nombres de paciente, profesional ni prestación) y los directorios de profesionales y prestaciones son exclusivos del dueño. Con eso, recepción no puede armar la agenda ni crear un turno: la API funciona, pero no existe la interfaz interna que la use.

## What Changes

- **Agregador de agenda**: nuevos `GET /agenda/dia` y `GET /agenda/semana` que devuelven en una sola respuesta los turnos del rango con nombres para mostrar (paciente, profesional, prestación), las columnas de profesionales, el catálogo de prestaciones activas y los bloqueos que intersectan el rango. Aplica RN-AU-03: recepción y dueño ven todas las agendas; el profesional sin flag ve solo la propia y recibe 403 `RN-AU-03` si pide otra.
- **Proyección de lectura para el panel**: profesionales y prestaciones exponen un subconjunto mínimo (id, nombre y especialidad/duración) a cualquier usuario autenticado del panel, sin abrir la gestión, que sigue siendo exclusiva del dueño.
- **Sesión real del panel**: formulario de login, almacenamiento del access token, reintento transparente de `/auth/refresh` ante un 401, bootstrap de `/auth/me` para conocer `rol` y `es_dueno`, y logout. Las rutas privadas redirigen al login real; la navegación se adapta al rol.
- **UI de agenda día/semana** a partir de la pantalla exportada de Stitch (`docs/design/agenda/583dff22e2694257a60010f10a833229.*`), con tokens de estado de `estados.css`: columnas por profesional, tarjetas con etiqueta textual de estado y sobreturno explícito, filtros, navegación día/semana, alta de turno interno (normal y sobreturno con motivo), transiciones confirmar/atender/ausencia/cancelar con mensajes `RN-XX-NN`, y gestión de disponibilidad/bloqueos solo para el dueño.
- **Sin reglas de negocio nuevas ni migraciones**: la creación, las transiciones y los huecos reutilizan los endpoints de C-07 y C-08.

**Fuera de alcance**: el shell completo del mockup (sidebar y top bar de Stitch), ficha clínica/odontograma, Mercado Pago, ARCA y WhatsApp automático; quedan para post-MVP (`knowledge-base/11_post_mvp_e_integraciones.md`).

## Capabilities

### New Capabilities

- `core/agenda`: agregación día/semana para el panel y la interfaz de agenda (vistas, filtros, alta de turnos, transiciones y configuración de agenda del dueño).

### Modified Capabilities

- `foundation/frontend-shell`: el login provisorio se reemplaza por el ciclo de sesión real (login, refresh, me, logout) y la navegación privada pasa a depender del rol.
- `core/profesionales`: se habilita una proyección mínima de lectura para el panel sin alterar la gestión exclusiva del dueño.
- `core/prestaciones`: ídem, proyección mínima de lectura para armar turnos sin abrir la gestión del catálogo.

## Impact

- **Backend**: nuevo módulo `app/domain/agenda/panel/` (router, schemas, service, consultas) montado en `/agenda`; reutiliza `profesional_del_alcance` y `require_role`. Sin migraciones.
- **Frontend**: `features/auth` (login), `features/agenda` (vistas, tarjetas, filtros, formularios), `pages/LoginPage`, `routes.tsx`, `shared/api/client.ts` (reintento de refresh), `shared/api/agendaClient.ts` y `shared/api/auth.ts`; tests Vitest de RBAC de vistas, estados y transiciones.
- **Diseño**: `docs/design/agenda/` ya exportado se usa como insumo; la skill `pantalla-a-componente` guía la conversión a componentes.
- **Dependencias**: ninguna nueva (sin Tailwind ni librería de componentes).
- **Riesgo**: tamaño de la respuesta semanal. Se acota a un rango máximo de 7 días y se apoya en los índices existentes por `(tenant_id, profesional_id, inicio)`.
