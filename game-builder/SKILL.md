---
name: game-builder
description: >-
  Builds 3D browser games that hold up next to AAA desktop titles — real
  authored assets pulled from Sketchfab and CC0 libraries (never blocky
  AI-generated placeholder geometry), retargeted and verified character
  animation, an open-world-scale level, a scripted story, hand-tuned
  player movement and third/first-person camera, and a settings screen built to
  AAA information architecture. Use this whenever the user asks for a 3D game,
  a WebGL/WebGPU game, "AAA graphics", "high graphics", a realistic or
  open-world game, a game that "doesn't look like a browser game", a playable
  three.js/Babylon scene, a game trailer/prototype, or asks to make any browser
  game look and feel like a real shipped title — even if they never say "AAA".
---

# game-builder

A browser game cannot out-polygon a console. It can still *read* as AAA, because
what makes a frame look expensive is not triangle count — it is correct light,
physical materials, texel density, silhouettes, motion, input feel and a UI
that behaves like a shipped product. Those are all achievable in a tab. The
things that instantly give a browser game away are the opposite: untextured
primitive geometry, flat shading, a camera on rails, characters that slide, and
a settings menu that is six checkboxes.

This skill is a production plan for getting the second list to zero.

## Hard rules

1. **Never ship blocky, untextured, generated geometry as the look.** This is
   the rule that matters most, so it comes first. Do not reach for
   `BoxGeometry`, `CylinderGeometry`, low-poly "stylised" packs, or
   image-to-3D output as the visual language of a scene the user will judge.
   Primitive-and-flat-material scenes are why browser games look like tech
   demos: no bevels to catch light, one flat albedo per surface, uniform
   roughness, no normal or AO detail, no decals, no scale cues. If a prop
   matters to the frame, it comes from a real library — see
   `references/assets.md` and the asset gate below.
2. **Assets come from outside your imagination.** Search Sketchfab (ask the
   user for a token, below), then the CC0 libraries, then a licensed pack.
   Kitbashing authored modules into a new building is fine. Extruding a
   building out of boxes is not.
3. **The token is the user's, and it stays on the server.** Ask for it in the
   first turn after scope, once, in the wording given below. Never put it in
   client code, a committed file, a log or the chat.
4. **Every asset is audited before it enters the build.** Triangle count,
   texture sizes, scale, pivot, skeleton, animation inventory, licence.
   `scripts/glb_audit.py` exists so this takes seconds.
5. **Animation is retargeted and measured, not hoped for.** Clips come from
   Mixamo/mocap or the asset. Bones are remapped, feet are checked against the
   ground, loops are checked at the seam.
6. **Controls and camera are the game.** A perfect frame that stutters when you
   walk is a failed build. Movement is tuned with the numbers in
   `references/controls.md` and verified with the telemetry harness.
7. **The settings menu is a feature with an information architecture**, laid
   out from reference screenshots of shipped AAA menus, not invented.
8. **Report what you verified and what you did not.** "Looks AAA" is not a
   finding. Frame-time p95, a screenshot, a passing input test, an audit table.

## The asset gate

Before modelling anything, ask for the Sketchfab token. Say it once, plainly:

> To make this look like a real game rather than a tech demo I want to pull
> authored assets (characters, props, environment kits, HDRIs) instead of
> generating geometry. Do you have a Sketchfab API token I can use? Sketchfab →
> Settings → Password & API → API token. I'll keep it in `.env` as
> `SKETCHFAB_TOKEN` and use it only from server-side scripts — it never goes
> into the browser bundle or the repo.

Then keep working while you wait — do not stall the whole build on it. If no
token arrives, walk the fallback ladder in `references/assets.md` § Fallbacks
(Poly Haven HDRIs, ambientCG PBR materials, Khronos sample assets, Quaternius,
Kenney, Mixamo for motion) and record the substitution. Never let the ladder
end at "so I made it out of boxes": the last resort is authoring a proper
modular kit with real PBR maps and bevels, not grey boxes.

Storage: `SKETCHFAB_TOKEN` in `.env` (gitignored). Scripts read it from the
environment. The one exception is a shipped *viewer* feature that downloads
models on behalf of a signed-in user — that needs the OAuth flow Sketchfab
documents, not a copied personal token.

## Stack

Follow the repo if it already has one. Otherwise:

| Need | Default | Why |
| --- | --- | --- |
| Renderer | three.js (r170+), `WebGPURenderer` with `WebGLRenderer` fallback | TSL node materials, compute, TAA/SSR nodes, best asset ecosystem |
| Physics | Rapier (`@dimforge/rapier3d-compat`) | WASM, fast, has a kinematic character controller |
| Post | three's own post nodes, or `postprocessing` (pmndrs) | bloom, SSAO, SMAA, DOF, LUT grading |
| Assets | `gltf-transform`, `gltfpack` (meshopt), `sharp` | DRACO/meshopt, KTX2, texture downscale |
| Build | Vite | fast, worker + wasm friendly |
| Audio | Web Audio through `three.Audio` / Howler | positional audio, ducking |

Babylon.js is the alternative when the user wants an editor and built-in
particles/physics; it is a legitimate choice, not a downgrade. Do not build a
custom renderer. Do not use a no-code game tool and then try to make it look
AAA — the ceiling is in the material and lighting pipeline.

## Budgets

