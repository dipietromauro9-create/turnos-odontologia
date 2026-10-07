# Investigación de mercado — Sistemas odontológicos de turnos y agenda

- **Proyecto**: turnos-odontologia (Metodología I, Argentina)
- **Fecha de consulta de todas las fuentes**: 2026-09-30
- **Cobertura**: Argentina → Latinoamérica → internacionales relevantes
- **Notas por sistema**: `discovery/sources/*.md` (18 notas). Referencia secundaria sin nota completa: turnoapp (Argentina, agenda genérica con Mercado Pago; Pro $14.999 ARS/mes; fuente: https://turnoapp.com.ar/ — 2026-09-30).
- **Regla aplicada**: solo funcionalidad con fuente pública verificable; lo demás figura como "No evidenciado". Las cifras de marketing de cada proveedor se identifican como afirmación comercial.

## A. Tabla comparativa (ordenada por relevancia para Argentina)

| # | Sistema | País | URL | Foco dental | Turnos 24/7 + recordatorios | Odontograma / clínica | Obras sociales AR | ARCA / factura electrónica | Mercado Pago | WhatsApp | Precio público | Modelo |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | DentalSoft | AR | https://dentalsoft.com.ar/ | Sí, total | Sí / automáticos | Odontograma 18 estados, ortodoncia; sin periodontograma evidenciado | Sí (cobertura + liquidaciones) | No evidenciado | Sí | Automático (costo Meta por mensaje) | Sí, ARS (Gratis 6 m; $30.000; $60.000) | SaaS nube |
| 2 | Benty | AR | https://benty.com.ar/ | Sí | Sí / recordatorios | Odontograma, planes, laboratorio, recetas | No evidenciado | Facturación electrónica (alcance AR no detallado) | No evidenciado | Sí | No | SaaS nube |
| 3 | Bilog | AR | https://bilog.com.ar/ | Sí | Sí / packs WA+SMS | Odontograma, HC, presupuestos, galería, recetas | Sí (liquidaciones) | Pack factura electrónica | No evidenciado | Packs con costo | No | SaaS + app móvil |
| 4 | DentalCore | AR | https://dentalcore.app/ | Sí + CDSS declarado | Portal + bot 9 flujos | Odontograma + periodontograma + especialidades | Declarado, sin detalle | ARCA declarado, sin detalle | No evidenciado | Bot propio (QR) | Parcial (USD 5… truncado) | Sistema en nube |
| 5 | Dentiqa | LATAM | https://dentiqa.app/ | Sí, total | Bot IA 24/7 + recordatorios | Odontograma versionado + periodontograma BOP/NIC + firma | No evidenciado | No evidenciado | Sí | API oficial Meta + IA Claude | Sí, USD 89/149/249 | SaaS nube |
| 6 | Reservo | CL | https://reservo.cl/ | Sí (módulo) | Sí / cupos WA | Odontograma + ficha facial, consentimientos | No evidenciado | Sí, ARCA integrado | Sí, en pesos | Cupos por plan | No estable AR (~$30.000 ref.) | SaaS nube |
| 7 | Docturno | AR | https://profesionales.docturno.com/ | No (multi-especialidad) | Sí + bot WA | HC general; sin odontograma | Horarios por cobertura | Facturador AFIP | Sí | Oficial declarado + costo extra | No | SaaS + marketplace |
| 8 | Dentatools | LATAM/AR | https://dentatools.co/ar/ | Sí básico | Auto-agendado + recordatorios | HC + odontograma + presupuestos PDF | No (declara que NO) | No (declara que NO) | No evidenciado | Sí | Sí, ARS ($15.000 / $30.000) | SaaS nube |
| 9 | FLAP | AR | https://flap.com.ar/odontologos | Sí (perfil) | Turnero 24/7 + avisos | Odontograma FDI + HC | No evidenciado | No evidenciado | Sí (señas) | Paquetes adicionales | No | SaaS |
| 10 | Odontoly | AR | https://odontoly.com/ | Sí | No (agenda interna + add-on bot) | Odontograma anatómico 32 marcas | No evidenciado | Add-on pago | No evidenciado | Add-on pago | Sí, USD 99,90/mes + setup USD 599,90 | Híbrida local-first + móvil |
| 11 | ClinIA (OdontoClinIA) | AR | https://www.clinia.com.ar/odontologia | Sí (módulo) | Sí + IA WA | Anamnesis, odontograma, planes | Sector público (SUMAR+) | Facturación electrónica declarada | No evidenciado | Sí | No | Web |
| 12 | Dentalink | CL | https://www.softwaredentalink.com/ | Sí, total | Sí / automáticos | Odontograma + periodontograma + ortodoncia | No evidenciado | No (Verifactu ES, RGPD) | No evidenciado | Sí + IA (oferta ES) | No (ref. USD 29 no oficial) | SaaS nube |
| 13 | AgendaPro | CL | https://agendapro.com/ar | No (genérico) | Sí + doble confirmación | Ficha editable; sin odontograma | No evidenciado | No evidenciado | No evidenciado | Sí, costo variable | No en AR | SaaS + app |
| 14 | Doctoralia | PL/ES | https://www.doctoraliar.com/ | No (marketplace) | Reserva + SMS | No evidenciado (Pro no público) | Filtro por OS (captación) | No evidenciado | No evidenciado | No evidenciado | No (profesional) / gratis paciente | Marketplace + app |
| 15 | Adiasoft | PE | https://www.adiasoft.com/ar/sistema-para-clinicas-dentales | Sí (ERP) | Portal paciente | Odontograma FDI trazable, CPOD, CIE-10 | No evidenciado | Configurado SIN emisión real (honesto) | No evidenciado | No evidenciado | No (USD por plan) | ERP nube |
| 16 | Encuadrado | CL | https://www.encuadrado.com/ | No | Sí / recordatorios | Fichas (CENS CL); sin odontograma | No | Boletas CL, no ARCA | No | Sí | Sí, UF (0,6/1/3 + IVA) | SaaS |
| 17 | SimplyBook.me | CY/LV | https://simplybook.me/es/ | No (salud gen.) | Sí + plugins | Notas SOAP cifradas; sin odontograma | No | No | No evidenciado | Plugin | Sí, USD 0–59,9 | SaaS + apps |
| 18 | Fresha | UK | https://www.fresha.com/es | No (belleza/salud) | Sí + marketplace | Notas de sesión; sin odontograma | No | No | No evidenciado | Costo por mensaje | Sí, USD por miembro + 20% marketplace | SaaS + apps |

## B. Matriz de puntuación ponderada (0–5)

Pesos: Turnos y automatización 25% · Clínica odontológica 20% · Integraciones locales y WhatsApp 15% · Administración/cobros/facturación 15% · Experiencia del paciente 10% · Seguridad/exportación/trazabilidad 10% · Precio y facilidad de adopción 5%.

| Sistema | Turnos 25% | Clínica 20% | Integ. 15% | Admin 15% | Exp.pac. 10% | Segur. 10% | Precio 5% | **Total** |
|---|---|---|---|---|---|---|---|---|
| DentalSoft (AR) | 5 | 4 | 3 | 4 | 5 | 2 | 5 | **4,05** |
| Dentiqa | 4 | 5 | 3 | 3 | 4 | 3 | 2 | **3,70** |
| Bilog (AR) | 4 | 4 | 2 | 4 | 4 | 2 | 2 | **3,40** |
| Reservo (CL) | 3 | 4 | 4 | 3 | 4 | 2 | 3 | **3,35** |
| DentalCore (AR) | 4 | 5 | 2 | 3 | 4 | 1 | 1 | **3,30** |
| SimplyBook.me | 4 | 2 | 2 | 3 | 4 | 4 | 4 | **3,15** |
| Dentalink (CL) | 3 | 5 | 2 | 3 | 3 | 2 | 2 | **3,10** |
| Benty (AR) | 3 | 4 | 2 | 3 | 3 | 3 | 2 | **3,00** |
| FLAP (AR) | 4 | 3 | 3 | 2 | 4 | 1 | 2 | **2,95** |
| Docturno (AR) | 4 | 2 | 3 | 3 | 4 | 1 | 2 | **2,90** |
| AgendaPro (CL) | 4 | 2 | 2 | 3 | 4 | 1 | 2 | **2,75** |
| ClinIA (AR) | 3 | 3 | 3 | 2 | 3 | 2 | 1 | **2,65** |
| Fresha (UK) | 4 | 1 | 1 | 3 | 5 | 2 | 3 | **2,65** |
| Adiasoft (PE) | 2 | 4 | 1 | 4 | 2 | 2 | 1 | **2,50** |
| Dentatools (AR) | 3 | 2 | 2 | 2 | 3 | 1 | 4 | **2,35** |
| Odontoly (AR) | 2 | 3 | 2 | 2 | 2 | 3 | 2 | **2,30** |
| Encuadrado (CL) | 3 | 1 | 1 | 2 | 3 | 1 | 2 | **1,90** |
| Doctoralia | 2 | 0 | 1 | 0 | 5 | 1 | 1 | **1,30** |

**Ranking ponderado (top-5)**: 1.º DentalSoft 4,05 · 2.º Dentiqa 3,70 · 3.º Bilog 3,40 · 4.º Reservo 3,35 · 5.º DentalCore 3,30.
Nota: Doctoralia puntúa 1,30 *como software de gestión* (no lo es); como canal de captación su puntaje sería ~5 y debe evaluarse por separado.

Criterio de puntaje: 0 = ausente/no evidenciado; 1 = mención marginal; 2 = básico; 3 = funcional verificado; 4 = sólido con evidencia amplia; 5 = diferencial comprobado. "No evidenciado" penaliza porque la regla de evidencia impide presumir capacidad.

## C. Análisis competitivo

### Funcionalidades estándar del mercado (lo que casi todos tienen)

1. Agenda online con reserva 24/7 y link para redes sociales.
2. Recordatorios/confirmaciones por WhatsApp y e-mail (casi siempre con costo por mensaje o cupo).
3. Historia clínica digital + odontograma básico + presupuestos.
4. Caja/cobros y reportes elementales; comisiones por profesional en el segmento medio-alto.
5. Gestión multi-profesional y multi-sede en planes superiores.
6. Chatbot o asistente virtual de primer nivel (de reglas a IA real).
7. Prueba/demo de acceso (gratis temporal o demo guiada); precios publicados solo en ~40% de los casos.

### Diferenciadores reales (verificados, no slogans)

- **Localización argentina profunda**: solo DentalSoft (obras sociales + liquidaciones + ARS público), Bilog (obras sociales + auditoría + 20 años) y Docturno (marketplace + Mercado Pago + facturador) la tienen. El resto "opera en Argentina" sin adaptarse.
- **ARCA real**: únicamente Reservo lo integra de forma documentada; Adiasoft es el único honesto al admitir que NO emite. Es el mayor vacío del mercado.
- **WhatsApp oficial + IA**: Dentiqa (Meta verificado + Claude en 3 capas) y DentalSoft (recepcionista IA 24 h) lideran; el resto usa WhatsApp manual, QR propio o costo extra.
- **Clínica avanzada**: periodontograma solo en Dentiqa, Dentalink y DentalCore; ortodoncia modular en DentalSoft/Dentalink; local-first/offline solo en Odontoly.
- **Captación**: Doctoralia (marketplace + reseñas + filtro OS) y Fresha (UX de reserva + marketplace) son la vara en adquisición, no en gestión.
- **Seguridad verificable**: SimplyBook.me (HIPAA + ISO 27001 + RSA-4096) y Benty (leyes argentinas declaradas) son lo único citable; el 80% del mercado no publica nada técnico.

### Vacíos frecuentes del mercado argentino

1. **Factura electrónica ARCA integrada**: 1 de 18 la tiene documentada.
2. **Obras sociales/prepagas con liquidaciones**: 3 de 18.
3. **Precios públicos en pesos**: 3 de 18 (DentalSoft, Dentatools, turnoapp como referencia genérica).
4. **Señas con Mercado Pago atadas al turno**: 3–4 de 18.
5. **Lista de espera y auto-relleno de huecos**: 1–2 de 18 (DentalCore declara auto-relleno; Fresha/SimplyBook tienen lista de espera genérica).
6. **Normativa argentina de datos/salud publicada**: 2 de 18 la declaran (Benty, Odontoly parcialmente).
7. **Exportación de datos y anti-lock-in**: casi nadie la documenta (excepción parcial: Odontoly CSV/JSON, Dentiqa CSV/Excel).
8. **Periodontograma, laboratorio dental y teleodontología**: minoritarios.

### Oportunidades de innovación para turnos-odontologia

1. **Núcleo AR-first**: turnos + señas MP + ARCA + obras sociales en un solo flujo, con precios en pesos: nadie lo hace completo.
2. **No-show cero**: recordatorios + confirmación + lista de espera con reasignación automática + penalización/seña: el hueco liberado hoy se pierde en casi todos.
3. **Transparencia radical**: pricing público, alcance honesto (qué NO hace), exportación abierta; el mercado opaco lo agradecería (caso Adiasoft/Dentatools como prueba).
4. **Recepción autónoma**: bot WhatsApp que agenda, confirma, cobra seña y deriva urgencias, pensado para consultorio de 1–3 profesionales (segmento peor atendido en precio).
5. **Continuidad clínica**: recall de controles periódicos e inactivos atado a la agenda (prometido por varios, evidenciado por pocos).

## D. Recomendación

### 5 competidores prioritarios para demo

1. **DentalSoft** — el rival directo: pricing en ARS, obras sociales, web + turnero + chatbot. Pedir demo del panel y del flujo paciente completo.
2. **Bilog** — el incumbente: 20 años y auditoría/OS; evaluar profundidad real de agenda y costo de packs WhatsApp/factura.
3. **Dentiqa** — la vara funcional: odontograma versionado, periodontograma, CRM y WhatsApp oficial con IA; medir costo real en ARS y ausencia de ARCA/OS.
4. **Reservo** — la única con ARCA + Mercado Pago + odontograma; verificar precio AR, agenda por sillón y soporte local.
5. **DentalCore** — la apuesta CDSS + bot de 9 flujos + portal paciente; auditar claims clínicos, precio final y seguridad.

### 3 productos de referencia UX

1. **Fresha** — flujo de reserva en 4 pasos, gestión de listas de espera y apps duales (negocio/cliente).
2. **Doctoralia** — búsqueda con filtro por obra social, perfiles con reseñas y confirmación/recordatorio del lado paciente.
3. **SimplyBook.me** — configuración guiada por IA, plugins modulares y página de reserva personalizable.

### MVP sugerido

**Imprescindibles (alcance mínimo viable)**:
- Agenda multi-profesional con vistas día/semana, duración variable por prestación, bloqueos, sobreturnos y anti-solapamiento.
- Turnero online 24/7 con link público, confirmación/cancelación/reprogramación por el paciente.
- Recordatorios y confirmaciones por WhatsApp (aunque sea manual/semiautomático al inicio) con actualización de la agenda.
- Ficha del paciente + odontograma FDI básico + presupuestos.
- Seña con Mercado Pago atada al estado del turno; caja diaria y reportes básicos (ocupación, ausencias, ingresos).
- Roles (profesional/recepción) y exportación CSV desde el día uno.

**Diferenciadores (apuesta del producto)**:
- Lista de espera con reasignación automática de huecos.
- Liquidación de obras sociales argentinas + factura ARCA en el mismo flujo del turno.
- Precios públicos en pesos y declaración honesta de alcance.
- Recall automático de controles periódicos e inactivos.

**Para etapas posteriores**:
- Periodontograma, ortodoncia modular, laboratorio, imágenes/RX.
- Bot IA WhatsApp 24/7, recepcionista por voz, campañas de marketing.
- Multi-sede, auditoría completa, API pública, app móvil, portal del paciente, firma digital.
