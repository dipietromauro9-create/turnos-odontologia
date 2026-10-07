# Spec Delta

## Purpose

Brinda la base de backend ejecutable sobre la que construyen todos los changes siguientes: señal de health, configuración por entorno, conectividad a la base de datos y un sobre uniforme de errores de dominio.

## ADDED Requirements

### Requirement: El endpoint de health informa liveness

El sistema DEBE (SHALL) exponer `GET /health` que devuelve HTTP 200 con un cuerpo JSON indicando el estado del servicio y la alcanzabilidad de la base de datos, sin requerir autenticación.

#### Scenario: El servicio sano reporta ok

- **WHEN** un cliente llama a `GET /health` con la base de datos alcanzable
- **THEN** la respuesta es HTTP 200 con `{"status": "ok"}` más un indicador de base de datos

#### Scenario: El endpoint de health es público

- **WHEN** un cliente no autenticado llama a `GET /health`
- **THEN** la petición tiene éxito (sin 401/403) porque el liveness tiene que funcionar para orquestadores y CI

### Requirement: La configuración carga desde el entorno

El sistema DEBE (SHALL) cargar toda la configuración de runtime exclusivamente desde variables de entorno con validación tipada al arrancar, fallando rápido con un mensaje claro cuando falta una variable requerida o está mal formada.

#### Scenario: El entorno válido arranca

- **WHEN** todas las variables requeridas (`DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`, `ACCESS_MINUTES`, `REFRESH_DAYS`, `TENANT_DEFAULT_SLUG`, `TZ`, `FRONTEND_ORIGIN`, `RECORDATORIO_VENTANA_HS`) están presentes y bien formadas
- **THEN** la aplicación arranca y expone los valores configurados a través de settings (sin loguear nunca los secretos)

#### Scenario: La variable requerida faltante falla rápido

- **WHEN** falta una variable requerida o está mal formada al arrancar
- **THEN** la aplicación se niega a arrancar con un error que nombra la variable problemática

### Requirement: Una sola zona horaria fija desde el día uno

El sistema DEBE (SHALL) operar en la única zona horaria `America/Argentina/Buenos_Aires` (RN-GL-03): el `TZ` por defecto es esa zona y todos los timestamps persistidos tienen zona horaria (aware).

#### Scenario: La zona horaria por defecto es Buenos Aires

- **WHEN** `TZ` no se sobrescribe en el entorno
- **THEN** la zona horaria efectiva es `America/Argentina/Buenos_Aires`

#### Scenario: Los datetimes naive se rechazan en el borde

- **WHEN** un datetime sin información de zona horaria llega a un borde validado
- **THEN** el sistema lo rechaza (4xx con código de error de dominio) en lugar de persistir un valor naive

### Requirement: Los errores de dominio usan un sobre uniforme

El sistema DEBE (SHALL) devolver los fallos de dominio/negocio con un sobre JSON que contenga al menos el campo `code` en formato `RN-XX-NN` (RN-GL-01), para que el frontend y los tests hablen el mismo idioma que la base de conocimiento.

#### Scenario: El fallo de dominio trae el código de regla

- **WHEN** una petición dispara un fallo de una regla de negocio codificada
- **THEN** el cuerpo de la respuesta incluye `{"code": "RN-XX-NN", ...}` identificando la regla, con un estado HTTP acorde a la clase de fallo (4xx, nunca 500 para una regla conocida)

### Requirement: Existe la sesión de base de datos y la línea base de migraciones

El sistema DEBE (SHALL) proveer una única fábrica de sesiones usada por todo acceso a datos y una cadena de migraciones inicializada (revisión base sin tablas de dominio todavía), para que C-02 pueda agregar las tablas `tenant`/`usuario` sin retrabajo.

#### Scenario: La API alcanza la base de datos

- **WHEN** la API corre bajo Compose con Postgres sano
- **THEN** `GET /health` (o un chequeo equivalente de arranque) confirma una conexión viva a la DB

#### Scenario: La cadena de migraciones está al día sobre una base nueva

- **WHEN** las migraciones corren contra una base Postgres 16 vacía
- **THEN** se aplican limpiamente hasta head con cero tablas de dominio y el chequeo pasa
