# Spec Delta

## Purpose

Convierte la agenda de turnos confirmados en una cola diaria de avisos por WhatsApp para recepción: genera de forma programada e idempotente un recordatorio por turno próximo, con texto listo para copiar, y registra quién lo envió o por qué falló.

## ADDED Requirements

### Requirement: Existe a lo sumo un recordatorio por turno

El sistema DEBE (SHALL) garantizar que un turno tenga como máximo un recordatorio registrado, sin importar cuántas veces se ejecute la generación. La unicidad DEBE (SHALL) estar respaldada por la base de datos, no solo por el servicio (RN-CO-01).

#### Scenario: Un segundo recordatorio para el mismo turno se rechaza

- **WHEN** se intenta insertar un recordatorio para un turno que ya tiene uno
- **THEN** la escritura falla por violación de unicidad y el recordatorio original queda intacto

#### Scenario: Reejecutar la generación no duplica recordatorios

- **WHEN** el job de generación corre dos veces seguidas sobre el mismo conjunto de turnos
- **THEN** cada turno conserva exactamente un recordatorio y no se inserta una segunda fila

### Requirement: La generación programada cubre los turnos confirmados próximos

El sistema DEBE (SHALL) generar un recordatorio en estado `pendiente` para cada turno en estado `confirmado` cuyo inicio caiga dentro de la ventana configurada `RECORDATORIO_VENTANA_HS` (por defecto `[ahora + 24 h, ahora + 48 h]`), y NO DEBE (SHALL NOT) generar recordatorios para turnos en otro estado ni para turnos fuera de la ventana superior.

#### Scenario: Turno confirmado dentro de la ventana genera un pendiente

- **WHEN** el job corre y existe un turno `confirmado` con inicio a 36 h
- **THEN** se crea un recordatorio `pendiente` asociado a ese turno

#### Scenario: Turnos no confirmados no generan recordatorio

- **WHEN** el job corre y existen turnos en estado `reservado`, `atendido`, `cancelado` o `ausente` dentro de la ventana
- **THEN** no se crea ningún recordatorio para esos turnos

#### Scenario: Turno más allá de la ventana superior no genera recordatorio

- **WHEN** el job corre y existe un turno `confirmado` con inicio a 72 h
- **THEN** no se crea recordatorio para ese turno

#### Scenario: La ventana se toma de la configuración

- **WHEN** `RECORDATORIO_VENTANA_HS` vale `12,36`
- **THEN** el job genera para turnos confirmados con inicio entre 12 h y 36 h, y no para los que están fuera de ese rango

### Requirement: La generación recupera los avisos perdidos tras una caída del worker

El sistema DEBE (SHALL) rellenar, en la siguiente ejecución, los recordatorios de turnos confirmados que ya entraron en la ventana mientras el worker estaba caído, sin duplicar los existentes y sin generar avisos para turnos ya pasados.

#### Scenario: El worker vuelve después de una caída y completa lo faltante

- **WHEN** el worker estuvo detenido y al reanudarse corre el job
- **THEN** se crean los recordatorios faltantes de turnos confirmados próximos que aún no tienen uno, y los que ya tenían recordatorio no se duplican

#### Scenario: Un turno próximo sin recordatorio se recupera

- **WHEN** el job corre y existe un turno `confirmado` a 10 h que no tiene recordatorio (porque el ciclo anterior no llegó a generarlo)
- **THEN** se crea su recordatorio `pendiente` para que recepción pueda avisar igual

#### Scenario: Un turno ya pasado no genera recordatorio

- **WHEN** el job corre y existe un turno `confirmado` cuyo inicio ya ocurrió
- **THEN** no se crea recordatorio para ese turno

### Requirement: El texto del recordatorio se arma por plantilla con los datos del turno

El sistema DEBE (SHALL) generar el texto del recordatorio en el backend a partir de una plantilla que incluya el nombre del paciente, el nombre del profesional, la fecha y hora del turno en `America/Argentina/Buenos_Aires` y la dirección del consultorio (RN-CO-02, RN-GL-03). La recepción NO DEBE (SHALL NOT) tener que componer el mensaje manualmente.

#### Scenario: El texto contiene los datos del turno

- **WHEN** se genera un recordatorio
- **THEN** el texto incluye el nombre del paciente, el nombre del profesional, la fecha y hora del turno y la dirección configurada del consultorio

#### Scenario: La fecha se expresa en la zona horaria del sistema

- **WHEN** un turno está almacenado en UTC y corresponde a las 10:00 en `America/Argentina/Buenos_Aires`
- **THEN** el texto muestra la hora local argentina y no la hora UTC

