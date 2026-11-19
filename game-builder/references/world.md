# World — building an open world that reads as authored

"Open world" in a browser means **traversable and continuous**, not
"200 km²". A dense, hand-dressed 1.2 × 1.2 km map with streaming, a road
network and 8 points of interest beats an empty 20 km plain every time — and it
is the only version that hits the frame budget.

## Contents

1. Decide the scale
2. Terrain
3. Streaming chunks
4. Modular architecture kits
5. Set dressing (where the AAA look actually lives)
6. Foliage and vegetation
7. Lighting over a large map
8. Points of interest and the story layer
9. Collision and traversal coverage
10. Verification

---

## 1. Decide the scale

| Map size | Fits | Streaming |
| --- | --- | --- |
| 300 × 300 m | a village, a facility, a valley | whole map resident |
| 1 × 1 km | the default: a district with a road loop and 6–8 POIs | 128 m tiles, 3×3 radius |
| 2 × 2 km | open world feel, needs fast travel | 128 m tiles, LOD + impostors |
| > 3 × 3 km | needs a procedural pipeline and a hard budget conversation | mandatory HLOD |

Write the number in `PLAN.md`. Then make the playable path 10–15 minutes long
with something to see every 40 seconds. Density is the whole trick.

## 2. Terrain

- **Heightmap** 1024² or 2048², 16-bit, world-scaled (e.g. 2 km / 2048 px =
  1 m per texel). Build it in code or in a small tool; a noise stack
  (fBm + ridged + erosion pass) plus hand-painted masks for roads and flats.
- **Split into tiles** (128 m) with shared edge vertices, so LOD seams do not
  crack: use `skirts` (a 2 m vertical skirt hidden under the surface) or
  stitch indices. Skirts are the pragmatic choice.
- **Splat map** with 4–8 layers: grass, dirt, rock, gravel, sand, snow. Blend
  by height, slope and a painted mask. Rock on slope > 35°, sand near water,
  grass elsewhere is already convincing.
- **Triplanar** for rock so cliffs do not stretch.
- **Add a detail normal + macro variation** at a second UV scale. Terrain that
  is one tiled texture is the classic "empty world" look.
- **Roads**: carve into the heightmap (flatten a spline corridor), then lay a
  road mesh with a slightly recessed base and a gravel edge decal. Roads are
  the strongest scale cue in an open world — the eye reads their width as
  human scale.

## 3. Streaming chunks

```ts
type Chunk = { key: string; root: THREE.Group; state: 'unloaded'|'loading'|'ready' };
const TILE = 128, RADIUS = 2;   // 5x5 tiles around the player

function updateStreaming(p: THREE.Vector3) {
  const cx = Math.floor(p.x / TILE), cz = Math.floor(p.z / TILE);
  const wanted = new Set<string>();
  for (let dz = -RADIUS; dz <= RADIUS; dz++)
    for (let dx = -RADIUS; dx <= RADIUS; dx++)
      wanted.add(`${cx + dx},${cz + dz}`);
  // unload first (free VRAM before the hitch), then queue loads
  // upload budget: 2 MB of geometry + 4 MB of textures per frame, max 1 tile
}
```

- **Async everywhere.** `GLTFLoader` on a worker via `createImageBitmap` +
  meshopt decode in a worker; never block the main thread on parse.
- **Placeholder LOD**: keep a low-res proxy of every tile so an unloaded
  neighbour is never a hole or a sky-blue gap.
- **Idle prefetch**: load the tiles in the direction of travel first
  (velocity-weighted queue), not in a spirial around the player.
- **Deterministic seeds** per tile so a reloaded chunk matches the old one.
- **Budget the hitch**: measure it. A 300 ms hitch is worse than a missing prop.

## 4. Modular architecture kits

The professional way to build a city without a level designer:

- **Snap grid**: 4 m wall modules, 4 m × 4 m floor/ceiling, 1 m trim. Every
  piece is authored to that grid and exports with its pivot on a grid corner.
- **Trim sheets**: one 2048² texture with 4–8 bevel profiles, repeated on
  every wall, cornice, skirting, window frame. This is how AAA packs get
  material consistency cheaply.
- **Vertex-blended materials** for walls (concrete → brick → grime) so no
  module is visually identical to its neighbour.
- **Broken variants**: one wall module with a hole, one with a doorway, one
  with a collapsed floor. Rotate and vary scale 0.98–1.02 to break tiling.
- **Interiors are cheap in tri count and expensive in draw calls** — merge each
  room to a few meshes with `BatchedMesh` once instanced.
- A 1 km district needs roughly: 12 wall modules, 6 window modules, 4 roof
  pieces, 3 doors, 2 stairs, 20 props, 10 decals. That is a *kit*, and it is
  achievable with the Sketchfab/subscription packs.

## 5. Set dressing (where the AAA look actually lives)

An empty street of correctly-modelled buildings still reads as a demo. Dressing
is the difference, and it is rule-driven:

- **Layers per 100 m²**: 1 large object (crate, barrel, car), 3 medium
  (pallet, bin, sign), 8 small (bottle, paper, cable), 2 decals, 1 light.
- **Rules that make it look authored**: objects cluster near edges and walls,
  debris follows wind/water (bottom of slopes, against kerbs), wear is where
  people walk (path wear decals on grass), grime is at the bottom 30 cm of
  walls, and nothing sits perfectly axis-aligned unless it is a fixture.
