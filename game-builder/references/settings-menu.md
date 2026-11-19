# The settings menu — built like a shipped AAA screen

A settings screen is the most-seen screen in the game and the cheapest place to
prove craft. Do not invent one. **Look at three to five screenshots of shipped
AAA settings menus first**, extract their anatomy, then build.

## Contents

1. Reference gathering
2. Anatomy extracted from AAA menus
3. Design tokens
4. Row types
5. Information architecture (the full settings list)
6. Apply / revert / dirty state
7. Quality presets and what each must change
8. Persistence and schema migration
9. Navigation and accessibility
10. Verification

---

## 1. Reference gathering

Capture, don't guess. Sources that reliably have clean 1080p/4K captures:

- Steam store pages ("View all screenshots") for the game's UI screenshots.
- Official press kits / publisher media pages (search "<game> press kit").
- `gameuidatabase.com`, `interfaceingame.com`, `vgba.se` (screenshot galleries).
- Subreddits / wikis for "settings menu" threads.
- The user's own screenshots, if they play the game.

Save 3–5 into `reference/settings/` (gitignored) and write down, for each:
category placement (left rail / top tabs), row height, control style
(segmented / slider / dropdown / checkbox), whether values show numerically,
footer actions, background treatment, and whether the game renders live behind
the panel.

Recent AAA conventions worth copying (Halo Infinite, Cyberpunk 2077, Horizon,
God of War, RE4, Helldivers 2, Alan Wake 2 all converge here):

- **Left category rail or top tabs**, 4–7 categories, active item marked by a
  filled block or an accent bar — not by colour alone.
- **Dense rows with a label column and a control column**, plus a one-line
  description under the label (or in a fixed tooltip panel at the bottom).
- **Values are visible as numbers**, right-aligned, tabular figures, with the
  unit or `%`.
- **A live 3D preview behind or beside the panel** for graphics settings.
- **A preset selector at the top** of the graphics tab, with a detected badge.
- **"Apply / Revert" or "Back"**, and a "Reset to defaults" that is confirmed.
- **A revert countdown** when a display setting could make the game unplayable
  ("Keep these settings? 14 s").
- **Hairline dividers, small caps section headers, and one accent colour.**
- **A note on settings needing a restart**, marked with a chip.

## 2. Anatomy extracted from AAA menus

Measurements below are from 1920×1080 captures, normalised to a 1080p canvas.
Reuse the proportions, not the pixels, and re-skin to the game's art direction.

| Part | Value | Notes |
| --- | --- | --- |
| Panel inset | 48 px top / 64 px sides | content never touches the edge |
| Category rail | 300–340 px wide | left rail; right-aligned labels, left-aligned icons |
| Rail item height | 52 px | 14 px gap between |
| Active marker | 3 px accent bar + 6% white fill | never colour alone |
| Header | title 28/32, uppercase, 0.14em tracking | subtitle 13 px, 55% opacity |
| Section header | 12 px uppercase, 0.16em tracking, 45% opacity | 32 px above, 12 px below |
| Row height | 56 px (compact) / 64 px (with description) | dividers only between groups |
| Label | 15 px / 500 weight | description 12.5 px, 55% opacity |
| Control column | 260–320 px, right-aligned | consistent width across all rows |
| Divider | 1 px, `rgba(255,255,255,0.07)` | inset 16 px from the right |
| Panel surface | `rgba(10,12,15,0.82)` + 24 px backdrop blur | never pure black |
| Text | `#F2F4F7` primary, `#9AA3AF` secondary | never pure white |
| Accent | one hue, used for focus + active + applied | e.g. `#E8B45A` warm amber |
| Focus ring | 2 px accent, 2 px offset, 4 px radius | visible on every focusable |
| Footer | 72 px, right-aligned Apply / Cancel / Defaults | Apply disabled when clean |
| Scroll | custom thin bar, fades when idle | wheel + drag + stick |

What makes these screens feel premium is mostly **restraint**: one accent, two
text weights, no shadows on flat elements, no gradients on buttons, generous
vertical rhythm, and every row aligned to the same two columns.

## 3. Design tokens

```css
:root {
  --bg-panel: rgba(10, 12, 15, 0.82);
  --bg-rail: rgba(6, 8, 11, 0.55);
  --bg-row-hover: rgba(255, 255, 255, 0.045);
  --bg-row-active: rgba(255, 255, 255, 0.075);
  --line: rgba(255, 255, 255, 0.07);
  --line-strong: rgba(255, 255, 255, 0.14);
  --text: #f2f4f7;
  --text-dim: #9aa3af;
  --text-faint: #6b7280;
  --accent: #e8b45a;
  --accent-dim: rgba(232, 180, 90, 0.18);
  --danger: #e06a5a;
  --radius: 4px;
  --font-ui: "Inter", "Barlow", system-ui, sans-serif;
  --tracking-caps: 0.14em;
  --dur: 140ms;
  --ease: cubic-bezier(0.32, 0.72, 0, 1);
}
```

