# Rendering — the frame that reads as AAA

## Contents

1. Renderer configuration
2. Image-based lighting and sky
3. Materials
4. Shadows
5. Post-processing stack
6. Colour grading and LUTs
7. Culling, LOD, instancing
8. Adaptive quality and upscaling
9. Frame budget anatomy
10. Quality tiers

---

## 1. Renderer configuration

Get these right before any art passes; each of them is a "browser demo" tell
when wrong.

```ts
const renderer = new WebGPURenderer({ antialias: false, alpha: false });
await renderer.init();                       // falls back to WebGL2
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.0;          // tune per scene, 0.8–1.4
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5)); // 2.0 is a trap
```

- **Always tonemap.** ACES (or AgX for a filmic look) is what stops highlights
  clipping to white and is the single cheapest "expensive render" upgrade.
  Raw linear output is the number one reason browser scenes look like a
  viewport rather than a game.
- **Antialias at the post level**, not MSAA on the default framebuffer, once
  you have an HDR pipeline. SMAA or TAA on an HDR float target.
- **Render HDR.** `HalfFloatType` target in linear space, tonemap at the end of
  the chain. Bloom and SSAO need the extra range to look right.
- **Pixel ratio cap 1.5.** Retina at 2.0 quadruples fragment cost for a
  difference nobody sees in motion.
- **Never `setPixelRatio` on every resize**, and handle `resize` with a
  debounce + `renderer.setSize(w, h, false)` so CSS owns the canvas box.

## 2. Image-based lighting and sky

IBL is the highest-value asset in the whole project. A Poly Haven HDRI at
1–4k (`.hdr`) run through `PMREMGenerator` gives every material in the scene a
correct environment in one line.

```ts
const pmrem = new THREE.PMREMGenerator(renderer);
const env = await new RGBELoader().loadAsync('/assets/hdri/golden_hour_2k.hdr');
scene.environment = pmrem.fromEquirectangular(env.texture).texture;
scene.environmentIntensity = 1.0;   // dial per time of day
scene.backgroundBlurriness = 0.15;  // if using the HDRI as the sky
```

- **Physical sky beats a painted skybox** for an open world: `Sky` /
  `SkyMesh` with sun elevation and turbidity, plus a matching `scene.fog`
  colour sampled from the horizon so distant geometry dissolves instead of
  ending at a hard edge.
- **Match fog to the sky.** Fog `#A8B4C0` against a peach horizon is an
  instant giveaway.
- **Add one directional sun** with a warm colour and a cool ambient fill
  (`HemisphereLight` sky/ground), and keep the sun in the same direction as the
  HDRI's sun. Two conflicting suns look wrong to every viewer even if they
  cannot name why.
- **Exposure per time of day.** Drive `toneMappingExposure` from the sun
  elevation curve so night is not a blue-lit day.

## 3. Materials

- **`MeshPhysicalMaterial` for hero surfaces**: `clearcoat` on car paint and
  wet stone, `sheen` on cloth, `iridescence` on oil/soap, `transmission` only
  on glass you actually need (it re-renders the scene — budget 2–3 objects).
- **AO from the texture.** Bake AO into the model during asset prep (or into
  vertex colours) and multiply it in; `aoMap` alone needs a second UV set.
- **Normal maps: tangent space, `flipY = false` for glTF**, and set
  `normalScale` per material — downloaded normal maps are often too strong.
- **Detail maps** on large surfaces (terrain, walls, floors) at a second UV
  scale. Without them a wall is a smear at 1 m and tiled noise at 20 m.
- **Triplanar mapping** for terrain and rock so slopes never stretch.
- **Vertex-colour blending** between two material sets (concrete/dirt,
  road/grass) using a mask in vertex alpha — this is how modular kits avoid a
  visible seam at every joiner.
- **Decals** (`DecalGeometry` or a projected transparent mesh) for posters,
  grime, bullet holes, road markings. They cost almost nothing and add more
  perceived detail than another 100k triangles.
- **Avoid** `MeshBasicMaterial` anywhere except debug, unlit emissive strips
  and sky. It is the flattest possible look.

## 4. Shadows

- **CSM (cascaded shadow maps)**: 2–3 cascades, 2048² each, λ ≈ 0.7, covering
  10 m / 40 m / 150 m. A single 2048 map over a 200 m world is mush.
- **Tighten the shadow frustum to the camera**, not the level.
- **Contact shadows** (or a cheap SSAO pass) for the last metre, where CSM
  resolution fails.
- **VSM** when you need soft, cheap, blurred shadows on foliage; PCFSoft for
  crisp architecture.
- **Bias discipline**: `bias -0.0005`, `normalBias 0.02`–`0.05` scaled by mesh
  size. Peter-panning (shadows detached from feet) is very visible on
  characters — check the feet specifically.

## 5. Post-processing stack

