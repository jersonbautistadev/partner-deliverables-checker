# Design System Master File

> **LOGIC:** When building a specific page, first check `design-system/pages/[page-name].md`.
> If that file exists, its rules **override** this Master file.
> If not, strictly follow the rules below.

---

**Project:** Partner Deliverables Checker
**Generated:** 2026-11-21 21:22:23
**Category:** General
**Token files:** `tokens.json` (W3C Design Tokens Community Group JSON).
**CSS variables:** `tokens.css` (`:root` custom properties).
Token files are master-level only; `--page` overrides do not emit tokens.
**Design Dials:** Variance 8/10 (Bold / Asymmetric) | Density 7/10 (Standard)

---

## Project decisions (override the generated rules below)

Generated with UI/UX Pro Max (`"bold vibrant energetic" --design-system --variance 8
--density 7`), then refined with the owner by comparing rendered dashboards. The live
implementation is `static/app.css`; the values below win over the generated tables.

- **Palette (owner-selected):** rose header `#E11D48`; burgundy primary buttons
  `#9F1239` (white text 8.0:1, hover `#881337`); page `#FFF1F2`; text `#4C0519`;
  muted text `#7F1D3A`; dividers `#FECDD3`; frames and focus `#881337`; yellow
  highlights `#FACC15` (active nav bar, count chips). The generated blue accent
  `#2563EB` was rejected as out of place and is not used.
- **Stat tiles:** solid rose family in order `#E11D48`, `#9F1239`, `#881337`, deep
  wine `#4C0519` (owner replaced black), all with white text (4.7:1 or higher).
- **Block style:** 2px burgundy frames with hard offset shadows (6px; 4px on phones
  and secondary cards), 4px radius, uppercase extra-bold page and section headings.
- **Status colors stay fixed** and are always paired with text: failed `#B91C1C`,
  missing `#A16207`, needs review `#6D28D9`, passed `#15803D`.
- **Header text is white** (4.7:1 on rose); lighter tints such as `#FFE4E6` fall
  below 4.5:1 there and are not used for text.
- **Controls:** input borders `#B4536B` (4.8:1 against white); focus is a 2px burgundy
  outline (white inside the header) plus a soft ring on inputs.
- **Fonts:** Inter (100–900 variable) self-hosted from `static/fonts/` under the
  SIL OFL; no third-party font requests.
- **Not applicable to this app:** the generated landing-page pattern, marketing
  sections and any decorative motion.



### Color Palette

| Role | Hex | CSS Variable |
|------|-----|--------------|
| Primary | `#E11D48` | `--color-primary` |
| On Primary | `#FFFFFF` | `--color-on-primary` |
| Secondary | `#FB7185` | `--color-secondary` |
| On Secondary | `#0F172A` | `--color-on-secondary` |
| Accent/CTA | `#2563EB` | `--color-accent` |
| On Accent/CTA | `#FFFFFF` | `--color-on-accent` |
| Background | `#FFF1F2` | `--color-background` |
| Foreground | `#881337` | `--color-foreground` |
| Card | `#FFFFFF` | `--color-card` |
| Card Foreground | `#881337` | `--color-card-foreground` |
| Muted | `#F0ECF2` | `--color-muted` |
| Muted Foreground | `#475569` | `--color-muted-foreground` |
| Border | `#FECDD3` | `--color-border` |
| Destructive | `#DC2626` | `--color-destructive` |
| On Destructive | `#FFFFFF` | `--color-on-destructive` |
| Ring | `#E11D48` | `--color-ring` |

**Color Notes:** Vibrant rose + engagement blue

### Typography

- **Heading Font:** Outfit
- **Body Font:** Work Sans
- **Mood:** geometric, modern, clean, balanced, contemporary, versatile
- **Google Fonts:** [Outfit + Work Sans](https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=Work+Sans:wght@300;400;500;600;700&display=swap)

**CSS Import:**
```css
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=Work+Sans:wght@300;400;500;600;700&display=swap');
```

### Spacing Variables

*Density: 7/10 — Standard*

| Token | Value | Usage |
|-------|-------|-------|
| `--space-xs` | `4px` / `0.25rem` | Tight gaps |
| `--space-sm` | `8px` / `0.5rem` | Icon gaps, inline spacing |
| `--space-md` | `16px` / `1rem` | Standard padding |
| `--space-lg` | `24px` / `1.5rem` | Section padding |
| `--space-xl` | `32px` / `2rem` | Large gaps |
| `--space-2xl` | `48px` / `3rem` | Section margins |
| `--space-3xl` | `64px` / `4rem` | Hero padding |

