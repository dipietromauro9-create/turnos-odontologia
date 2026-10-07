# Discovery — turnos-odontologia

**Fecha**: 2026-09-30
**Fuentes investigadas**: 18 sistemas (ver `discovery/sources/` + `discovery/market-research.md` con tabla comparativa, matriz ponderada, análisis y recomendación)
**Regla de evidencia**: solo funcionalidad con fuente pública verificable; lo demás figura como "No evidenciado". Las cifras de marketing de cada proveedor se identifican como afirmación comercial.

## 1. Problema que resuelve

Los consultorios odontológicos argentinos (1–3 profesionales) coordinan turnos
por WhatsApp manual, papel o planillas: sufren ausentismo sin recordatorios
sistemáticos, huecos liberados que se pierden, cobros de señas desacoplados de
la agenda y doble carga administrativa (turno por un lado, facturación y obras
sociales por otro). Ningún sistema local une en un solo flujo turnos + señas
con Mercado Pago + factura ARCA + liquidación de obras sociales.

## 2. Usuarios / roles

- **Paciente**: reserva, confirma, cancela o reprograma online sin llamar.
- **Odontólogo independiente / dueño de consultorio**: ve su agenda, ficha
  clínica y caja diarias; liquida obras sociales.
- **Recepción / asistente** (consultorios con personal): carga turnos,
  confirma asistencias, cobra señas y gestiona la lista de espera.
- Secundario (post-MVP): clínicas multi-profesional y multi-sede.

## 3. Casos de uso

1. Como paciente, quiero ver horarios libres y reservar 24/7 desde un link
   (redes/web) sin llamar ni escribir.
2. Como paciente, quiero confirmar, cancelar o reprogramar mi turno y dejar
   una seña por Mercado Pago.
3. Como odontólogo, quiero ver mi agenda del día/semana con duraciones
   variables por prestación, bloqueos y sobreturnos, sin solapamientos.
4. Como recepción, quiero confirmar asistencias por WhatsApp y reasignar
   automáticamente los huecos liberados desde la lista de espera.
5. Como odontólogo, quiero registrar ficha clínica, odontograma FDI y
   presupuesto, y liquidar la prestación por obra social con factura ARCA.
6. Como dueño, quiero reportes de ocupación, ausencias e ingresos, y
   recuerdo automático de controles periódicos e inactivos.

## 4. Competidores / soluciones existentes

| Competidor | País | Problema que resuelve | Pricing público | Diferenciadores |
|---|---|---|---|---|
| DentalSoft | AR | Gestión odontológica integral AR-first | Sí, ARS (Gratis 6 m; $30.000; $60.000) | Obras sociales + liquidaciones, recepcionista IA, precio en pesos |
| Dentiqa | LATAM | Clínica avanzada + CRM + IA | Sí, USD 89/149/249 | Odontograma versionado, periodontograma, WhatsApp oficial Meta + IA |
| Bilog | AR | Gestión con 20 años de trayectoria | No | Obras sociales, auditoría, app móvil |
| Reservo | CL | Agenda + facturación regional | Parcial (~$30.000 ref.) | Única con ARCA integrado documentado + Mercado Pago en pesos |
| DentalCore | AR | Clínica con CDSS + bot paciente | Parcial (USD 5… truncado) | Bot de 9 flujos, portal paciente, periodontograma |
| Benty | AR | Gestión odontológica en nube | No | Declara adecuación a leyes argentinas; laboratorio y recetas |
| Docturno | AR | Marketplace + gestión multi-especialidad | No | Captación + Mercado Pago + facturador AFIP |
| Dentatools | LATAM/AR | Gestión básica accesible | Sí, ARS ($15.000/$30.000) | Precio bajo honesto; declara que NO hace OS ni factura (transparencia) |
| FLAP | AR | Turnero + gestión por perfil | No | Señas con Mercado Pago, odontograma FDI |
| Odontoly | AR | Gestión local-first | Sí, USD 99,90/mes + setup | Offline-first, exportación CSV/JSON |
| ClinIA | AR | Gestión con IA (incluye sector público) | No | Anamnesis, SUMAR+, facturación declarada |
| Dentalink | CL | Suite dental regional | No | Periodontograma, ortodoncia, IA (oferta ES) |
| AgendaPro | CL | Agenda genérica multi-rubro | No en AR | Doble confirmación, app; sin odontograma |
| Doctoralia | PL/ES | Marketplace de captación | No (profesional) | Filtro por obra social, reseñas; NO es software de gestión |
| Adiasoft | PE | ERP de clínicas | No (USD por plan) | Odontograma trazable CIE-10/CPOD; honesto: NO emite factura real |
| Encuadrado | CL | Agenda de servicios | Sí, UF + IVA | Sin foco dental ni ARCA |
| SimplyBook.me | CY/LV | Reserva genérica por plugins | Sí, USD 0–59,9 | Seguridad verificable (HIPAA + ISO 27001), plugins modulares |
| Fresha | UK | Marketplace belleza/salud | Sí, USD + 20% marketplace | Vara UX de reserva en 4 pasos, apps duales |

