---
name: OdontoGrid Clinical OS
colors:
  surface: '#faf8ff'
  surface-dim: '#d2d9f4'
  surface-bright: '#faf8ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f2f3ff'
  surface-container: '#eaedff'
  surface-container-high: '#e2e7ff'
  surface-container-highest: '#dae2fd'
  on-surface: '#131b2e'
  on-surface-variant: '#3d4947'
  inverse-surface: '#283044'
  inverse-on-surface: '#eef0ff'
  outline: '#6d7a77'
  outline-variant: '#bcc9c6'
  surface-tint: '#006a61'
  primary: '#00685f'
  on-primary: '#ffffff'
  primary-container: '#008378'
  on-primary-container: '#f4fffc'
  inverse-primary: '#6bd8cb'
  secondary: '#006a63'
  on-secondary: '#ffffff'
  secondary-container: '#99efe5'
  on-secondary-container: '#006f67'
  tertiary: '#712ae2'
  on-tertiary: '#ffffff'
  tertiary-container: '#8a4cfc'
  on-tertiary-container: '#fffbff'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#89f5e7'
  primary-fixed-dim: '#6bd8cb'
  on-primary-fixed: '#00201d'
  on-primary-fixed-variant: '#005049'
  secondary-fixed: '#9cf2e8'
  secondary-fixed-dim: '#80d5cb'
  on-secondary-fixed: '#00201d'
  on-secondary-fixed-variant: '#00504a'
  tertiary-fixed: '#eaddff'
  tertiary-fixed-dim: '#d2bbff'
  on-tertiary-fixed: '#25005a'
  on-tertiary-fixed-variant: '#5a00c6'
  background: '#faf8ff'
  on-background: '#131b2e'
  surface-variant: '#dae2fd'
typography:
  headline-xl:
    fontFamily: Plus Jakarta Sans
    fontSize: 1.75rem
    fontWeight: '700'
    lineHeight: 2.25rem
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 1.25rem
    fontWeight: '600'
    lineHeight: 1.75rem
    letterSpacing: -0.015em
  headline-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 1.125rem
    fontWeight: '600'
    lineHeight: 1.5rem
    letterSpacing: -0.01em
  title-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 0.9375rem
    fontWeight: '600'
    lineHeight: 1.375rem
    letterSpacing: -0.005em
  body-default:
    fontFamily: Inter
    fontSize: 0.875rem
    fontWeight: '400'
    lineHeight: 1.25rem
    letterSpacing: 0em
  body-medium:
    fontFamily: Inter
    fontSize: 0.875rem
    fontWeight: '500'
    lineHeight: 1.25rem
    letterSpacing: 0em
  body-compact:
    fontFamily: Inter
    fontSize: 0.8125rem
    fontWeight: '400'
    lineHeight: 1.125rem
    letterSpacing: 0em
  label-default:
    fontFamily: Inter
    fontSize: 0.75rem
    fontWeight: '600'
    lineHeight: 1rem
    letterSpacing: 0.02em
  label-compact:
    fontFamily: Inter
    fontSize: 0.6875rem
    fontWeight: '700'
    lineHeight: 0.875rem
    letterSpacing: 0.04em
  code-time:
    fontFamily: Inter
    fontSize: 0.8125rem
    fontWeight: '600'
    lineHeight: 1rem
    letterSpacing: -0.01em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  gutter: 1rem
  gutter-compact: 0.5rem
  margin: 1.5rem
  margin-compact: 1rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 0.75rem
  space-lg: 1rem
  space-xl: 1.5rem
  space-2xl: 2rem
---

## Brand & Style

This design system powers internal operations for a high-volume dental healthcare environment in Argentina. The audience comprises dental receptionists, practice managers, hygienists, and odontologists operating under tight patient turnarounds. The interface balances high data density with clinical serenity, mitigating operational stress through clarity, predictable interaction models, and unequivocal legibility.

The aesthetic fuses **Clinical Functionalism** with **Modern Enterprise SaaS**. It avoids decorative frivolity in favor of structural precision: cool slate foundations, surgical white operational planes, and high-visibility status taxonomies. The visual tone is authoritative, hygienic, and precise—reassuring staff during rapid scheduling triage, double-bookings (*sobreturnos*), and treatment chair allocations.

## Colors

The palette is engineered around high semantic differentiation and rigorous accessibility (WCAG AA/AAA compliance) against surgical lighting and varied display outputs.

