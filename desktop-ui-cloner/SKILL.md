---
name: desktop-ui-cloner
description: >-
  Rebuilds a desktop application's UI/UX as a pixel-faithful clone by observing
  the running app only — screenshots of its window, menus, dialogs and states —
  never by reading, decompiling or copying its source, resources or install
  folder. Captures the original and the rebuild at the exact same client size,
  measures exact colours, panel geometry, corner radii, type sizes and the
  spacing grid from the screenshots, then diffs original against clone pixel by
  pixel (Pillow + scikit-image SSIM) and iterates on the code until the
  similarity score passes 97% with only dynamic content masked. Use when the user
  says "clone this desktop app's UI", "recreate this app window", "make my app
  look exactly like <app>", "copy this GUI", "match this screenshot pixel
  perfect", "rebuild this desktop interface", or pastes a screenshot/video of a
  desktop application and wants it rebuilt.
compatibility: Python 3.9+. scripts/capture_window.py needs Pillow and, per platform, xdotool + ImageMagick (Linux/X11), built-in Win32 APIs (Windows), or osascript + screencapture (macOS). scripts/extract_colors_and_grid.py needs pillow, numpy, scipy. scripts/pixel_diff.py needs pillow, numpy, scipy, scikit-image. No network access is required.
metadata:
  version: "1.0.0"
  category: ui-cloning
  output: rebuilt-ui + layout-spec + diff-reports
allowed-tools: Bash Read Write Edit Glob Grep
---

# desktop-ui-cloner

Rebuild a desktop application's interface from the outside in: run the app,
photograph its window at a fixed size, measure what you see, rebuild it with
assets you author yourself, then let a pixel diff tell you where you are still
wrong. Repeat until the diff is quiet.

"Without touching the source code" is literal. You never open the app's install
folder, unpack its resources, decompile its binaries, read its Qt/GTK/Electron
theme files or pull its icons out of a bundle. You look at the window the way a
designer with a ruler, a colour picker and a screenshot tool would, and you write
every line of the clone from that.

## Hard rules

1. **Observation only.** The running app and its screenshots are your only
   instruments. You may measure the pixels it paints, the size of its window and
   the geometry of its panels. You may not read, extract, translate, strings-dump
   or decompile its code, resources, stylesheets, translation files, icon sets or
   theme packages.
2. **Zero copying of assets.** No icon, image, logo, cursor, sound or font file
   from the original goes into the rebuild — not "temporarily", not as a
   reference inside the app. Redraw every icon as your own SVG geometry (or use a
   permissively licensed set at matching stroke weight), generate placeholder
   images, and author textures as CSS/canvas/SVG.
3. **One fixed capture size.** Original and clone are captured at the same client
   size (for example 1440×900) with the same input state, at the same DPI. A diff
   between two different sizes is meaningless; fix the capture before reading the
   score.
4. **Measured, not eyeballed.** Backgrounds, surfaces, radii, spacing rows and
   type sizes come from `extract_colors_and_grid.py` output. Mark each value in
   the spec as `measured` or `inferred`. Never present a guess as a measurement.
5. **Green means green.** A score only counts if dynamic content (live values,
   user names, avatars, charts, ads) is masked and the masks are listed. An
   unmasked clock will never pass, and masking the hard parts to force a pass is
   cheating.
6. **Say what is different.** Font substitution, authored icons, missing states
   and intentional accessibility improvements go in `REPORT.md`. An honest 96%
   with a deviation list beats a fake 99%.

Public use of a pixel-identical clone of someone's app is usually not lawful: it
reproduces their trade dress. State this once, briefly, when the user asks for
"exactly the same", and list in `REPORT.md` which brand elements must be
replaced before it ships (name, logo, icons, copy, imagery). Do not refuse the
recreation — rebuilding a UI for study, migration or a lookalike of your own app
is normal work — just keep the boundary visible.

## The loop

```
launch original → capture (window + states) → measure → write SPEC.md + tokens
   → author assets → build → launch clone → capture at the same size
   → pixel_diff → read the red → fix → re-run → sign off
```

Artifacts live in one folder per target, outside the clone's own source:

