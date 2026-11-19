# Web player — UI clone spec

- **Source:** open.spotify.com web player, observed through a signed-in browser session on 2026-11-16. Never fetched: no HTML, CSS bundles, JS, fonts or images were downloaded or copied.
- **Scope:** the player shell plus every main route: Home, Search (browse + results), Your Library, Playlist, Album, Artist, Show/Podcast, Liked Songs, and the four right-panel tabs (Now playing, Queue, Connect, Lyrics).
- **Reference viewport:** 1440×900 (primary) · checked at 390×844 mobile.
- **Goal:** pixel-faithful replica of layout, type and surfaces, with an invented catalogue and simulated playback (no audio).
- **Stack:** static HTML + CSS + ES modules. No framework, no build step.
- **Capture:** `reference/` (gitignored, never shipped).

Provenance is marked `measured` (from the capture), `inferred` (judgement) or `deviated` (deliberate change).

## 1. Surfaces

| # | surface | value | area | where | note |
|---|---------|-------|------|-------|------|
| 1 | page background | `#000000` | full | body | measured |
| 2 | main view | `#121212` | 848×748 at 1440 | centre panel, radius 8 | measured |
| 3 | sidebar | `#000000` | 280×748, radius 8 | left | measured |
| 4 | right panel | `#121212` | 280×748 | right | measured (radius 8 inferred) |
| 5 | elevated surface | `#1f1f1f` | chips, search field, cards | top bar / panel | measured (`--background-elevated-base`) |
| 6 | tinted base | `rgba(255,255,255,.10)` | shortcut tiles, chips | home | measured (`--background-tinted-base`) |
| 7 | tinted highlight | `rgba(255,255,255,.14)` | hover | rows, chips | measured |
| 8 | tinted press | `rgba(255,255,255,.21)` | active | rows | measured |
| 9 | text | `#ffffff` | — | primary copy | measured |
| 10 | text subdued | `#b3b3b3` | — | secondary copy, icons | measured |
| 11 | essential subdued | `#7c7c7c` | — | borders, disabled | measured |
| 12 | accent | `#1ed760` | play buttons, toggles | global | measured (`--essential-bright-accent`) |
| 13 | negative | `#f3727f` | errors | global | measured |
| 14 | hover row | `rgba(255,255,255,.10)` | 56px rows | tracklists | measured |

