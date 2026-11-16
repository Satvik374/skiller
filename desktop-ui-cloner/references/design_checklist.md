# Design checklist — does the rebuild actually look like the original?

Printed scores are necessary and insufficient. A rebuild can hit 98% and still be
wrong in ways people notice instantly (a 1px-off baseline, the wrong icon weight,
a border that should not exist). Run this list before you say the clone is done,
and record the result of each line in `REPORT.md`.

Two rules for filling it in:

1. **Evidence, not vibes.** Every "pass" cites a number, a filename or a diff
   region id. "Looks close" is not a result.
2. **Mark deviations, do not hide them.** If you changed something on purpose
   (font licence, an artificial shadow removed, a hit target enlarged for
   accessibility), write it in the deviations table with the reason. A
   documented deviation is fine; an undocumented one is a bug.

---

## 1. Zero-copy audit (gate: must pass before anything else)

The clone must not contain a single byte of the original application.

- [ ] No file was copied, renamed or converted out of the app's install folder,
      resources, bundle, `asar`, `.pak`, `resources.pri`, `.dll`, `.so`, `.qrc`,
      `.icns`, `.ico`, `.dylib` or theme folder.
- [ ] No code, string table, translation file, stylesheet or markup was
      extracted, decompiled or pasted — including "just to read the layout".
- [ ] No icon, image, logo, cursor, sound or font file from the original is in
      the repo. Every icon is drawn by you (SVG, own geometry) or comes from a
      permissively licensed set; every image is generated or licensed.
- [ ] No `data:` blob, base64 string or embedded binary in the source.
- [ ] The clone does not read from the original app at runtime (no IPC, no
      `QFile`/`resources` access, no bundling of its theme, no scraping its
      assets on launch).
- [ ] Brand identifiers (product name, logo, trademark strings) are placeholders
      in your build unless the user owns them.
- [ ] `rg -n 'data:(image|font|video)/[a-z]+;base64' .` returns nothing.
- [ ] `find . -name '*.ico' -o -name '*.icns' -o -name '*.ttf' -o -name '*.otf'`
      only lists fonts you licensed yourself, with their licence files.

If any line fails: stop, delete the artifact, and redraw or regenerate it. Do
not "clean it up later" — later never comes and the diff will not catch it.

## 2. Colour

| what | tolerance | how to check |
| --- | --- | --- |
| window background | **0** — exact hex | `pixel_diff.py` mean ΔE for that region must be 0.00; compare the `background` value in both measurement JSONs |
| panel / surface fills | 0 for flats, ΔE ≤ 2 for gradients | measurement report `roles.surfaces`, both runs |
| text colour | ΔE ≤ 2 | `text[].color` in both reports |
| accent / selection | ΔE ≤ 2 | measure the selected row explicitly (capture that state) |
| border / divider | ΔE ≤ 3, and the same 1px width | zoom the crop to 4x; a missing 1px line is a real mismatch, not noise |

- [ ] The clone's page/panel background hex is identical to the original's, not
      "a shade off". Light greys (`#F5F5F5` vs `#F7F7F7`) are what the eye
      catches first.
- [ ] Dark mode (if the original has it) was measured separately, not derived by
      inverting.
- [ ] Alpha/translucency: if a surface is translucent, both the alpha and what
      shows through were rebuilt.
- [ ] Gradients run in the same direction with the same stops.
- [ ] Disabled/placeholder text uses its own measured colour, not 50% opacity.

## 3. Geometry

| what | tolerance at the same window size |
| --- | --- |
| window client size | exact — both captures must be the same WxH |
| panel x/y | ±1 px |
| panel width/height | ±1 px |
| gaps between panels | ±1 px |
| corner radius | ±1 px (radius is fitted to the anti-aliased corner arc, so ±1 is the honest resolution), and no radius where the original has none |
| border width | exact px |
| text baseline / top of ink | ±1 px |
| row height in lists/tables | ±1 px |
| icon size | ±1 px, same optical alignment |

- [ ] Every panel in the measurement report exists in the clone at the same
      `x, y, w, h` (compare the two JSON reports, not just the picture).
- [ ] Row/column structure matches: same number of columns, same fixed/flex
      behaviour when the window is resized.
- [ ] Spacing uses the measured base unit (usually 4 or 8), not framework
      defaults.
- [ ] Scrollbars, splitters, tab bars and toolbars have the measured thickness.
- [ ] Menu bar / title bar / traffic lights are rebuilt or hidden deliberately
      (note which), not left as the toolkit default if the original differs.
- [ ] At the minimum window size the layout still matches the original's
      behaviour (min size, wrapping, scroll).

## 4. Typography

- [ ] Family is the closest available substitute, chosen by category first
      (grotesque vs. geometric vs. humanist), then by metrics. Recorded as a
      substitution with the licence.
