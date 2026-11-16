# Authored assets

Nothing in `site/` comes from the observed service. Everything below was made
for this build.

| file | stands in for | role | method | visible difference |
|------|---------------|------|--------|--------------------|
| `site/src/js/icons.js` — every glyph | the site's icon set (16–32px) | icon | hand-drawn SVG geometry on a 24px grid, 1.6–2px strokes, `currentColor` | same optical size and stroke weight, different path drawings |
| `site/src/js/icons.js` — `logo` | the service mark (32px, top-left) | mark | own circle with three curved bars | a placeholder mark; **must be replaced** before public use |
| `site/src/css/base.css` — `.art` | album / playlist / artist / podcast cover photos | image | stacked `conic`, `radial` and `linear` gradients plus ring and hatch geometry, driven by per-item `--h1` / `--h2` hues | abstract gradient art instead of photography |
| `.art--liked` | Liked Songs cover | image | violet→ice gradient with a solid heart glyph | abstract, no photo mosaic |
| `.art--round` | artist portrait crops | image | circular mask over the same authored art | no faces |
| top-bar avatar | account avatar photo | avatar | initial on `#e8734a` | no photo |
| `content.js` catalogue | real artist/track/album/show data | content | invented names, durations and play counts | entirely different catalogue |
| `content.js` lyrics | real lyrics | content | written for this demo | different words, timed to the fake clock |

## How the covers work

A deterministic hue pair per item (`h1`, `h2` on each record) feeds one CSS
recipe: a conic wedge, a radial highlight, a linear base, a ring and a hatch
overlay. That gives every card a distinct, consistent "release artwork" without
a single image file, and it stays crisp at any size.

## What could not be recreated

- **Photography.** Artist and podcast imagery is missing by design; portraits
  would have to be generated or licensed.
- **The mark.** A wordmark/mark placeholder is used and flagged in `DESIGN.md`
  §8 as must-replace.
- **Audio.** No recordings are shipped. The transport, queue, progress and
  lyrics all run against a simulated clock.
- **Fonts.** The original UI face is proprietary; Figtree is substituted at the
  measured sizes and tracking.