### Requirement: La cola de recepción muestra los avisos pendientes y los fallidos

El sistema DEBE (SHALL) exponer una cola de recordatorios que incluya los estados `pendiente` y `fallido`, ordenada por el inicio del turno, con los datos necesarios para enviar el aviso sin consultas adicionales. Los recordatorios ya `enviado` y los de turnos cancelados NO DEBEN (SHALL NOT) aparecer en la cola.

#### Scenario: La cola incluye pendientes y fallidos

- **WHEN** recepción consulta la cola y existen recordatorios `pendiente` y `fallido` de turnos confirmados
- **THEN** ambos aparecen, ordenados por la fecha/hora del turno

#### Scenario: Un fallido sigue visible para reintento

- **WHEN** un recordatorio se marcó `fallido`
- **THEN** sigue apareciendo en la cola de recepción hasta que se marque `enviado`

#### Scenario: Un enviado sale de la cola

- **WHEN** un recordatorio se marcó `enviado`
- **THEN** deja de aparecer en la cola de pendientes

#### Scenario: Un turno cancelado no muestra su recordatorio

- **WHEN** un turno con recordatorio pendiente se cancela
- **THEN** ese recordatorio no aparece en la cola de recepción

### Requirement: Marcar un recordatorio como enviado registra quién lo envió

El sistema DEBE (SHALL) permitir marcar un recordatorio `pendiente` o `fallido` como `enviado`, registrando el usuario que lo envió (RN-CO-03). Un recordatorio ya `enviado` NO DEBE (SHALL NOT) poder volver a marcarse, y la base DEBE (SHALL) rechazar cualquier fila `enviado` sin usuario responsable.

#### Scenario: Marcar enviado registra al usuario

- **WHEN** recepción marca como `enviado` un recordatorio pendiente
- **THEN** el estado pasa a `enviado` y queda registrado el usuario que lo marcó

#### Scenario: Un fallido puede reintentarse y marcarse enviado

- **WHEN** recepción marca como `enviado` un recordatorio que estaba `fallido`
- **THEN** el estado pasa a `enviado` y queda registrado el usuario del reintento

#### Scenario: No se puede reenviar un recordatorio ya enviado

- **WHEN** se intenta marcar como `enviado` un recordatorio que ya está `enviado`
- **THEN** la operación se rechaza con un error de dominio identificable y el estado no cambia

### Requirement: Marcar un recordatorio como fallido lo deja reintentable

El sistema DEBE (SHALL) permitir marcar como `fallido` un recordatorio `pendiente` o `fallido`, manteniéndolo en la cola y sin registrar un responsable de envío.

#### Scenario: Marcar fallido mantiene el aviso en la cola

- **WHEN** recepción marca como `fallido` un recordatorio pendiente
- **THEN** el estado pasa a `fallido`, no se registra `enviado_por` y el aviso sigue en la cola

#### Scenario: Volver a marcar fallido es idempotente

- **WHEN** se marca como `fallido` un recordatorio que ya estaba `fallido`
- **THEN** la operación tiene éxito y el registro queda igual

### Requirement: La cola y el marcado respetan tenant, rol y alcance del profesional

El sistema DEBE (SHALL) limitar la cola y el marcado al tenant resuelto de la request (R3) y a los roles `recepcion` y `profesional`. Un usuario `profesional` sin `es_dueno` DEBE (SHALL) ver y operar únicamente los recordatorios de turnos de su propio profesional; dueño y recepción ven el consolidado del tenant. Un recordatorio de otro tenant DEBE (SHALL) responder como inexistente (404 genérico).

#### Scenario: Un profesional sin dueño solo ve sus propios recordatorios

- **WHEN** un usuario `profesional` sin `es_dueno` consulta la cola
- **THEN** solo aparecen los recordatorios de turnos de su profesional vinculado

#### Scenario: Dueño y recepción ven el consolidado

- **WHEN** un usuario dueño o de recepción consulta la cola
- **THEN** aparecen los recordatorios de todos los profesionales del tenant

#### Scenario: Un recordatorio de otro tenant no es accesible

- **WHEN** se intenta marcar un recordatorio que pertenece a otro tenant
- **THEN** la respuesta es 404 y el recordatorio del otro tenant no se modifica

#### Scenario: Un rol no autorizado no accede a la cola

- **WHEN** un usuario sin rol `recepcion` ni `profesional` consulta la cola
- **THEN** la respuesta es 403 y no se devuelven recordatorios
