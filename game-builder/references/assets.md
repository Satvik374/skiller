# Assets — sourcing, licences, pipeline, audit

## Contents

1. Why generated geometry fails
2. The Sketchfab download API
3. Licensing and attribution
4. Fallback ladder
5. Optimisation pipeline
6. Import hygiene and scale
7. Audit thresholds
8. Registry format

---

## 1. Why generated geometry fails

A primitive with `MeshStandardMaterial({color})` renders as a shape with one
constant albedo, one roughness, one metalness, flat or coarse normals, no AO,
no edge wear, no dirt in the crevices, no decals. Under a real HDRI it looks
like plastic. Three details carry ninety percent of the "expensive" read:

- **Bevels.** Every manufactured edge in the real world catches a highlight.
  A 2 cm chamfer with a normal map is the difference between "box" and "crate".
  This is why you can spot AI-generated game assets instantly: hard 90°
  corners.
- **Texel density consistency.** A texture must have the same pixels-per-metre
  on a door and on the wall it sits in. Mismatched density reads as amateur at
  any polygon count. Target 512 px/m for hero surfaces, 256 px/m for props,
  128 px/m for distant set dressing.
- **Roughness variation.** Real surfaces are not uniformly glossy. A grime
  mask in roughness (and a slightly darker albedo in the same place) is what
  makes PBR materials sing.

Also: AI image-to-3D output is dominant in silhouette and dead in topology — no
edge loops, no clean UVs, no retopo-ready quads, no rigging, murky normals. It
cannot be animated well and cannot be LOD'd. Do not build a character out of it.

## 2. The Sketchfab download API

The Download API is an extension of the Data API v3. Models must be marked
downloadable by their author, and downloading requires an authenticated token.
Formats available: **glTF/GLB and USDZ only** (not FBX/OBJ).

Write scripts that read the token from the environment:

```bash
export SKETCHFAB_TOKEN='...'      # never commit, never paste in chat
```

### Authenticate

Two header forms; both are accepted on `/download`:

```
Authorization: Token  <api-token>       # from Settings → Password & API
Authorization: Bearer <oauth-token>     # from an OAuth2 app
```

`scripts/sketchfab_fetch.py` uses `SKETCHFAB_TOKEN`, `Token` scheme by default,
`--bearer` to switch.

### Search (no auth needed for public results, but send it anyway)

```bash
curl -sG 'https://api.sketchfab.com/v3/search' \
  --data-urlencode 'type=models' \
  --data-urlencode 'q=abandoned warehouse' \
  --data-urlencode 'downloadable=true' \
  --data-urlencode 'animated=true' \
  --data-urlencode 'license=cc0,by,by-sa' \
  --data-urlencode 'sort_by=-likeCount' \
  --data-urlencode 'count=24' \
  -H "Authorization: Token $SKETCHFAB_TOKEN"
```

Useful filters: `type=models`, `downloadable`, `animated`, `rigged`,
`license`, `tags`, `categories`, `min_face_count`, `max_face_count`,
`sort_by=-likeCount|-publishedAt|relevance`, `count<=24`, `cursor`.

Result fields that matter: `uid`, `name`, `viewerUrl`, `isDownloadable`,
`animationCount`, `faceCount`, `vertexCount`, `license {slug,label}`,
`user {displayName, username, profileUrl}`, `thumbnails.images[]`,
`tags[]`, `boundingBox`? (not always present — trust the file).

### Download in two steps

```bash
# 1. ask for a temporary archive URL (expires in ~300 s)
curl -s 'https://api.sketchfab.com/v3/models/<UID>/download' \
  -H "Authorization: Token $SKETCHFAB_TOKEN"
```

```json
{
  "gltf": { "url": "sketchfab-prod-media.s3.amazonaws.com/archives/.../gltf/....zip",
            "size": 45388265, "expires": 300 },
  "usdz": { "url": "...", "size": 6394777, "expires": 300 }
}
```

```bash
# 2. fetch the zip immediately, unzip, load the .glb / .gltf inside
curl -sL -o /tmp/model.zip "https://<gltf.url>"
```