Order matters: geometry → SSAO → SSR → volumetrics → bloom → TAA/SMAA → DOF →
motion blur → tonemap → LUT → grain/vignette/CA → UI (untouched).

| Effect | Why it reads AAA | Cost | Notes |
| --- | --- | --- | --- |
| Bloom (selective) | emissives glow like a camera saw them | low | threshold ~0.9 in HDR, mip chain; selective so the HUD never blooms |
| SSAO / GTAO | contact darkening in corners | med | radius 0.5–1.5 m scaled to scene, half-res |
| SSR | wet roads, puddles, marble | high | half-res + roughness fade, or fake with a reflection probe |
| Volumetric fog / god rays | depth and scale | med–high | ray-march 32–48 steps at half res |
| TAA | kills shimmer on foliage and fences | med | needs jitter + velocity; ghosts on thin geometry — clamp history |
| DoF | separates subject from background | med | use for cutscenes and ADS only, not gameplay |
| Motion blur | speed | low | camera-only blur is acceptable; per-object needs a velocity buffer |
| Film grain + vignette + subtle CA | photographic cohesion | almost free | keep grain ≤ 0.03 or it looks like compression noise |
| LUT grade | the "movie look" | free | see below |

Turn effects **off** in motion tests before tuning them, then add back one at a
time — a stack that hides bugs will ship those bugs.

## 6. Colour grading and LUTs

Author a `.cube` LUT per biome/time-of-day (lift/gamma/gain + saturation
curve) and apply it as the last colour step. This is how a flat render becomes
a *look*. Exposure-matched, one LUT per lighting state, blended over 2 s when
the time of day changes. Do not stack a CSS filter over the canvas — it
captures the UI too and murders text contrast.

## 7. Culling, LOD, instancing

- **Frustum culling** is free; keep object bounding volumes tight and correct
  (a merged level mesh has one useless bound → never merge the whole level).
- **Occlusion culling**: WebGPU timer/occlusion queries or a portal/room graph
  for interiors. In a city, occlusion is worth more than any shader.
- **Instancing** for anything repeated >20 times: `InstancedMesh` for props and
  foliage, `BatchedMesh` (or merge by material) for static kit pieces.
- **LOD**: switch by screen-space projected size, not raw distance, and
  cross-fade over 8% of the range. Foliage: 3 LODs + billboard.
- **Streaming**: 64–128 m tiles, async load with `KHR_meshopt` workers, upload
  budget ≤ 2 MB/frame, always keep a 1-tile fallback so the player never sees
  a hole.

## 8. Adaptive quality and upscaling

- **Resolution scale** 0.6–1.0 driven by a rolling p95 frame time. This is the
  single most effective safety valve on integrated GPUs; implement it in phase
  1, not at the end.
- **Temporal upscaling**: render at 0.7× and use TAA with jitter (or the
  `FSR`-style node) to reconstruct. Set expectations: it is not DLSS.
- **Hysteresis**: change tiers on 3 consecutive bad seconds, upscale on 5 good
  ones, or the image pumps visibly.
- **Never change tier during a cutscene or a load**, and never mid-air.

## 9. Frame budget anatomy

Target 16.6 ms at 1080p on integrated graphics:

| Stage | Budget |
| --- | --- |
| CPU: input, animation, physics, scripts | 3.0 ms |
| CPU: culling, draw submission | 1.5 ms |
| GPU: shadow cascades | 2.0 ms |
| GPU: opaque + alpha-test | 5.0 ms |
| GPU: transparent + particles | 1.5 ms |
| GPU: post chain | 3.0 ms |
| Slack | 0.6 ms |

Measure with `renderer.info` (calls, triangles, textures, geometries) and
`timestamp-query` when available. Log a 20 s window at each landmark and keep
the numbers in `PERF.md`. A single number from one frame is not a measurement.

## 10. Quality tiers

Every tier must change a real value. Wire them through one `QualityManager`
(see `references/settings-menu.md` § Quality presets):

| Setting | Low | Medium | High | Ultra |
| --- | --- | --- | --- | --- |
| Resolution scale | 0.66 | 0.8 | 1.0 | 1.0 |
| Shadow cascades / res | 1 / 1024 | 2 / 1024 | 3 / 2048 | 3 / 2048 |
| SSAO | off | half | full | full |
| SSR | off | off | half | full |
| Volumetrics | off | 24 steps | 40 | 56 |
| TAA | off (SMAA) | on | on | on |
| Texture filter | bilinear | trilinear | aniso 4 | aniso 16 |
| Foliage density | 0.4 | 0.7 | 1.0 | 1.0 |
| LOD bias | 0.5 | 0.75 | 1.0 | 1.25 |
| Post effects | tonemap only | +SSAO+bloom | full | full + DOF |

Defaults are derived from a 3-second benchmark at first launch, then stored.
Show the detected preset in the settings header with a "Detected" chip — a
small touch that makes the menu feel like a shipped product.