Rules: **one accent hue**, **two text weights**, **no border radius above
6 px**, **no gratuitous shadows**, **tabular numerals** for values
(`font-variant-numeric: tabular-nums`), and **no emoji / no rounded pill
buttons**. A settings screen with rounded pill toggles and blue accent reads as
a web dashboard — that is the failure mode to avoid.

## 4. Row types

| Control | Use | Implementation notes |
| --- | --- | --- |
| Segmented | 2–4 discrete choices (Low/Med/High) | equal width, active filled with accent-dim + accent text |
| Slider | continuous (sensitivity, FOV) | show number live, keyboard ±1, Shift ±10, drag + wheel |
| Dropdown/select | 5+ options, or long labels | native `<select>` styled, or a listbox for gamepad |
| Toggle | boolean | a 36×20 track with a sliding 16 px knob; label says the positive state |
| Stepper | integer with arrows | resolution scale in 5% steps |
| Keybind | input mapping | click → "Press a key…", conflict detection, Esc cancels |
| Action button | "Benchmark", "Reset", "Delete save" | text button, left-aligned in the control column |

Every control must be operable by mouse, keyboard **and** gamepad, and must
show a focus state. A control that only works with a mouse is a bug in a game.

## 5. Information architecture

Use these six categories. The list is the deliverable — a menu with three tabs
feels like a jam game.

**Display**
Window mode (Fullscreen / Borderless / Windowed) · Resolution · Refresh rate ·
VSync · Frame rate cap · Monitor (multi-display) · HDR (if supported) ·
Brightness calibration (a 3-step pattern screen).

**Graphics**
Quality preset + "Detected: High" chip ·
Resolution scale (50–100%) · Upscaling (Off / TAAU / FSR) ·
Anti-aliasing (Off / FXAA / SMAA / TAA) ·
Textures · Shadows · Shadow cascades · Ambient occlusion ·
Screen space reflections · Volumetrics / fog · Bloom · Depth of field ·
Motion blur (with strength) · Film grain · Lens flare · Chromatic aberration ·
Foliage density · LOD bias · Draw distance · Anisotropic filtering ·
Water quality · Effects quality · Post-processing quality ·
**Benchmark** button · **Reset graphics**.

**Gameplay**
Difficulty (Story / Normal / Hard / Custom) · Combat/damage scaling ·
HUD scale · HUD opacity · Crosshair style · Subtitles on/off + size + background ·
Language · Camera shake · Auto-sprint · Hold vs toggle for crouch/aim/sprint ·
Aim assist (gamepad only) · Tutorial hints · Damage numbers.

**Controls**
Mouse sensitivity (cm/360) · ADS sensitivity multiplier · Invert Y · Invert X ·
Gamepad sensitivity · Gamepad deadzone · Vibration · Button layout /
rebinding table (primary + secondary per action) · Reset controls.

**Audio**
Master · Music · SFX · Dialogue · UI · Dynamic range (Night / TV / Cinema) ·
Subtitles · Mono audio · Output device · Mute on focus loss.

**Accessibility**
UI scale (80–140%) · Text size · High-contrast HUD · Colour-blind mode
(Deuteranopia / Protanopia / Tritanopia + intensity) · Reduce motion
(shake, bob, FOV kick) · Toggle vs hold · Screen reader labels · Subtitle
customisation (size, background, speaker names) · Camera comfort (FOV cap).

Order within a tab matters: **most-likely-to-be-changed first**, then the
expensive stuff, then the diagnostics. Group with section headers ("Image",
"Lighting", "Effects", "Performance").

## 6. Apply / revert / dirty state

Three modes exist in shipped games; pick per project and be consistent:

1. **Live apply + Apply/Cancel footer** (console style). Values preview
   immediately; Cancel restores the snapshot taken on tab entry.
2. **Draft + Apply** (menu style). Nothing changes until Apply; a dot on the
   footer marks dirty state.
3. **Live apply, no cancel** with an undo toast. Only acceptable in small games.

Ship mode 1 or 2, never a mixture. Implementation:

```ts
class SettingsStore {
  private committed: Settings;
  private draft: Settings;
  dirty() { return !deepEqual(this.committed, this.draft); }
  set<K extends keyof Settings>(k: K, v: Settings[K]) {
    this.draft[k] = v;
    this.onPreview?.(k, v);          // live preview through QualityManager
  }
  apply() { this.applyAll(this.draft); this.committed = structuredClone(this.draft); this.save(); }
  cancel() { this.draft = structuredClone(this.committed); this.applyAll(this.draft); }
  defaults() { this.draft = structuredClone(DEFAULTS); this.onPreview?.(...); }
}
```