Status codes you must handle explicitly, because they mean different things:

| Code | Meaning | Action |
| --- | --- | --- |
| 400 | model is not downloadable | pick another model; tell the user which one and why |
| 401 | token missing/invalid | stop, ask for the token again |
| 403 | token lacks permission (store/paid model) | pick another model |
| 404 | model gone | pick another |
| 429 | rate limited | back off with `Retry-After`, then retry |
| 200 | good | download **now**; the URL dies in minutes |

Never hotlink `sketchfab-prod-media` URLs from the game — they expire and
they are not a CDN for your site. Download, keep locally under
`public/assets/`, and ship from there.

Prefer `-likeCount` + a face-count ceiling rather than picking the first hit:
the first page of a search is full of 300k-triangle scans that will never run
in a browser.

## 3. Licensing and attribution

Every downloadable model is Creative Commons (CC0 / CC-BY / CC-BY-SA / CC-BY-ND
/ CC-BY-NC) or a paid Standard licence. Most allow commercial use.

- **Attribution is a licence condition for CC-BY**, not a courtesy.
  Show creator name + link in an in-game **Credits** screen, and keep
  `CREDITS.md` in the repo. `sketchfab_fetch.py` writes both rows for you.
- **NC** models cannot ship in a commercial build. Record the slug; warn the
  user before the build goes public.
- **ND** models cannot be modified — so you cannot optimise, retarget or
  kitbash them. Treat ND as unusable for a game and pick something else.
- **Standard-licence (paid)** models: the user's purchase, their terms.
- Do not redistribute the extracted archive as a downloadable pack, and do not
  keep the original textures in a public `/assets` listing if the licence
  forbids standalone access. Serving files to the game client is fine; a
  browsable "download all models" directory is not.

Put the same attribution text behind an in-game "Licences" panel. That is what
AAA games do and it costs one component.

## 4. Fallback ladder

When Sketchfab is unavailable (no token, or nothing suitable), descend in
order. Stop as soon as the frame reads correctly.

| Rung | Source | Licence | Good for |
| --- | --- | --- | --- |
| 1 | Sketchfab (token) | CC / paid | characters, hero props, environment kits, vehicles |
| 2 | Mixamo | free, Adobe account | humanoid motion clips + a base rig |
| 3 | Poly Haven | CC0 | HDRIs (the single biggest visual win per MB), textures, a few models |
| 4 | ambientCG | CC0 | PBR material sets (albedo/normal/rough/ao/displacement), decals |
| 5 | Khronos glTF Sample Assets | permissive | reference models, animation test rigs (Fox, CesiumMan) |
| 6 | Quaternius / Kenney | CC0 | stylised foliage and modular kits — acceptable *only* if art direction is stylised |
| 7 | Fab / Unreal Marketplace / Unity Asset Store | paid, user's account | when the user needs a coherent kit fast |
| 8 | Author it yourself in code + textures | yours | signage, decals, trim sheets, water, sky, particles, HUD |

If the project needs a signature character and rung 1 is empty, say so plainly
and offer: (a) wait for the token, (b) buy a character pack, (c) ship a
first-person game where the body is rarely seen. All three are better than a
generated humanoid.

## 5. Optimisation pipeline

Raw Sketchfab scans are 100k–2M triangles with 4K PNGs. Nothing ships raw.

```bash
# audit first — decide from numbers, not vibes
python3 game-builder/scripts/glb_audit.py download/warehouse.glb --max-tris 120000

# compress + simplify + repack
bash game-builder/scripts/optimize_assets.sh public/assets/props/warehouse.glb
```

What the pipeline does and why each step matters:

- **Deduplicate + prune** — identical materials merged, unused UV sets dropped.
- **Meshopt / DRACO** — geometry compresses 4–8×. Meshopt decodes faster and
  supports animation; DRACO is smaller but slower. Use meshopt for anything
  animated or instanced, DRACO for one-off static hero meshes.
- **KTX2 (Basis) textures** — stays compressed in GPU memory, cuts VRAM 4–6×
  and removes upload stalls. Requires `KTX2Loader` + transcoder wasm. If you
  cannot ship the transcoder, use WebP/JPEG and downscale instead — never ship
  4K PNGs.
