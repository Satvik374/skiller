# DESIGN.md template

Copy this into `clones/<slug>/DESIGN.md` and fill it in. Delete nothing that
applies; an empty row is a finding, not a chore. Mark every value
`measured`, `inferred` or `deviated` at the end of the row where it is not
obvious.

---

# <Site name> — UI clone spec

- **Source:** <url> — captured <date>
- **Scope:** <pages / sections>
- **Reference viewport:** 1440×900 · also captured 768×1024, 390×844
- **Goal:** <pixel-faithful replica for study / same skeleton with my brand>
- **Stack:** <html+css+js / next / vite …>
- **Capture:** `reference/` (never shipped). Screenshots are reference only.

## 1. Surfaces

| # | surface | value | area | where | note |
|---|---------|-------|------|-------|------|
| 1 | page background | `#______` | full | html/body | measured |
| 2 | header band | `#______` | 1440×72 | fixed top | translucent + blur 12px |
| 3 | hero band | `#______` | 1440×720 | section 1 | gradient, angle/stops below |
| 4 | card | `#______` | 380×240 | feature grid | 1px border `#____` |
| … | | | | | |

Gradients and overlays:

```
hero overlay: linear-gradient(180deg, rgba(0,0,0,0) 0%, rgba(0,0,0,.55) 100%)
hero backdrop: radial-gradient(60% 50% at 20% 10%, #____ 0%, transparent 70%), ...
grain: feTurbulence baseFrequency .8, opacity .06
```

## 2. Type

| role | original (confidence) | substitute | size | line | ratio | weight | tracking | case | colour |
|------|----------------------|-----------|------|------|-------|--------|----------|------|--------|
| display | <name> (high) | Inter | 72px | 76px | 1.06 | 600 | -0.03em | none | `#____` |
| h1 | | | 48px | 54px | | 600 | -0.02em | | |
| h2 | | | 36px | 44px | | 600 | | | |
| lead | | | 20px | 30px | | 400 | | | |
| body | | | 16px | 26px | | 400 | | | |
| small | | | 14px | 20px | | 400 | | | |
| label | | | 12px | 16px | | 600 | 0.08em | uppercase | |
| button | | | 15px | 20px | | 500 | | | |

Loaded faces and weights: <list>. Fallback stack: <stack>.

## 3. Layout system

- Container: `max-width: ___; padding-inline: ___;` measured content width ___.
- Base spacing unit: ___px (derived from ___ repeats). Scale: <list>.
- Section paddings: top ___ / bottom ___ (varies per section: see below).
- Grid: <12-col? asymmetric? gap __>.
- Breakpoints: ___ / ___ / ___ (measured declarations; behaviour confirmed by
  re-capture).

### Section map

| # | section | y | h | bg | container | columns | gap | pad-y |
|---|---------|---|---|----|-----------|---------|-----|-------|
| 1 | header | 0 | 72 | `#__` | 1200 | flex | 32 | 0 |
| 2 | hero | 72 | 720 | `#__` | 1200 | 2 (56/44) | 64 | 96 |
| … | | | | | | | | |

## 4. Components

One block each. Every state you saw; add focus, disabled and error even if the
original hides them.

```
Button
  variants   primary, secondary, ghost
  box        h 44, pad 0 20, radius 10
  type       button role, 15/20, 500
  colours    bg accent, text on-accent, border transparent
  hover      bg accent-600, translateY(-1px), 150ms ease-out
  focus      2px ring accent at 2px offset
  active     translateY(0), bg accent-700
  disabled   opacity .5, pointer-events none
  icon       16px, gap 8, currentColor
  used on    hero, nav, CTA band
```

## 4b. Interaction states

One row per control, or per control group when several controls only re-trigger
the same state. Every `clicked` control from `reference/interactions/` appears
here; every `skipped` control appears in §8 under "Unobserved controls".