### Foundations & Surfaces
- **Canvas Base**: Cool Gray 50 (`#F8FAFC`) forms the ambient working backdrop, reducing glare during 8-hour shifts.
- **Surface Panels**: Crisp White (`#FFFFFF`) isolates cards, schedule grids, and patient records.
- **Surface Elevation Muted**: Slate 100 (`#F1F5F9`) serves as column dividers, inactive time blocks, and header tracks.
- **Borders & Dividers**: Slate 200 (`#E2E8F0`) for crisp structural partitions; Slate 300 (`#CBD5E1`) for interactive element boundaries.

### Primary Clinical Accents
- **Primary Teal (`#0D9488`)**: Primary actions, selected navigation states, active treatment chair highlights.
- **Deep Teal Shade (`#0F766E`)**: Hover and active states for primary interactive controls.
- **Teal Tint Substrate (`#CCFBF1`)**: Low-strain background wash for completed clinical milestones.

### Clinical Scheduling Status Palette
Every operational status possesses a paired foreground (text/icon) and surface (tinted background) to ensure instant visual triage across multi-chair day views:
- **Reservado (Scheduled / Unconfirmed)**: Text `#2563EB` | Surface `#DBEAFE` | Border `#93C5FD`
- **Confirmado (Patient Confirmed)**: Text `#16A34A` | Surface `#DCFCE7` | Border `#86EFAC`
- **Atendido (Completed In-Chair)**: Text `#0D9488` | Surface `#CCFBF1` | Border `#5EEAD4`
- **Ausente (No-Show)**: Text `#D97706` | Surface `#FEF3C7` | Border `#FCD34D`
- **Cancelado (Void / Strikethrough)**: Text `#DC2626` | Surface `#FEE2E2` | Border `#FCA5A5`
- **Sobreturno (Urgent Squeeze-in / Overbook)**: Text `#7C3AED` | Surface `#EDE9FE` | Border `#C4B5FD` (Accompanied by a 2px left border accent)

## Typography

Typography prioritizes tabular clarity and high scan rates. **Plus Jakarta Sans** provides structural elegance and geometric certainty across major headings, module headers, and doctor/operatory identifiers. **Inter** acts as the high-legibility workhorse for the schedule grid, patient labels, DNI/insurance details, and micro-badges.

- **Tabular Numerals (`font-variant-numeric: tabular-nums`)**: Compulsory across all appointment time blocks, patient contact strings, and payment fields to prevent layout jitter during data updates.
- **Schedule Compactness**: In appointment cells, patient names take `body-medium` (13px equivalent), medical aid (*obra social*) labels take `label-compact` uppercase, and times use `code-time`.
- **Text Truncation**: Ellipsis is enforced with accompanying tooltip indicators to avoid vertical cell overflow in dense 15-minute slot configurations.

## Layout & Spacing

The target platform is a desktop canvas calibrated specifically for 1440px displays, common across modern clinical workstations.

### Grid & Layout Structure
- **Global Shell**: Fixed-width or responsive-contained canvas with a 240px persistent collapsible sidebar (navigating between *Agenda*, *Pacientes*, *Liquidaciones*, and *Configuración*).
- **Schedule Grid Architecture**: A rigid multi-column system where columns represent clinical operatories (*Sillones 1–4*) or practitioners. Slot heights conform to a 48px baseline (representing 30-minute intervals) and subdivide into 24px sub-intervals (15-minute procedures).
- **Gutter and Margin Disciplines**: 
  - Standard container padding uses `margin` (`1.5rem` / 24px).
  - Inter-column gaps in the schedule grid use `gutter-compact` (`0.5rem` / 8px) to maximize horizontal data density across simultaneous chairs without edge collision.
- **Rhythm**: Spacing conforms strictly to a 4px modular scale (`space-xs` through `space-2xl`), eliminating arbitrary pixel offsets.

## Elevation & Depth

This system intentionally departs from heavy drop shadows to preserve a sterile, surgical dashboard tone. Depth is communicated primarily through **calibrated low-contrast borders** and **tonal surface separation**, backed by featherweight ambient shadows only when managing elevated modal workflows.

- **Level 0 (Base Canvas)**: Cool Gray 50 (`#F8FAFC`). Flat.
- **Level 1 (Panels & Schedule Cells)**: Pure White (`#FFFFFF`) with a 1px solid border in Slate 200 (`#E2E8F0`). Flat surface contrast.
- **Level 2 (Hover & In-Grid Drag)**: Lifted appointment cards on drag-to-reschedule receive `box-shadow: 0 4px 12px -2px rgba(15, 23, 42, 0.08), 0 2px 6px -1px rgba(15, 23, 42, 0.04)` and scale to `z-index: 10`.
- **Level 3 (Popovers, Context Menus & Quick-Actions)**: `box-shadow: 0 10px 24px -4px rgba(15, 23, 42, 0.10), 0 4px 8px -2px rgba(15, 23, 42, 0.04)`, bordered with Slate 300 (`#CBD5E1`).
- **Level 4 (Patient Turn Modals & Overlays)**: Backed by an authoritative slate scrim `rgba(15, 23, 42, 0.45)` with `backdrop-filter: blur(2px)`. The modal container employs `box-shadow: 0 20px 32px -8px rgba(15, 23, 42, 0.16)`.