- **Storytelling props**: a knocked-over chair, a barricade with a note, an
  abandoned campfire. Two per POI. They cost nothing and turn a set into a
  place.
- **Signage with your own text** — a shop sign is a 20-second canvas texture
  and adds more "real place" than any high-poly asset.
- **Variation via random rotation, jitter and tint**, seeded per tile, with a
  handful of authored variants per slot. Never place the same crate 40 times
  with no variation.
- **Decals**: grime, posters, road markings, bullet holes, water stains.
  Projected decals are the highest perceived-detail-per-byte tool you have.

## 6. Foliage and vegetation

- **`InstancedMesh`** with per-instance colour variation and a wind vertex
  shader (vertex position offset by `sin(time + phase) * windStrength *
  vertexHeight`).
- **Alpha-tested, not blended**, cards at LOD2+ (blended foliage destroys
  early-Z and sorts badly).
- **3 LODs + a billboard** (2 crossed cards) beyond 60 m, with density fade.
- Grass: 3 species, 8–15 tufts/m² in the near ring (≤ 20 m), cards beyond.
  A grass field is a strong AAA signal; keep the shader cheap and jitter the
  rotation.
- **Wind must be consistent** across all vegetation and any cloth — one global
  wind vector and direction, shared.
- **Foliage is the first thing that shimmers** under motion. TAA + a slightly
  blurred alpha threshold, and cap the alpha test to a stable value.

## 7. Lighting over a large map

- **One sun + one hemisphere fill + IBL** for outdoors. Nothing else, unless a
  POI needs a local light.
- **Time of day**: sun elevation/azimuth drives sun colour, intensity,
  exposure, sky turbidity and fog colour from a small curve table. Add
  `night` (moon + cool IBL + emissive windows) as a second lighting state.
- **Local lights are expensive**: cap dynamic point lights at 8, fade by
  distance, and prefer emissive materials + baked-ish "glow" quads for
  windows and signs.
- **Interiors**: a baked probe look — an emissive ambient + one shadowed spot
  per room beats 12 point lights by a factor of ten in cost.
- **Fog is not optional** on a 1 km map: it hides the draw distance and gives
  aerial perspective, which is a huge part of "looks real".

## 8. Points of interest and the story layer

A story-based game needs the world to carry the narrative, not only cutscenes.

```
content/
├── story.json          # acts, beats, flags
├── quests/
│   ├── q01_arrival.json
│   └── q02_the_tower.json
├── dialogue/
│   └── npc_ferryman.json
├── pois.json           # id, position, radius, tags, discovery state
└── items.json
```

- **Mission graph**: nodes with `id`, `objectives[]`, `prerequisites[]`,
  `triggers[]`, `rewards[]`. Keep it data — a designer should be able to add a
  quest without touching engine code.
- **Trigger volumes**: `onEnter` / `onExit` / `onInteract` / `onTimer`, each
  firing an event bus message. Never hard-code `if (player.position.x > 40)`.
- **Objectives**: `reach`, `collect`, `talk`, `survive`, `escort`, `stealth`.
  Each has a world marker, a HUD line, and a completion predicate.
- **Dialogue**: a linear runner with optional choices; subtitles always on by
  default, skippable, and never longer than 2 lines on screen at once.
- **Pacing**: an open world needs a strong opening 90 seconds. Spawn the player
  looking at the landmark they will spend the game walking toward.
- **Save/load**: serialise `flags`, `completedQuests`, `playerPos`,
  `inventory`, `settingsVersion`. Version the schema from day one.

## 9. Collision and traversal coverage

- **Static colliders only** for the world; characters are capsules, props are
  convex hulls or boxes, terrain is a `Heightfield` (Rapier has one) — never a
  trimesh for terrain, it is slow to build and unstable at seams.
- **Collision proxies** from the optimised mesh's `_col` child, not the render
  mesh.
- **Ledges and invisible walls**: an open world needs soft boundaries. Use
  steep terrain + invisible colliders that are *inside* visible geometry, and
  a "return to play area" prompt rather than a hard wall in the open.
- **Every doorway, stair and ramp must be walkable** — auto-step handles the
  stairs only if `maxHeight` ≥ the riser (0.35 m handles a 30 cm riser).

## 10. Verification

| Check | How | Pass |
| --- | --- | --- |
| No holes / missing chunks | fly a fixed spline at 40 m/s, log unloaded tiles under the camera | 0 empty frames |
| Streaming hitch | record frame times during the spline | p95 < 20 ms, max < 100 ms |
| Traversal coverage | scripted walk from each POI to the next on the road graph | 100% completable |
| Collision coverage | drop 200 random points, raycast down; assert hit within 0.5 m | ≥ 99% |
| Frame budget at landmarks | 20 s sample at each POI | p95 under budget |
| Foliage shimmer | record a slow pan, watch for crawling edges | none visible |
| Scale sanity | a 1.8 m reference capsule next to doors, cars, kerbs | plausible everywhere |
| Seams | walk every kit boundary | no visible light/texture seam |
| Landmarks | 6 screenshots at golden hour | all read as intentional compositions |

The landmark screenshots are not decoration: they are how you and the user
agree on whether the world is done. Keep them in `shots/world/`.