**The revert countdown** is the detail that makes the screen feel AAA. When a
setting can black-screen the game (window mode, resolution, HDR, upscaler),
apply it with a modal: "Keep these settings? 15" and auto-revert at zero. Bind
the confirm to the same key/button as the menu's confirm.

**Restart-required settings** get a chip and are applied on next boot from the
saved file. Do not pretend they applied.

## 7. Quality presets and what each must change

A preset is a bag of values, never a label:

```ts
const PRESETS = {
  low:    { resolutionScale: 0.66, shadows: 0, ssao: false, ssr: false,
            volumetrics: 0, taa: false, foliageDensity: 0.4, lodBias: 0.5 },
  medium: { resolutionScale: 0.8,  shadows: 1, ssao: true,  ssr: false,
            volumetrics: 24, taa: true, foliageDensity: 0.7, lodBias: 0.75 },
  high:   { resolutionScale: 1.0,  shadows: 2, ssao: true,  ssr: true,
            volumetrics: 40, taa: true, foliageDensity: 1.0, lodBias: 1.0 },
  ultra:  { ...high, shadows: 3, volumetrics: 56, dof: true, lodBias: 1.25 },
};

class QualityManager {
  apply(preset: Partial<Quality>) { /* sets renderer + scene values, then */
    this.onChanged?.();           // triggers shadow map rebuild, LOD refresh
  }
}
```

- Selecting a preset **writes the individual controls** (they become "Custom"
  when edited). Custom is a fifth, derived state.
- Changing any individual control that a preset owns flips the preset label to
  **Custom** — and the label must be honest.
- Presets need to be **measured**: log the frame time after each tier change and
  warn in the console if a tier costs less than 1 ms (that setting is cosmetic).
- **Auto-detect**: 3 s of the opening scene, take p95, pick the highest tier
  that holds 60 fps, store as detected. Offer "Use detected settings" once.

## 8. Persistence and schema migration

```ts
const SCHEMA = 3;
type SettingsFile = { version: number; values: Settings };

function load(): Settings {
  const raw = localStorage.getItem('settings');
  if (!raw) return structuredClone(DEFAULTS);
  const parsed = JSON.parse(raw) as SettingsFile;
  if (parsed.version < SCHEMA) return migrate(parsed, SCHEMA);
  return clampAll({ ...DEFAULTS, ...parsed.values }); // unknown/missing keys
}
```

- **`clampAll` on every load.** A stale file with `resolutionScale: 0` is a
  black screen and an unrecoverable one if you can't reach the menu.
- **Version + migration** from day one; you will add settings.
- **Debounce writes** (250 ms) and write on `apply()`, not per slider pixel.
- **Per-profile storage** if there are profiles; a single slot is fine for one
  player.
- **Ship a `?safe` URL flag** that boots at Low + windowed, and mention it in
  the settings footer as "Startup options". It saves users with a dead GPU
  config and takes ten lines.

## 9. Navigation and accessibility

- Focus is on a **row**, not on the inner control, until you press
  confirm/Enter; arrows change value directly on that row (console behaviour).
- **Left/Right** = previous/next category; **Up/Down** = rows; **Shoulder
  buttons** = tabs too.
- Focus never leaves the panel; Esc/B backs out one level, then out of the menu.
- **No setting may be colour-only**: pair it with a label, icon or check mark.
- Minimum **14 px** text at 1080p, and honour the UI scale setting.
- Contrast: body text ≥ 4.5:1 on the panel surface. Check the dim grey on the
  translucent panel — this is where most dark menus fail.

## 10. Verification

- [ ] Every setting changes something observable; no dead controls
- [ ] Presets change every value their table claims, and flip to Custom
- [ ] Apply / Cancel / Defaults behave exactly as specified, including the
      revert countdown on display settings
- [ ] Settings survive reload, and survive a schema migration from an old file
- [ ] A corrupt/out-of-range settings file falls back without a black screen
- [ ] Whole menu operable with keyboard only, and with a gamepad only
- [ ] Focus ring visible on every row and control; nothing focus-traps
- [ ] Screenshot the built menu next to the AAA references and compare layout
      density, type scale, accent count — list the differences
- [ ] `?safe` boots
- [ ] Frame time re-measured at Low and Ultra and recorded in `PERF.md`

Report the comparison honestly: "layout matches the reference's two-column
density; our accent is used twice where the reference uses it once" is a
useful verdict. "Looks AAA" is not.

`assets/settings-menu.html` implements this anatomy in plain HTML/CSS/JS —
port it, don't redesign from scratch.