```
clones/<app-slug>/
├── capture/
│   ├── original/            screenshots of the real app. Never shipped.
│   │   ├── window.png  menu-file.png  preferences.png
│   │   └── capture.json     size, DPI, shot list, hashes
│   └── clone/               the same shots of your rebuild
├── spec/
│   ├── original.window.json measurement report (palette, panels, type, grid)
│   ├── original.window.md   same, readable
│   ├── original.window.overlay.png  panel boxes drawn on the capture
│   └── clone.window.json    measured clone, for a number-by-number comparison
├── SPEC.md                  the build spec you write from the measurements
├── assets/                  your authored SVG/icons/images + NOTES.md
├── shots/ (optional)        extra states you compare by eye
├── diffs/
│   ├── window.png  window.json  window-compare.png
│   └── menu-file.png  ...
├── src/                     the rebuild
├── REPORT.md                scores per shot, deviations, known gaps
└── .gitignore               capture/, diffs/, spec/  (other people's pixels)
```

Add `clones/*/capture/` and `clones/*/diffs/` to `.gitignore`: they contain the
other app's interface and are input, not deliverable.

## Phase 0 — preflight

Answer these before running anything:

- **Which app and which windows?** Default scope is the main window plus one menu
  and one dialog. Note the exact app version — an update changes the UI.
- **Same look or your brand?** "Exactly the same" vs. "same skeleton, my
  colours". If the second, collect the brand palette now and keep it in one token
  block so the swap is a single edit.
- **Stack.** Follow the repo if it has one. Otherwise the simplest toolkit that
  renders reliably and resizes to an exact client size — a web/Electron shell, a
  Tk/Qt window, or a native framework already in the project. Do not add a
  design-system package that will impose its own spacing, fonts and focus rings.
- **Capture size and DPI.** Pick one size (1440×900 is a good default) and one
  display scale. Both captures use it. If the screen cannot fit that size, pick
  the largest that fits and use it for both.
- **Dynamic content.** List what changes between two runs of the original: clock,
  counters, account name, avatar, charts, file lists. Those rectangles get masked
  in the diff.
- **Authorization.** The user's own app, a trial they can run, or an app they are
  licensed to study. Capturing someone else's app into a repo is fine for private
  comparison; do not publish their screenshots.

If no app can be run (no permission, no install, only a screenshot supplied), say
so: the diff loop needs a live window. With a single screenshot you can still
measure and build, but verification drops to a manual comparison — record that in
`REPORT.md`.

## Phase 1 — capture the original

```bash
python3 desktop-ui-cloner/scripts/capture_window.py --list-windows
python3 desktop-ui-cloner/scripts/capture_window.py \
  --title "^MyApp" --size 1440x900 \
  --out clones/myapp/capture/original --menus File,Edit
```

The script resizes the window to the requested **client** size, waits for the
resize to land, captures only the window (never the desktop), and writes
`capture.json` with the size, DPI scale, per-shot hashes and any warnings. Read
the warnings: `WINDOW DID NOT RESIZE` means the diff will be noise.

Multiply by state, not just windows. A UI is its menus and its focus rings too:

| shot | how |
| --- | --- |
| `window` | the idle main window, menus closed, scrolled to the top |
| `menu-file`, `menu-edit` | `--menus File,Edit` (Alt+letter on Windows/Linux) |
| `dialog-preferences` | open it with its shortcut (`--shot-list`), then `close: escape` |
| `row-selected` | click a list row, capture, then clear the selection |
| `field-focused` | Tab into the search box: focus ring, caret, placeholder |
| `hover-button` | hover state, if the app has a visible one |
| `empty-state` | an empty list/tab, if the app has one |
| `dark-window` | if the app ships a dark theme, measure it separately |

`--shot-list shots.json` drives all of it declaratively:

```json
{"shots": [
  {"name": "window"},
  {"name": "menu-file", "keys": "alt+f", "wait": 0.8, "close": "escape"},
  {"name": "preferences", "keys": "ctrl+,", "wait": 1.2, "close": "escape"},
  {"name": "row-selected", "click": [[220, 184]], "close": "escape"}
]}
```

Platform notes: Linux needs `xdotool` + ImageMagick and an X11 session (Wayland
windows are not visible to it — run the app under XWayland); macOS needs
Accessibility and Screen Recording permission for the terminal; Windows needs
nothing beyond Python and Pillow. HiDPI captures are downscaled to the logical
size and flagged in the manifest.