These are the numbers that keep a browser frame honest on a mid laptop
(integrated GPU, 1080p, 60 Hz target). Put them in `PERF.md` and check them.

| Budget | Target | Ceiling |
| --- | --- | --- |
| Frame time p50 / p95 | 10 / 14 ms | 16.6 / 22 ms |
| Triangles on screen | 1.5 M | 3 M |
| Draw calls | 400 | 900 |
| Unique materials in a view | 40 | 90 |
| Texture memory resident | 350 MB | 700 MB |
| Single texture | 1024² props, 2048² hero | 4096² skybox/LUT only |
| GLB per prop / per hero | 1 MB / 15 MB | 4 MB / 40 MB |
| Streaming hitch | < 50 ms | 100 ms |
| Time to first playable frame | 8 s | 20 s |

## Phases

Each phase ends with a gate. Do not start the next phase to escape a failing
gate; the failure gets more expensive.

**0 — Contract.** Ten lines in `PLAN.md`: genre, camera (first/third person),
art direction (realism vs stylised realism — not "low poly"), target hardware,
world size, story premise and length, which systems are in, and what is
explicitly out. Ask only what truly blocks this; assume the rest and say so.

**1 — Pipeline spike (half a day).** One hero asset off Sketchfab, audited,
optimised, in a lit turntable scene with HDRI + ACES tonemapping + shadows.
This proves the whole chain before there is a game to break. Gate: the asset
audit passes and the turntable frame would pass for a store screenshot.

**2 — Movement vertical slice.** Capsule, kinematic controller, input layer,
spring-arm camera, one test room built from authored modules. Gate: you can
walk, sprint, jump, crouch and look for two minutes without clipping, sliding,
or a camera pop, and the telemetry harness passes.

**3 — World.** Terrain, streaming chunks, modular kit, set dressing, lighting
and time of day. Gate: a camera tour of the map at six landmarks holds the
frame budget and has no holes.

**4 — Characters and animation.** Player rig, locomotion blend space, one-shots,
NPC rigs, retarget, foot contact. Gate: no T-pose frame, no foot sliding at
walk/run, loop seams under tolerance, clips listed in `ANIMATION.md`.

**5 — Story and systems.** Mission graph, triggers, objectives, dialogue,
save/load, HUD. Gate: the whole story is completable start to finish without
the debug console.

**6 — UI and settings.** Title screen, pause, HUD, and the settings screen from
`references/settings-menu.md`. Gate: every setting actually changes a renderer
value, persists across reload, and is gamepad-navigable.

**7 — Verification and performance.** Full harness, adaptive quality,
`REPORT.md`. Gate: the checklist in `references/verification.md` is green or the
failures are written down.

## References

| Read this | When |
| --- | --- |
| `references/assets.md` | sourcing, licensing, Sketchfab API, optimisation, audit thresholds, fallback ladder |
| `references/rendering.md` | lighting, materials, post stack, LOD/streaming, upscaling, quality tiers |
| `references/animation.md` | retargeting, blend spaces, foot IK, root motion, loop and contact verification |
| `references/world.md` | open-world scale, terrain, modular kits, set dressing, story/quest data |
| `references/controls.md` | input abstraction, character controller numbers, camera rig, tuning and telemetry tests |
| `references/settings-menu.md` | AAA settings anatomy, tokens, control types, apply/revert flow, quality presets |
| `references/verification.md` | definition of done, harness, perf capture, honesty policy |

## Scripts

| Script | Use |
| --- | --- |
| `scripts/sketchfab_fetch.py` | search Sketchfab, download a model's glTF archive, extract, register licence + author |
| `scripts/glb_audit.py` | inspect a GLB/glTF: tris, textures, skeletons, clips, bbox, loop seams; fail on budget |
| `scripts/optimize_assets.sh` | meshopt/DRACO + KTX2 + texture downscale through gltf-transform/gltfpack |

All read `SKETCHFAB_TOKEN` from the environment. Run `--help` first.

## Assets in this skill

`assets/settings-menu.html` is a working reference implementation of the
settings screen described in `references/settings-menu.md` — read it, port its
structure into the project's framework, and re-skin it to the game. It is a
starting point with the right anatomy, not a finished design.

## Anti-patterns

- **"Stylised low-poly" as an excuse.** It is a valid art direction, but it is
  a *decision the user makes*, not an escape hatch for not sourcing assets.
  When in doubt the answer is realism with authored assets.
- **Grey-boxing into the final build.** Grey boxes are a testing tool for
  phase 2 only; they must be gone from any frame you show the user.
- **One big GLB of the whole level.** No culling, no streaming, 300 MB.
- **A fixed camera.** No spring arm, no collision, no shoulder offset, no
  damping — the single strongest "browser demo" tell after blocky assets.
- **Animation by `mixer.clipAction(clip).play()` with no blend.** Snapping
  between idle and run.
- **Settings that are cosmetic.** A "Ultra" preset that changes nothing is
  worse than no setting.
- **Claiming verification you didn't do.** If you did not open the page and
  move the character, say so.

## Output

A playable build, plus: `PLAN.md`, `PERF.md`, `ANIMATION.md`, `CREDITS.md`
(licences and authors, shown in-game too), `assets/registry.json`,
`REPORT.md` with the verification table, and screenshots in `shots/`. End the
chat with what works, what is approximate, what was substituted, and the
measured frame time — not adjectives.