## Shapes

The interface embraces a **Soft (Level 1)** shape grammar. Controlled, tighter radii (`0.25rem` / 4px base, `0.5rem` / 8px containers) preserve internal real estate within high-density scheduling grids and data tables. Rounder forms are avoided, as they waste valuable cell area and introduce visual softness unsuitable for an analytical clinical SaaS.

- **Inputs, Buttons, Micro-Badges**: 4px border-radius (`rounded`).
- **Cards, Filter Bars, Data Panels**: 8px border-radius (`rounded-lg`).
- **Patient Quick-Inspect Modals & Drawers**: 12px border-radius (`rounded-xl`) on outer vertices.
- **Status Indicators (Pills)**: Full pill (`rounded-full`) exclusively used for high-visibility operational tags (e.g., *Confirmado*, *Sobreturno*).

## Components

### Buttons & Interactive Controls
- **Primary Action (e.g., "Nuevo Turno")**: Solid Teal (`#0D9488`), text white, font-weight 600. Hover: `#0F766E`. Active: `#115E59`. Focus ring: 2px Teal at 50% opacity with 2px offset.
- **Secondary Action (e.g., "Exportar Agenda")**: Background white, border 1px Slate 300 (`#CBD5E1`), text Slate 700 (`#334155`). Hover: background Slate 50 (`#F8FAFC`), border Slate 400.
- **Icon Micro-Actions**: 28x28px interactive areas in appointment cards (e.g., Quick WhatsApp Confirmation, Reschedule, Check-in) using muted Slate 500 (`#64748B`), shifting to primary teal on hover.

### Appointment Schedule Cards (The Core Grid Unit)
- **Base Canvas**: Compact card seated inside the time/chair grid.
- **Structure**: 
  - 3px solid color-coded left accent bar tied directly to the appointment status.
  - Line 1: `code-time` (e.g., `10:30 - 11:00`) and Status Chip right-aligned.
  - Line 2: Patient Name (`body-medium`, Slate 900) + Alert icons (e.g., medical allergies, first consultation).
  - Line 3: Treatment & Coverage (e.g., *Endodoncia • OSDE 310*) in `label-compact` Slate 500.
- **Cancelado State**: Background `#FEF2F2`, border `#FCA5A5`, text `#991B1B` with patient name struck through (`text-decoration: line-through`).
- **Sobreturno Highlighting**: Bordered with a distinct dashed/solid Violet (`#7C3AED`) frame, `#EDE9FE` background, and a prominent badge: `SOBRETURNO`.

### Status Badges & Chips
- **Geometry**: Compact height (20px), padding `0 6px`, radius 9999px (pill).
- **Semantics**:
  - `Reservado`: Blue text `#1D4ED8` on Blue tint `#DBEAFE`.
  - `Confirmado`: Green text `#15803D` on Green tint `#DCFCE7`.
  - `Atendido`: Teal text `#0F766E` on Teal tint `#CCFBF1`.
  - `Ausente`: Amber text `#B45309` on Amber tint `#FEF3C7`.
  - `Cancelado`: Red text `#B91C1C` on Red tint `#FEE2E2`.
  - `Sobreturno`: Purple text `#6D28D9` on Violet tint `#EDE9FE`.

### Schedule Header & Operatory Switcher
- Persistent horizontal bar above the grid displaying the selected date navigation (day/week view toggle, datepicker) and dentist/chair column headings.
- Column headers include the practitioner name, specialty (*Periodoncia*, *Ortodoncia*), assigned chair number, and daily occupancy percentage indicator (e.g., `85% Ocupado`).

### Input Fields & Search Bars
- Standard input height: 36px (compact desktop scale).
- Background `#FFFFFF`, 1px border Slate 300 (`#CBD5E1`), font size `0.875rem`. Focus state transitions border to Primary Teal (`#0D9488`) with zero layout shift.
- Universal search input includes inline prefix icon and a keyboard shortcut hint (`⌘K` / `Ctrl+K`) for rapid patient lookup by DNI, surname, or phone number.