- [ ] Size, weight, line-height, letter-spacing, case and alignment per role are
      the measured values, not rounded to a "nice" scale.
- [ ] Ink height of a sample string in the clone is within ±1px of the original
      at the same size (crop both, overlay, zoom).
- [ ] No fallback font flash, no synthesised bold/italic, no tofu glyphs.
- [ ] Truncation/wrapping happens at the same width, with the same ellipsis.
- [ ] Numbers in tables/labels: tabular figures if the original aligns columns,
      same weight.

## 5. Assets, icons, states

- [ ] Every icon is redrawn to the original's stroke weight, corner treatment and
      optical size (compare at 4x zoom against the capture; "same shape" is not
      enough — stroke weight is what reads as "off").
- [ ] Icons are pixel-aligned to the grid (no half-pixel blur).
- [ ] Images and photos are your own generated/licensed stand-ins with matching
      crop, focal point, aspect and colour treatment.
- [ ] Hover, focus, active, selected, disabled, pressed and open states all exist
      and were captured and compared — not just the idle window.
- [ ] Keyboard focus ring matches the original's style (colour, width, offset) or
      is intentionally improved and documented.
- [ ] Empty, loading and error states look like the original's (or are documented
      as unimplemented rather than silently blank).
- [ ] Menus open in the same place, with the same item height, padding,
      separators, shortcuts column and checkmark position.

## 6. Behaviour that changes the look

- [ ] Resizing the window reflows exactly like the original (test the same two
      sizes you captured).
- [ ] Scroll positions, sticky headers and frozen rows/columns behave the same.
- [ ] Animations/transitions: duration and easing within ~20%, or absent in both.
- [ ] Tooltips/dropdowns/popovers appear at the same offset with the same shadow.
- [ ] DPI scaling: at 125%/150% the layout still holds (no clipped text).

## 7. Reading the score

The score is `100 × (1 − (0.25 × mismatched area + 0.65 × (1 − detail SSIM) +
0.10 × colour drift))`: mismatched area catches colour and spacing, detail SSIM
(computed over content cells only, dynamic masks removed) catches text, icons and
layout, colour drift catches a global tint. Reference points measured on the
script's own fixtures — use them to sanity-check a number that looks surprising:

| score | reference point / what it usually means |
| --- | --- |
| 100.00 | byte-identical captures |
| ≥ 99.5 | Near-identical. Text re-rasterised with 1px anti-aliasing offsets measures ≈ 99.9. Ship it. |
| 97 – 99.5 | Passing. Red is concentrated in glyph AA, icon interiors and long gradients. Glance at the diff to confirm no structural red before accepting. |
| 92 – 97 | Typically one systemic error: every font +2px measures ≈ 96.4, a surface colour a shade off, or a 2px padding error repeated in every row. Find the repeated region, not each instance. |
| 85 – 92 | Panels shifted 8px with a recoloured accent measures ≈ 89. Spacing or type scale is wrong, or a band is missing. |
| < 85 | Structural: different window chrome, missing panels, wrong column count, or the two captures are not the same size / DPI. Fix capture first. |

A substituted font sets a ceiling: if glyph shapes differ from the original, the
detail term stays low no matter how clean the layout is. That is a real
difference, not noise — record it as a deviation and report the achieved score.

A pass is `score >= --fail-under` **and** an empty structural red list **and** the
manual sections above. The score is computed with dynamic regions masked; what is
masked must be listed in `REPORT.md` with its rectangle, or the pass is
unverifiable.

## 8. Run log

Keep one row per iteration. This is how you tell "still improving" from "stuck".

| # | score | what changed | red regions before → after | note |
|---|-------|--------------|----------------------------|------|
| 1 | | initial build | | |
| 2 | | | | |
| 3 | | | | |

Stop when: score ≥ threshold, or two consecutive runs improve by < 0.3 points, or
six iterations have run. On a plateau, re-read the largest diff region and the
deviation list — the blocker is usually a mismatch you decided to ignore.

## 9. Attestation

```markdown
# Clone verification — <APP NAME>

Date: <YYYY-MM-DD>    Skill: desktop-ui-cloner 1.0.0
Original: <app + version>   Rebuild: <stack>
Window size compared: <W>x<H> @ DPR <n>

## Scores
| shot | score | threshold | masked regions |
|------|-------|-----------|----------------|
| window |  | 97 |  |

## Copy audit
- [x] no code, resources, icons, fonts or images taken from the original
- [x] every icon redrawn; every image generated or licensed
- scans run: <command> → <result>

## Deviations
| area | original | rebuild | reason |
|------|----------|---------|--------|

## Known gaps
<states not built, regions masked, behaviours unverified>

Signed: <name / agent id>
```

This checklist is engineering guidance, not legal advice. Cloning an
application's look for study or for a lookalike is normal practice; shipping it
under the original's name or trade dress is not. When the rebuild is meant to be
public or commercial, tell the user to get their own legal review.