Gradients (authored approximations of the reference's artwork-derived headers):

```
page/hero falloff: linear-gradient(180deg, color-mix(in oklab, hsl(var(--h1) 42% 40%) 88%, #fff) 0%, hsl(var(--h1) 34% 24%) 34%, rgba(18,18,18,.66) 78%, #121212 100%)
hero tint:        radial-gradient(120% 90% at 8% 0%, hsl(var(--h2) 60% 50% / .35), transparent 62%)
sticky top bar:   linear-gradient(180deg, rgba(18,18,18,.92) 30%, rgba(18,18,18,0))
cover art:        conic + radial + linear stack over per-item hues (see base.css .art)
```

## 2. Type

Original family is a proprietary UI cut (SpotifyMixUI / SpotifyMixUITitle). Substituted with **Figtree** (open licence) — closest available match for its round, high-x-height grotesque shapes.

| role | original (confidence) | substitute | size | line | weight | tracking | case |
|------|----------------------|-----------|------|------|--------|----------|------|
| hero title | SpotifyMixUITitle (high) | Figtree | 96px → shrinks to fit, min 32 | 1.0 | 800 | -0.045em | none |
| section title | SpotifyMixUITitle (high) | Figtree | 24px | 1.2 | 700 | 0 | none |
| card title | SpotifyMixUI (high) | Figtree | 16px | 1.4 | 500 | 0 | none |
| body | SpotifyMixUI (high) | Figtree | 16px | 1.5 | 400 | 0 | none |
| small | SpotifyMixUI (high) | Figtree | 14px | 1.4 | 400 | 0 | none |
| pill button | SpotifyMixUI (high) | Figtree | 14px | 1 | 700 | 0.01em | none |
| caption | SpotifyMixUI (high) | Figtree | 12px | 1.4 | 400 | 0 | none |
| micro (artist line in player) | SpotifyMixUI (high) | Figtree | 11px | 1.4 | 400 | 0 | none |

Loaded weights: 400, 500, 600, 700, 800. Fallback: `"Helvetica Neue", Helvetica, Arial, system-ui, sans-serif` with `font-display: swap`.

## 3. Layout system

- Shell padding 8px; column gap 8px; row gap 8px.
- Grid: `280px minmax(0,1fr) 280px` measured at 1440; main 848, panel 280.
- Top bar 64px; player bar 72px; panels 748px tall at 900 viewport height.
- Sidebar: library header 59px (`16px 16px 8px`), chips 32px tall, rows 64px with 48px art.
- Spacing base 4px (measured repeats: 4/6/8/12/16/24/32/48/64/96).
- Content padding 24px; shelf cards 154px wide, 16px gap; browse tiles `minmax(180px,1fr)` aspect 1.62.
- Breakpoints (inferred from behaviour, confirmed by resize): 1180px drops the right panel, 900px drops the sidebar and adds the bottom tab bar, 560px trims top-bar and tracklist columns.

### Section map (desktop)

| # | region | y | h | bg | width |
|---|--------|---|---|----|-------|
| 1 | top bar | 0 | 64 | `#000` | 1424 |
| 2 | sidebar | 64 | 748 | `#000` | 280 |
| 3 | main view | 64 | 748 | `#121212` | 848 |
| 4 | right panel | 64 | 748 | `#121212` | 280 |
| 5 | player bar | 820 | 72 | `#000` | 1424 |

### Detail page geometry (measured)

- Header band 270px at the top of the main view, gradient from artwork colour to `#121212`.
- Cover 189–232px, radius 4, `box-shadow: 0 4px 60px rgba(0,0,0,.5)`.
- Hero title 96px/800; meta row 14px.
- Action bar: 56px green play circle, 32px pill, 32px icon buttons.
- Tracklist header 36px with 1px bottom border; rows 56px; columns `16px 4fr 3fr 2fr 64px`.

## 4. Components

```
Card
  box        column, 154px wide, art 1:1 radius 6
  type       title 16/1.4 500, sub 14/1.4 subdued
  hover      art scrim rgba(0,0,0,.18); 48px green play FAB fades up 8px, 150ms
  focus      visible outline on keyboard

Chip / filter pill
  box        h 32, padding 0 12, radius pill
  colours    rgba(255,255,255,.10) → .14 hover; active #fff / #000 700

Shortcut tile
  box        h 56, radius 4, art 56×56 flush left, label 14/700
  hover      rgba(255,255,255,.14)

Track row
  box        h 56, padding 0 12, radius 4, columns per §3
  hover      rgba(255,255,255,.10); number → play icon; heart + ⋯ appear
  current    title in #1ed760

Transport
  play       32px white circle, black glyph, scale 1.06 on hover
  toggles    16px glyphs at 32px hit area; active state #1ed760
  progress   4px rail rgba(255,255,255,.30), white fill, 12px thumb on hover, green on hover

Right panel
  tabs       Now playing / Queue / Connect / Lyrics, 16px glyphs at 32px
  now playing title 24/800, artist 14 subdued, green verified glyph
  cards      #1f1f1f, radius 8, padded 12–16
```

## 5. Assets

| file | stands in for | role | method | visible difference |
|------|---------------|------|--------|--------------------|
| `src/js/icons.js` | every UI glyph | icon | hand-authored SVG on a 24px grid, 1.6–2px strokes | optical weight matched, path shapes differ |
| `src/js/icons.js` `logo` | service mark (32px) | mark | own circle + three arcs | a placeholder mark, not their logo — **must replace** |
| CSS `.art` | album/playlist/artist/podcast covers | image | layered `conic`/`radial`/`linear` gradients + geometry, per-item hue | abstract art instead of photography |
| `.art--liked` | Liked Songs cover | image | gradient + glyph | abstract instead of the original treatment |
| text avatar | account avatar | avatar | initials on `#e8734a` | no photo |
| track/artist/album/show names | real catalogue | content | invented in `content.js` | entirely different catalogue |

Full notes: `assets/NOTES.md`.

## 6. Motion

| element | trigger | property | from → to | duration | easing |
|---------|---------|----------|-----------|----------|--------|
| card play FAB | hover | opacity, translateY | 0/8px → 1/0 | 150ms | cubic-bezier(.3,0,0,1) |
| rows/chips | hover | background-color | base → tinted | 100–200ms | same |
| hero title | load | — | shrinks to fit width | instant | — |
| progress fill | tick | width | position → position | 250ms linear-ish | — |

`prefers-reduced-motion: reduce` disables transitions and animations (deviation: reference does not).

## 7. Anti-patterns

- No drop shadows on cards; only the hero cover, play FABs and overlays carry shadow.
- No card background at rest; hover is a 18% scrim over the art only.
- No radius above 16px except pills and the avatar.
- No second sans family, no serif, no mono.
- No centred body copy; only empty states are centred.
- No gradient buttons; gradients belong to artwork and hero bands.
- No icon mix: one authored set, consistent stroke.
- No light theme; `color-scheme: dark` and `#000` page background.
- No visible horizontal scrollbars inside shelves or the sidebar chip row.

## 8. Deviations

| # | what | why | impact |
|---|------|-----|--------|
| 1 | typeface substituted (Figtree) | original licensed | slightly rounder terminals; sizes/tracking measured |
| 2 | all artwork authored as gradients | cannot reuse their images | covers read as abstract art |
| 3 | logo replaced by an authored mark | trademark | visible difference; flagged must-replace |
| 4 | invented catalogue + demo user | no real account data in a replica | content differs from any real library |
| 5 | playback simulated, no audio | no licensed recordings | progress/queue/lyrics run on a fake clock |
| 6 | focus rings + reduced-motion support | accessibility | visible only on keyboard / reduced-motion users |
| 7 | hero title auto-shrinks | reference does this too, exact algorithm inferred | long titles stay on one line |

## 9. Acceptance checklist

- [x] page background `#000000`, panels `#121212` exactly (measured)
- [x] every surface in §1 present with its exact value
- [x] shell geometry matches at 1440×900: 8px pad, 280/848/280 columns, 64px bar, 72px player
- [x] every type role matches §2 in size, weight and tracking
- [x] radii, borders and shadows match per component
- [x] hover/focus/active/pressed states exist for rows, cards, chips, transport
- [x] no horizontal page scroll at 1440 or 390
- [x] all assets authored; zero target URLs in the shipped bundle
- [x] keyboard pass: space, arrows, `/`, `m`, Escape; visible focus
- [x] no console errors on any route
- [ ] screenshot diff ≥ 90 — not meaningful here: the clone ships a different catalogue, so geometry was verified by measurement instead of pixel diff