### Shadow Depths

| Level | Value | Usage |
|-------|-------|-------|
| `--shadow-sm` | `0 1px 2px rgba(0,0,0,0.05)` | Subtle lift |
| `--shadow-md` | `0 4px 6px rgba(0,0,0,0.1)` | Cards, buttons |
| `--shadow-lg` | `0 10px 15px rgba(0,0,0,0.1)` | Modals, dropdowns |
| `--shadow-xl` | `0 20px 25px rgba(0,0,0,0.15)` | Hero images, featured cards |

---

## Component Specs

### Buttons

```css
/* Primary Button */
.btn-primary {
  background: #2563EB;
  color: #FFFFFF;
  padding: 12px 24px;
  border-radius: 8px;
  font-weight: 600;
  transition: all 200ms ease;
  cursor: pointer;
}

.btn-primary:hover {
  opacity: 0.9;
  transform: translateY(-1px);
}

/* Secondary Button */
.btn-secondary {
  background: transparent;
  color: #881337;
  border: 2px solid #E11D48;
  padding: 12px 24px;
  border-radius: 8px;
  font-weight: 600;
  transition: all 200ms ease;
  cursor: pointer;
}
```

### Cards

```css
.card {
  background: #FFF1F2;
  border-radius: 12px;
  padding: 24px;
  box-shadow: var(--shadow-md);
  transition: all 200ms ease;
  cursor: pointer;
}

.card:hover {
  box-shadow: var(--shadow-lg);
  transform: translateY(-2px);
}
```

### Inputs

```css
.input {
  padding: 12px 16px;
  border: 1px solid #E2E8F0;
  border-radius: 8px;
  font-size: 16px;
  transition: border-color 200ms ease;
}

.input:focus {
  border-color: #E11D48;
  outline: none;
  box-shadow: 0 0 0 3px #E11D4820;
}
```

### Modals

```css
.modal-overlay {
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(4px);
}

.modal {
  background: white;
  border-radius: 16px;
  padding: 32px;
  box-shadow: var(--shadow-xl);
  max-width: 500px;
  width: 90%;
}
```

---

## Style Guidelines

**Style:** Brutalism

**Keywords:** Raw, unpolished, stark, high contrast, plain text, default fonts, visible borders, asymmetric, anti-design

**Best For:** Design portfolios, artistic projects, counter-culture brands, editorial/media sites, tech blogs

**Key Effects:** No smooth transitions (instant), sharp corners (0px), bold typography (700+), visible grid, large blocks

### Page Pattern

**Pattern Name:** Hero + Features + CTA

- **Conversion Strategy:** Deep CTA placement. For CTA label text, verify at least 4.5:1 against the button fill; use 7:1 only when the product explicitly targets AAA normal-text contrast. Keep focus and component boundaries independently visible. Disable hero parallax under reduced motion and render its static final state.
- **CTA Placement:** Hero (sticky) + Bottom
- **Section Order:** Hero with headline/image > Value prop > Key features (3-5) > CTA section > Footer

---

## Anti-Patterns (Do NOT Use)


### Additional Forbidden Patterns

- ❌ **Emojis as icons** — Use SVG icons (Heroicons, Lucide, Simple Icons)
- ❌ **Missing cursor:pointer** — All clickable elements must have cursor:pointer
- ❌ **Layout-shifting hovers** — Avoid scale transforms that shift layout
- ❌ **Low contrast text** — Maintain 4.5:1 minimum contrast ratio
- ❌ **Instant state changes** — Always use transitions (150-300ms)
- ❌ **Invisible focus states** — Focus states must be visible for a11y

---

## Pre-Delivery Checklist

Before delivering any UI code, verify:

- [ ] No emojis used as icons (use SVG instead)
- [ ] All icons from consistent icon set (Heroicons/Lucide)
- [ ] `cursor-pointer` on all clickable elements
- [ ] Hover states with smooth transitions (150-300ms)
- [ ] Light mode: text contrast 4.5:1 minimum
- [ ] Focus states visible for keyboard navigation
- [ ] `prefers-reduced-motion` respected
- [ ] Responsive: 375px, 768px, 1024px, 1440px
- [ ] No content hidden behind fixed navbars
- [ ] No horizontal scroll on mobile