**Notas**: el rival directo es DentalSoft (mismo segmento + localización AR).
Dentiqa es la vara funcional, Reservo la única con ARCA documentado.
Doctoralia y Fresha son referencia de captación/UX, no de gestión.

**Ranking ponderado (top-5)**: 1.º DentalSoft 4,05 · 2.º Dentiqa 3,70 ·
3.º Bilog 3,40 · 4.º Reservo 3,35 · 5.º DentalCore 3,30. Detalle de pesos y
criterios en `discovery/market-research.md` sección B.

## 5. Funcionalidades necesarias

- Agenda multi-profesional con vistas día/semana, duración variable por
  prestación, bloqueos, sobreturnos y prevención de solapamientos.
- Turnero online 24/7 con link público; confirmación, cancelación y
  reprogramación por el paciente.
- Recordatorios y confirmaciones por WhatsApp con actualización de la agenda.
- Ficha del paciente + odontograma FDI básico + presupuestos.
- Seña con Mercado Pago atada al estado del turno; caja diaria y reportes
  básicos (ocupación, ausencias, ingresos).
- Roles (profesional/recepción) y exportación CSV desde el día uno.

## 6. Funcionalidades opcionales

- Periodontograma, módulo de ortodoncia, laboratorio dental, imágenes/RX.
- Bot IA de WhatsApp 24/7, recepcionista por voz, campañas de marketing.
- Multi-sede, auditoría completa, API pública, app móvil, portal del
  paciente, firma digital.

## 7. Reglas de negocio

- La seña condiciona el estado del turno (reservado vs. confirmado).
- El sobreturno es explícito; nunca solape silencioso.
- Un profesional no puede tener dos turnos superpuestos.
- El hueco liberado por cancelación se ofrece automáticamente a la lista de
  espera antes de quedar libre.
- La liquidación de obra social se ata a la prestación del turno por
  cobertura.

## 8. Integraciones

- WhatsApp (API oficial de Meta) para recordatorios, confirmaciones y avisos.
- Mercado Pago para señas y cobros atados al turno.
- ARCA para factura electrónica en el mismo flujo del turno.
- Obras sociales / prepagas argentinas (cobertura + liquidaciones).
- Google Calendar como referencia de sincronización (post-MVP).

## 9. Restricciones

- Precios públicos en pesos argentinos; alcance honesto (declarar qué NO
  hace, como hacen Dentatools y Adiasoft).
- Adecuación declarada a la normativa argentina aplicable a datos de salud
  (leyes 25.326 de datos personales y 26.529 de derechos del paciente).
- Exportación de datos abierta desde el día uno (anti-lock-in).
- Segmento inicial acotado: independiente y consultorio chico; cadenas y
  multi-sede quedan fuera del MVP.

## 10. Riesgos

- **Supuesto sin probar**: que los pacientes confirmen por WhatsApp y dejen
  seña online en vez de seguir coordinando por mensaje informal — no validado
  con usuarios reales todavía.
- **Riesgo de integraciones**: ARCA documentada en 1/18 competidores y
  Mercado Pago atado al turno en 3–4/18; el costo técnico real de ambas
  integraciones es la mayor incógnita del MVP.
- **Riesgo de alcance**: los claims de IA/CDSS de la competencia no están
  auditados; prometer IA clínica sin validación nos expone al mismo
  descrédito.
- **Riesgo de opacidad del mercado**: 11/18 no publican precios; estimar
  disposición a pagar en ARS requiere validación directa con odontólogos.
- **Riesgo de seguridad**: el 80% del mercado no publica nada técnico; hay
  que diseñar privacidad/trazabilidad desde el día uno para diferenciarse.

## 11. Preguntas abiertas

- ¿Precio objetivo en ARS y modalidad de cobro del MVP (suscripción, por
  profesional, por turno)?
- ¿Seña obligatoria u opcional por defecto?
- ¿Qué obras sociales priorizar en la v1?
- ¿Alcance inicial: solo odontólogo independiente o también consultorio de
  hasta 3 profesionales desde el día 1?
- ¿WhatsApp arranca manual/semiautomático o con API oficial desde la v1?