- **Channel packing** — occlusion/roughness/metalness into one RGB texture
  (`ORM`). three.js reads `aoMap`/`roughnessMap`/`metalnessMap` from separate
  slots; either pack and use a custom node material, or accept three textures.
- **Texture downscale** to the budget in `SKILL.md`. A 1024² prop read at 2 m
  is indistinguishable from 4096² and costs 16× the VRAM.
- **LOD** — for hero props generate LOD1 (50%) and LOD2 (15%) with
  `gltf-transform simplify`, and a billboard/impostor for foliage and distant
  buildings.
- **Collision proxies** — never collide against the render mesh. Author a
  low-poly `_col` mesh, or extract a convex hull (`gltf-transform` + Rapier
  `ColliderDesc.convexHull`). Ship the col mesh in the same GLB as a named
  child and hide it at runtime.

Keep originals in `download/` (gitignored) and only optimised output in
`public/assets/`. Add `download/` and `*.zip` to `.gitignore`.

## 6. Import hygiene and scale

Fix these at import, once, in a `preprocess` step — not per-object in game code:

- **Units: 1 unit = 1 metre.** Sketchfab is usually metres; Mixamo is
  centimetres and must be scaled ×0.01. Check with the audit's bbox: a human
  should be 1.6–1.95 m tall.
- **Y-up, -Z forward.** Bake rotations into the mesh so the character faces
  -Z and its feet sit at y=0.
- **Pivot at the base centre** for props, **at the feet** for characters, **at
  the steer point** for vehicles. A pivot in the middle of a crate means every
  placement is off by half its height.
- **Apply transforms.** A node with `scale: 0.01` and a rotated parent breaks
  instancing and physics. Flatten in `gltf-transform` or Blender.
- **Name things.** `SM_` static mesh, `SK_` skeletal, `MAT_`, `T_`. Animations
  `AS_<char>_<action>_<variant>`. You will search these names for weeks.
- **Strip cameras and lights** from downloaded scenes — they fight yours.
- **One material per logical surface**, not per triangle island.

## 7. Audit thresholds

`glb_audit.py` prints a table and exits non-zero when a limit is exceeded. Use
these defaults unless the art direction says otherwise.

| Check | Prop | Hero / character | Environment chunk |
| --- | --- | --- | --- |
| Triangles | ≤ 20k | ≤ 120k | ≤ 250k |
| Textures | ≤ 1024² | ≤ 2048² | ≤ 2048² |
| Materials | ≤ 3 | ≤ 8 | ≤ 20 |
| Bones | — | ≤ 120 | — |
| File size | ≤ 4 MB | ≤ 40 MB | ≤ 60 MB |
| Required | bbox sane (0.05–50 m) | bbox + clips + skin | bbox + no cameras |

Also treat these as failures: missing image references, `KHR_draco` or
`EXT_meshopt_compression` present without the decoder wired up, more than one
UV set unused, animation clips with zero duration, skins whose joint count
exceeds 4 influences per vertex (three.js supports 4 by default).

## 8. Registry format

`assets/registry.json` is the source of truth for provenance. Generate it in
the fetch script, never by hand:

```json
{
  "warehouse_ruin": {
    "file": "public/assets/env/warehouse_ruin.glb",
    "source": "sketchfab",
    "uid": "49d97ca2fbf34f85b6c88ae8ebc7514f",
    "url": "https://sketchfab.com/3d-models/warehouse-ruin-49d97ca2fbf34f85b6c88ae8ebc7514f",
    "title": "Warehouse Ruin",
    "author": "some_artist",
    "author_url": "https://sketchfab.com/some_artist",
    "license": "CC-BY-4.0",
    "attribution_required": true,
    "downloaded_at": "2026-11-19T10:40:00Z",
    "audit": { "tris": 48120, "textures": [2048, 2048], "clips": 0 }
  }
}
```

`CREDITS.md` and the in-game credits screen are both rendered from this file.
That is what keeps a 60-asset project inside its licence obligations without
anyone remembering anything.
