# Build report

## What this is

A study replica of the music web player interface: same shell geometry, surface
palette, type scale and component anatomy, rebuilt from browser measurements.
The catalogue, artwork and audio are not the original's — artists, albums,
episodes and covers are invented, and playback is simulated.

## Verified

- Shell measured against the live reference at 1440×900: 8px padding and gaps,
  280px sidebar, 848px main, 280px right panel, 64px top bar, 72px player bar,
  panels 748px tall, panels radius 8, `#000` page, `#121212` main, `#1f1f1f`
  elevated, `#1ed760` accent.
- Hero header: 189–232px cover with `0 4px 60px` shadow, 96px/800 title that
  shrinks to fit one line, 56px green play button, 36px table header, 56px rows.
- Type roles: 24px/700 section titles, 16px card titles, 14px secondary, 12px
  captions, measured tracking.
- Routes render without console errors: Home, Browse, Search results, Library,
  Playlist, Album, Artist, Show, Liked Songs, and the panel tabs (Now playing,
  Queue, Connect, Lyrics).
- Interaction walked in the real browser: row play, card play FAB, play/pause,
  next/prev, seek, volume, shuffle/repeat, like, queue, panel tabs, search
  typing, library filter chips, playlist creation modal.
- Responsive: 390px hides sidebar and panel, shows the bottom tab bar, no
  horizontal page scroll.

## Approximate

- **Typeface.** Original is a proprietary segmented font family; Figtree is the
  substitute. Sizes, weights and tracking are measured; letterform shapes differ.
- **Artwork.** All covers are authored gradients rather than photography, so
  colour and composition come from the item's hue pair, not a real image.
- **Hero gradient.** The reference derives its header colour from the cover
  image; this build derives it from the same authored hue, so the band matches
  in structure and falloff, not in exact pixels.
- **Right panel.** Geometry and content order are measured; card paddings inside
  the panel are inferred from the 4px scale.
- **Breakpoints** (1180 / 900 / 560) are inferred from resize behaviour, not from
  declared media queries.

## Not verified

- A pixel-diff score against the reference is not meaningful here: the shipped
  page has a different catalogue and different artwork, so any diff score would
  measure content, not fidelity. Geometry was checked with bounding boxes.
- No audio path exists, so nothing about real streaming is tested.
- Only Chromium at 1440×900 and 390×844 was inspected; Safari and Firefox were
  not run.

## Before public use

1. Replace the mark and any wordmark with your own.
2. Replace the catalogue and copy (`site/src/js/content.js`) with licensed or
   your own content.
3. Replace the gradient covers if you need real artwork.
4. Add audio or point the transport at a real player API — the current clock is a
   UI harness only.