| # | page | control (path / label) | trigger | observed result | screenshot | measured values |
|---|------|------------------------|---------|-----------------|------------|-----------------|
| 1 | / | `body > header button#menu` — "Menu" | click | drawer slides in from the right | `reference/interactions/index/shots/003-menu-after.png` | drawer 420px, bg `#__`, shadow `0 20px 60px rgba(...)`, 240ms ease-out |
| 2 | / | `#faq button:nth-of-type(2)` — "How it works" | click | accordion row expands, icon rotates 180° | `.../007-how-it-works-after.png` | expanded h 164px, gap 12px, 180ms |
| 3 | /pricing | `[role=tab]` — "Annual" | click | prices swap to annual, badge appears | `.../011-annual-after.png` | tab underline 2px, badge 20px pill |
| … | | | | | | |

Coverage: `__` clicked + `__` skipped = `__` discovered. Source:
`reference/interactions/index.json`.

## 5. Assets

| file | stands in for | role | box | method | visible difference |
|------|---------------|------|-----|--------|--------------------|
| | | | | | |

## 6. Motion

| element | trigger | property | from → to | duration | easing |
|---------|---------|----------|-----------|----------|--------|
| hero h1 | load | opacity, translateY | 0/16px → 1/0 | 600ms | cubic-bezier(.2,.8,.2,1) |
| cards | scroll in | opacity, translateY | 0/24px → 1/0, stagger 80ms | 500ms | ease-out |
| nav links | hover | color | muted → text | 150ms | ease |

Reduced motion: <what is disabled>.

## 7. Anti-patterns

Phrase each so it is checkable. These are things the original deliberately does
not do; if they appear, the clone is wrong.

- No drop shadows on cards — surfaces are separated by 1px borders only.
- No rounded corners above 12px, except the pill buttons (999px).
- No centred body copy; only the hero heading is centred.
- No colour transitions on section backgrounds, only on links and buttons.
- No gradient buttons; gradients appear only in the hero backdrop.
- No icon set mix: all icons are 1.5px stroke, 20px.
- No more than two font families.

## 8. Deviations

| # | what | why | impact |
|---|------|-----|--------|
| 1 | typeface substituted | original licensed | tracking tuned; widths within 2% |
| 2 | hero photo replaced | cannot reuse | same crop, grade and scrim |
| 3 | focus rings added | a11y | visible only on keyboard |

### Unobserved controls

Controls the interaction run skipped. Their behaviour is unknown, not inferred.
Copy the reason from `manifest.json`.

| # | page | control | reason | what would settle it |
|---|------|---------|--------|----------------------|
| 1 | / | `button#delete-account` | destructive-action | ask the user; do not click |
| 2 | / | `form#newsletter button[type=submit]` | form-submit | test with a disposable address, or ask |
| … | | | | |

## 9. Acceptance checklist

- [ ] page background hex equals the measured value exactly
- [ ] every surface in §1 present with its exact hex
- [ ] section order and top offsets match §3 within 4px at 1440×900
- [ ] container width and column counts match at 1440, 768, 390
- [ ] every type role matches §2 in size, weight, tracking and case
- [ ] line widths of the three longest headings within 2% of the reference
- [ ] radii, borders and shadows match per component
- [ ] hover, focus, active, disabled, open states behave the same
- [ ] every `clicked` control in `interactions/index.json` appears in §4b with
      its screenshot and measured values
- [ ] every `skipped` control appears in §8 "Unobserved controls" with a reason
- [ ] menus, modals, drawers, tabs, toggles and accordions match the captured
      after-states, not just the resting page
- [ ] `index.json.complete` is true, or the shortfall is explained in `REPORT.md`
- [ ] no horizontal scroll where the reference has none
- [ ] all assets authored, `assets/NOTES.md` complete, zero target URLs in the build
- [ ] screenshot diff ≥ 90 per viewport, or the shortfall explained
- [ ] keyboard pass works, no console errors
