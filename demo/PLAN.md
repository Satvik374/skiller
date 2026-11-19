# Harbour — PLAN

Written per `game-builder` phase 0 before any build work.

| Field | Decision |
| --- | --- |
| Genre | third-person exploration vignette (no combat) |
| Camera | third person, damped spring arm with collision |
| Art direction | realistic dusk harbour, HDR IBL, ACES, wet ground |
| Target | desktop browser, integrated GPU, 1080p, 60 Hz |
| World size | 40 m playable area (a demo, not an open world) |
| Story | none — this is the asset/animation/controls/settings pipeline test |
| In scope | HDR environment, animated character with locomotion blend, hero prop, spring-arm camera, wired settings |
| Out of scope | combat, quests, streaming, NPCs, audio, save games |

## Asset sourcing

No Sketchfab token was available for this run, so the fallback ladder applied
(`references/assets.md` § 4). Every asset was audited before use:

| Asset | Source | Licence | Audit |
| --- | --- | --- | --- |
| `fox.glb` | Khronos glTF Sample Assets (Fox, by PixelMannen) | CC0 | 576 tris, 24 bones, 3 clips, loops 0.0° |
| `helmet.glb` | Khronos glTF Sample Assets (Damaged Helmet, by theblueturtle_) | CC-BY 4.0 | 15,452 tris, 2048² PBR set |
| `dusk_1k.hdr` | Poly Haven (Venice Sunset) | CC0 | 1k equirect, 1.4 MB |
| ground maps | authored procedurally in `main.js` | ours | albedo/roughness/bump |

**Substitution to revisit:** a Sketchfab kit would give the dock actual
architecture (bollards, crates, chains, mooring rings) instead of a bare plane.
The scene reads as a lighting/material test, which is what this run is for.