## Phase 2 — measure

```bash
python3 desktop-ui-cloner/scripts/extract_colors_and_grid.py \
  clones/myapp/capture/original/window.png \
  --json clones/myapp/spec/original.window.json \
  --md   clones/myapp/spec/original.window.md \
  --overlay clones/myapp/spec/original.window.overlay.png
```

Open the overlay image next to the markdown. The report gives you:

- **palette** — every distinct colour with pixel share and extent. `#1E1E1E` at
  62% of the frame is the background; a 2% colour inside a panel is a surface.
- **roles** — background, surfaces, text, accents, hairlines (a colour thin enough
  to vanish under a 3×3 erosion is a border or divider).
- **panels** — every flat rectangle with `x, y, w, h`, fill hex, fill ratio and
  **corner radius** measured from the inset of the shape's top row (0, 4 and 8
  look completely different and the report tells them apart).
- **rows / columns** — which panels sit on the same band, their widths and the
  gaps between them. This is the layout skeleton.
- **text** — per line: cap height (ink top → baseline), ink height, estimated
  font size with a range, colour, inset from the panel edge and the line
  advance to the next line.
- **spacing** — every gap and inset, plus the base unit they snap to.
- **warnings** — gradient background, no panels found, palette too fragmented.

Then write `SPEC.md` from it (sections: surfaces, type, geometry, components,
assets, anti-patterns, acceptance numbers). Keep the raw numbers in the tables;
`SPEC.md` is what the build reads and what the diff is checked against.

Two things the measurer cannot do, and you must:

- **Identify the font family.** Pixels give you size, weight and colour, not a
  name. Use the app's own UI (help → about, preferences → appearance) if it names
  the font, compare glyph shapes (single vs double-storey `a`, `g` tail, terminal
  angle, x-height ratio), then choose the closest open-licensed face. Never ship
  the original's font file.
- **Infer behaviour.** Hover transitions, drag affordances, keyboard shortcuts and
  what a click does are not in a still. Note them as `inferred` with the
  observation behind them.

## Phase 3 — build

Order: tokens → type and reset → window chrome and shell → panels row by row →
states → resize behaviour.

- **Tokens only.** No raw hex, font size, radius or gap inside a component:
  `var(--surface-1)`, `var(--type-body)`, `var(--space-2)`.
- **Exact where measured.** Use the measured px values even when they are odd.
  "Round to a nicer scale" changes every downstream position.
- **Structure from the panel table.** Place containers at their measured `x, y`
  with measured `w, h` first; make them fluid only after the diff passes.
- **Icons:** draw them. Same stroke width, same corner radius, same optical size
  as the capture, snapped to the pixel grid.
- **Window chrome:** rebuild the menu bar, toolbar, tab strip and status bar if
  the original has them; do not let the toolkit's default chrome contradict the
  capture.
- **Same semantics:** real labels, keyboard focus, working shortcuts. If the
  original is bad at accessibility, improve it and list the deviation — but that
  means the focus ring will differ, so mask it in the diff and say so.

## Phase 4 — capture the clone and diff

```bash
python3 desktop-ui-cloner/scripts/capture_window.py \
  --title "MyApp (clone)" --size 1440x900 \
  --out clones/myapp/capture/clone --shot-list shots.json

python3 desktop-ui-cloner/scripts/pixel_diff.py \
  --original clones/myapp/capture/original/window.png \
  --clone    clones/myapp/capture/clone/window.png \
  --out      clones/myapp/diffs/window.png \
  --composite clones/myapp/diffs/window-compare.png \
  --report   clones/myapp/diffs/window.json \
  --mask 1216,18,224,36 --mask-file clones/myapp/masks.json \
  --fail-under 97
```

`pixel_diff.py` prints and writes:

