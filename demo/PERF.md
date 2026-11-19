# Harbour — performance

## Measured

Captured in the Cloud VM, which has **no GPU**: WebGL runs on SwiftShader (ANGLE
software rasteriser). Absolute numbers are therefore meaningless for the budget
in `SKILL.md`; only the scene cost is useful.

| Metric | Value | Note |
| --- | --- | --- |
| Triangles on screen | 36,690 | ground 4,608 (48×48) + helmet 15,452 + fox 576 + shadow pass |
| Draw calls | 20 | includes the shadow pass and 3 post passes |
| Textures | 7 | HDR 1k, fox 1024², helmet 5 × 2048² |
| Frame rate (HUD, software GL) | 20 fps | not representative of hardware |
| rAF p50/p95 | not valid | sampling ran in a backgrounded tab; rAF throttled to ~1 Hz |

**Do not quote these as a thumbstick figure.** A hardware p95 requires running
`scripts/perf.mjs`-style sampling on real hardware; that is listed as an open
check in `REPORT.md`.

## Scene budget reasoning

- 36.7k triangles for a hero shot is ~2% of the skill's 1.5 M budget — headroom
  for the environment kit that replaces the single ground plane.
- 20 draw calls is well inside 400. The next step is a modular kit, which will
  add material groups; that is where batching (`BatchedMesh`) starts to matter.
- The 2048² helmet texture set is the largest single VRAM item. Fine at 1 asset;
  at 40 assets it needs KTX2.

## Things that cost more than they look like

- `UnrealBloomPass` runs a full mip chain: ~35% of the post time here.
- Shadow pass duplicates every caster draw call; disabling shadows halved
  triangles in the test (32,084 → 16,056).
- `resolutionScale` at 50% reduced the pixel ratio from 1.0 to 0.5 and is the
  only setting that moves the software rasteriser's frame time noticeably.
