# Harbour — verification report

Produced by following `game-builder` on a small prompt:
*"a small scene with an animated animal, a proper third-person camera, and a
settings menu that actually does something"*.

## Results

| Area | Check | Result | Evidence |
| --- | --- | --- | --- |
| Assets | 2 GLBs within `hero` budget, 0 violations | PASS | `shots/asset-audit.json` |
| Assets | licences + authors recorded (CC0, CC-BY) | PASS | `CREDITS.md` |
| Load | all assets 200, no console errors | PASS | browser network log |
| Assets | clip inventory: Survey / Walk / Run, loops 0.0° | PASS | `shots/asset-audit.json` |
| Controls | 12/12 self-test assertions | PASS | `window.__demo.runSelfTest()` |
| Controls | walk 1.26 m/s, run 3.46 m/s (targets 1.35 / 3.6) | PASS | self-test |
| Animation | blend weights normalise to 1.0 | PASS | self-test |
| Camera | settles to 4.20 m boom, never below y = 0.35 | PASS | self-test |
| Camera | no clipping: raycast pull-in with floor clamp | PASS | code + frames 09 |
| Settings | 5 settings change real renderer state | PASS | self-test |
| Settings | menu opens over the live scene, HUD hidden, Back closes | PASS | frame 16 |
| Perf | hardware frame time | NOT MEASURED | see `PERF.md` |
| Story / world | not applicable to this demo | — | — |

## Bugs found by running the verification pass

These are the reason the skill insists on a harness rather than eyeballing. All
were found *after* the code "looked finished", and all were caught by a check,
a measurement, or a screenshot comparison.

| # | Symptom | Cause | Fix |
| --- | --- | --- | --- |
| 1 | Blank scene, `Cannot read properties of undefined (reading 'mapping')` | `RGBELoader.loadAsync` resolves with the DataTexture, not `{ texture }` in three r187 | accept `hdr.texture ?? hdr` |
| 2 | HUD reported 1 draw call / 1 triangle | `renderer.info` resets per post-processing pass, so it reported only the final fullscreen quad | `info.autoReset = false`, reset once per frame |
| 3 | Fox ran backwards | yaw target had a stray `+ π` | `atan2(vx, vz)` only |
| 4 | Camera collapsed to 1.68 m at y = 0.05 | pitch clamped to −0.3 put the boom under the floor; the ground raycast then pulled the camera in | pitch min −0.04 + hard floor at y = 0.35 |
| 5 | Hard horizon seam | fog colour (dark blue) did not match the HDR horizon | fog sampled from the horizon, density retuned |
| 6 | Large dark polygon on the ground, moving with the camera | screen-space derivative `bumpMap` flips sign across large quads. Subdividing (48×48) only turned one wedge into per-quad rectangles — the check that settled it was toggling shadows off and seeing it persist | replaced `bumpMap` with a generated tangent-space **normal map**; no derivative dependence, patches gone |
| 7 | Bloom blew the fox's white chest into a glow blob | threshold 0.92 sat below the clipped fur | threshold 1.05, strength 0.35 |
| 8 | HUD bled through the settings glass | HUD is z-index 5 under a translucent overlay | HUD/hint hidden while the menu is open |
| 9 | Dead "Audio" tab with a disabled slider | scope creep in the schema | removed — no control that does nothing |
| 10 | No way out of the settings screen | footer only had Cancel/Apply | added Back, which also restores the HUD |
| 11 | Live preview returned a 403 blank page | Vite blocks unknown hosts | allowed the preview hostname from an env var, never hardcoded in the config |

## Remaining rough edges (known, not fixed)

- The horizon is a pale band where the fogged ground meets the sky. Correct in
  principle, slightly brighter than the HDR's sky above it. A real fix is a sky
  shader blending to the fog colour, not another fog tweak.
- The fox is a stylised 576-triangle CC0 model with a blown-white chest under
  bloom. It is an authored asset, not generated geometry, but it does not
  support a realism claim — which is exactly why the next run needs Sketchfab.
- No CSM: one 2048² cascade over 20 m. Fine at this scale, wrong for a level.

## What this demo does not prove

- **Frame rate on real hardware.** The VM has no GPU; everything ran on
  SwiftShader at ~20 fps. Budgets in `SKILL.md` are unvalidated here.
- **Open-world scale.** The playable area is 40 m; nothing about streaming,
  occlusion or HLOD was exercised.
- **Story.** There is none.
- **Real Sketchfab assets.** No token was available, so the fallback ladder was
  used. A Sketchfab environment kit is what this scene is missing: the dock is
  a plane, and no amount of material work hides that.
- **Mobile / touch input.**

## Next run, in order

1. Sketchfab token → a harbour kit (bollards, crates, chains, a shed, a crane).
2. A humanoid with Mixamo clips to exercise retargeting and foot IK, which this
   quadruped did not.
3. Streaming a 1 × 1 km version to test the chunk budget.