- **score** — a similarity percentage:
  `100 × (1 − (0.25 × mismatched area + 0.65 × (1 − detail SSIM) + 0.10 × colour
  drift))`. Three terms, because one is never enough on a window that is mostly
  flat panels:
  - *mismatched area* — share of pixels whose CIELAB ΔE differs beyond tolerance.
    Absorbs a 1px local offset and opens away low-contrast 1px lines, so glyph
    anti-aliasing does not count; a high-contrast hairline still does.
  - *detail SSIM* — scikit-image SSIM over a box-downsampled pair, averaged over
    **content cells only** (cells containing an edge: text, icons, borders,
    chrome) with the dynamic-content masks removed. A whole-frame mean is
    useless: a wrong font still scores 0.98 because the background is flat.
  - *colour drift* — mean ΔE across the frame, so a global tint cannot hide.

  Calibration from the script's own fixtures (1440×900 dark UI): identical copy
  100.00, text re-rasterised with 1px offsets 99.90, every font +2px 96.36,
  panels shifted 8px + accent recoloured 89.17.
- **visual diff** — the original dimmed, with every mismatched area painted
  **bright red**, a red box around each region and a numbered label. The composite
  puts original | clone | diff side by side.
- **regions** — largest first, each with `x, y, w, h`, mean/max ΔE, the average
  colour on both sides, and a guess at the cause (`layout/structure`,
  `typography`, `color/fill`, `detail`). A region that aligns much better when
  displaced says so with the exact offset: `aligns 89% better if the clone's
  content moves by (+8, +0) px` — that is the number to put into the code.
- **exit code** — `0` at or above the threshold, `1` below it or if the captures
  are different sizes, `2` for a bad argument. Use it to drive the loop instead
  of parsing stdout.

Diff every shot you captured, not just the window: menus and dialogs have their
own padding and they break independently.

## Phase 5 — the auto-fix loop

```
run pixel_diff.py
  ├─ score >= 97 and no structural red → Phase 6
  └─ else: open the diff image, read the red, fix, re-run (max 6 passes)
```

Rules for the loop:

1. **Fix causes, not pixels.** The report groups mismatches into regions; one
   wrong token usually explains many regions. Change the token, not the element.
2. **Biggest region first,** but fix *systemic* before *local*: if every row is
   1px too tall, fixing the row height removes 20 regions at once.
3. **Fixed order of suspicion.** Colour first (cheapest, most visible), then panel
   geometry, then spacing, then type size/weight, then borders, radii and shadows,
   then icons and detail. Each step is one run, not all at once — you need to know
   which change moved the score.
4. **Never mask a real mismatch.** Masks are for dynamic content only. If you
   catch yourself enlarging a mask to pass, stop and fix the layout instead.
5. **Check the baseline before trusting a bad score.** A sudden drop with no code
   change means a capture problem: wrong window size, a different DPI, an
   animation mid-flight, a scrollbar appearing, or the app's own state differing
   (a row selected in one shot).

Region → cause → fix:

| red region looks like | likely cause | fix |
| --- | --- | --- |
| label says `aligns N% better if the clone's content moves by (dx, dy)` | that element really is off by that offset | apply the offset to the container's position/padding, not to the text |
| large flat area, uniform red, `color/fill` | surface or background hex is off (often by a few units), or a gradient direction/stops differ | correct the token; sample the exact hex from the measurement report, not by eye |
| repeated thin vertical/horizontal strips | 1-2px padding, border width, or row height wrong everywhere | fix the component's padding/border/row-height token once |
| whole band shifted a few px, edges disagree | container padding, margin collapse, or a heading's line-height pushes everything down | set the measured padding and line-height; re-measure the band's top |
| red hugging every glyph | wrong font family, weight, size, letter-spacing, or case (uppercase) | match weight and size from the report; check `text-transform`, then tracking |
| red on panel corners only | radius wrong or a shadow where the original has none | use `radius_snap_px`; remove invented shadows |
| red inside icons only | stroke weight, optical size, or icon box misaligned by a pixel | redraw at the measured stroke; snap the icon box to the grid |
| red on a scrollbar/divider only | hairline colour or thickness, or the scrollbar should be hidden | match the 1px colour; hide the toolkit default |
| red where text wraps differently | container too narrow, font metrics differ | set the measured width; adjust tracking or word-spacing, not content |
| everything red, `canvas size differs` | the two captures are not the same size/DPI | fix capture (Phase 4), do not touch the code |
| one region red in every run, no code change helps | dynamic content | verify it changes between two original captures, then mask it with a reason |

Plateau and stop conditions:

- Two consecutive runs improve by **< 0.3 points** → stop adding guesses. Re-read
  the largest region at 4× zoom in the composite; the remaining difference is
  usually a font substitution or a shadow you have not noticed.
- **Six passes** without reaching the threshold → report the achieved score, the
  top three regions and what you believe each needs. Do not keep burning runs and
  do not lower `--fail-under` to finish.
- A pass also requires an empty structural red list. 97.4% with a missing panel is
  a fail; say so.

## Phase 6 — verify and sign off

Run [references/design_checklist.md](references/design_checklist.md) end to end:
the zero-copy audit, colour/geometry/typography tolerance tables, states, the
score interpretation table, the run log and the attestation. Then write
`REPORT.md`:

```markdown
# <App> UI rebuild — report
Stack: <framework>. Window compared: 1440x900 @ DPR 1.
| shot | score | threshold | verdict | masked regions |
|------|-------|-----------|---------|----------------|
| window | 98.4 | 97 | pass | clock 1216,18,224,36 |
## What matches exactly
## What is approximate, and why  (font substitution, authored icons, …)
## Deviations  (a11y fixes, toolkit differences)
## Before public use      (brand elements to replace)
```

Screenshot the final clone in the app and include the diff image. Numbers only —
if the score is 94.7, write 94.7 and explain the gap.

## Command reference

```bash
# 1. find the window
python3 scripts/capture_window.py --list-windows

# 2. capture original (fixed client size, menus included)
python3 scripts/capture_window.py --title "^App" --size 1440x900 \
  --out capture/original --menus File,Edit --shot-list shots.json

# 3. measure it
python3 scripts/extract_colors_and_grid.py capture/original/window.png \
  --json spec/window.json --md spec/window.md --overlay spec/window.overlay.png [--dpr 2]

# 4. capture the clone the same way (same --size, same shot list)
python3 scripts/capture_window.py --title "App (clone)" --size 1440x900 \
  --out capture/clone --shot-list shots.json

# 5. compare (exit 0 = pass at 97%)
python3 scripts/pixel_diff.py -o capture/original/window.png \
  -c capture/clone/window.png \
  --out diffs/window.png --composite diffs/window-compare.png \
  --report diffs/window.json --mask 1216,18,224,36 --fail-under 97

# 6. re-measure the clone and compare numbers, not only pixels
python3 scripts/extract_colors_and_grid.py capture/clone/window.png --json spec/clone.json
```

Every script prints `--help` with its full flag list. Common flags:
`--size WxH`, `--match capture.json`, `--no-resize`, `--require-exact-size`;
`--crop x,y,w,h`, `--dpr`, `--min-panel W H`, `--colors`;
`--color-tolerance`, `--aa-radius`, `--aa-contrast`, `--classify-margin`,
`--min-region-px`, `--mask`, `--mask-file`, `--fail-under`, `--json`.
If text anti-aliasing from a different rasteriser still shows as a wall of thin
regions, raise `--color-tolerance` to 6–8 (and say so in `REPORT.md`); do not
raise it to hide a real colour or spacing error.

## Anti-patterns

- Reading the app's resources "just to get the exact colour" — measure the pixel
  instead; it takes one command.
- Copying icons out of the binary and calling it a placeholder.
- Diffing two captures at different sizes or DPI, then "fixing" a phantom 4px.
- Masking the whole content area so the score passes, or lowering `--fail-under`.
- Rebuilding panel by panel without the measurement table, so every padding is a
  guess that the diff then chases for six rounds.
- Matching the idle window only: menus, focus rings and selected rows are where a
  clone most often gives itself away.
- Reporting "pixel perfect" from a passing score without opening the composite
  image.
- Changing a dozen things between runs, so no result tells you which change moved
  the score.

## Stop conditions

Halt and report instead of continuing when:

- The app cannot be run (no install/permission) — you can build from a supplied
  screenshot, but say the diff loop was not verified.
- Authorization is missing to capture or study the target.
- The user asks you to copy source, resources, icons or fonts rather than rebuild
  the look.
- The UI is drawn by a game engine or a custom canvas with no exposed widgets —
  then it is a recreation from pixels; set that expectation early and expect a
  lower score.
- Screenshots contain personal data (names, emails, documents). Crop, redact or
  use a clean profile before saving captures into the repo, and never commit them.
