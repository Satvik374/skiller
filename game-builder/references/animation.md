# Animation — rigs, retargeting, blend spaces, contact

An unretargeted or unblended character is more damaging to the "AAA" read than
low texture resolution. This file is the whole chain: get clips, map bones,
build a locomotion blend, fix feet, verify seams.

## Contents

1. Clip sources
2. The retarget problem, and the math
3. Reference implementation (three.js)
4. Locomotion blend space
5. One-shots, additive layers, crossfades
6. Foot sliding and foot IK
7. Root motion
8. NPCs and crowd
9. Verification

---

## 1. Clip sources

- **Mixamo** — free, Adobe account required, huge humanoid library. Download
  **FBX Binary**, then convert to GLB with `gltf-transform` (`fbx2gltf` or
  Blender headless). Two useful formats: *with skin* (a full character,
  ~40 MB — good for NPC variety) and *without skin* (motion only, ~200 KB —
  the right choice when you already have a rig).
- **Sketchfab** — many rigged models ship animation clips in the GLB
  (`animationCount > 0` in search). Audit them; clip naming is chaos.
- **Your own mocap** (Rokoko/MediaPipe) — viable for a prototype, but noise on
  the hips and feet needs cleanup.
- **Procedural** — walk cycles do not need mocap if the character is
  small/distant; but a hero character seen at 2 m needs real motion.

Minimum clip set for a third-person game: `idle`, `walk_fwd`, `run_fwd`,
`jump_start`, `jump_air`, `jump_land`, `turn_l/r` (or a pivot), plus per weapon
or per interaction. Eighth-direction strafes only if the camera is free and the
character strafes; otherwise rotate the character to the movement vector.

## 2. The retarget problem, and the math

A Mixamo clip uses `mixamorig:Hips`, `mixamorig:Spine`, …; a Sketchfab
character uses `Hips`, `Spine`, or `CC_Base_Hip`. Bone *names* differ, rest
poses differ, bind orientations differ, and scale differs (Mixamo is cm).

The correct approach is rest-pose delta retargeting:

1. **Build a bone map** target→source by normalised name
   (`mixamorig:LeftArm` → `leftarm` → matches `upperArm.L`). Normalise by
   lowercasing and stripping prefixes, `:`/`_`/`.` and digits.
2. **Capture both rest poses** (world quaternions of every bone in bind pose).
3. **For each frame**, for each bone: compute the source's world delta from its
   own rest, then apply that delta to the target's rest world rotation:
   `targetWorld = sourceWorldDelta * targetRestWorld`.
4. **Convert back to local** by multiplying with the parent's inverse world
   rotation, walking the hierarchy from root outward.
5. **Hips translation** is retargeted separately as a scalar: multiply by
   `targetRestHipHeight / sourceRestHipHeight` (this is what fixes the
   cm-to-m character that sinks into the floor).
6. **Scale the whole clip duration** if the source is at a different frame rate.

Doing it in world space (rather than copying local rotations) is what makes
characters of different proportions land poses that still look human.

## 3. Reference implementation (three.js)

```ts
// retarget.ts — apply a source clip's motion onto the target skeleton.
const REST = new WeakMap<THREE.Bone, THREE.Quaternion>(); // target rest world

export function captureRest(skinned: THREE.SkinnedMesh) {
  skinned.skeleton.update();
  skinned.updateWorldMatrix(true, true);
  for (const bone of skinned.skeleton.bones) {
    const w = new THREE.Quaternion();
    bone.getWorldQuaternion(w);
    REST.set(bone, w);
  }
}

const normalise = (n: string) =>
  n.toLowerCase().replace(/^mixamorig[:_]?/, '').replace(/[_\s:.\-]/g, '').replace(/\d+/g, '');

export function retargetClip(
  clip: THREE.AnimationClip,
  srcRoot: THREE.Object3D,
  dstRoot: THREE.Object3D,
  dstBones: THREE.Bone[],
): THREE.AnimationClip {
  const byName = new Map(dstBones.map((b) => [normalise(b.name), b]));
  const srcBones = new Map<string, THREE.Object3D>();
  srcRoot.traverse((o) => srcBones.set(normalise(o.name), o));

  const tracks: THREE.KeyframeTrack[] = [];
  const tmpQ = new THREE.Quaternion();
  const srcRest = new THREE.Quaternion();
  const srcWorld = new THREE.Quaternion();
  const dstRest = new THREE.Quaternion();
  const parentWorld = new THREE.Quaternion();
  const parentInv = new THREE.Quaternion();

  for (const track of clip.tracks) {
    const [nodeName, prop] = track.name.split('.');
    const dst = byName.get(normalise(nodeName));
    const src = srcBones.get(normalise(nodeName));
    if (!dst || !src || prop !== 'quaternion') continue;

    const times: number[] = [];
    const values: number[] = [];
    const srcParent = src.parent!;
    const dstParent = dst.parent!;

    for (let i = 0; i < track.times.length; i++) {
      // source local -> source world at this frame
      src.getWorldQuaternion(srcRest); // bind pose, captured once outside ideally
      const q = new THREE.Quaternion().fromArray(track.values as any, i * 4);
      srcWorld.copy(srcRest).multiply(q); // rest * localDelta (approx.)
      // source delta from its own rest
      const delta = srcRest.clone().invert().premultiply(srcWorld).normalize();
      // apply to target rest world
      dstRest.copy(REST.get(dst)!);
      const targetWorld = delta.multiply(dstRest).normalize();
      // world -> local
      dstParent.getWorldQuaternion(parentWorld);
      parentInv.copy(parentWorld).invert();
      tmpQ.copy(parentInv).multiply(targetWorld).normalize();
      times.push(track.times[i]);
      tmpQ.toArray(values, i * 4);
    }
    tracks.push(new THREE.QuaternionKeyframeTrack(`${dst.name}.quaternion`, times, values));
  }

  const out = new THREE.AnimationClip(clip.name, clip.duration, tracks);
  // hips height: scale translation separately
  return out;
}
```

That is the shape of it, not copy-paste-production: capture the source rest
pose once (not per frame), handle the hips translation track with the height
ratio, and normalise quaternion sign flips (`q` and `-q` are the same
rotation — if consecutive keyframes flip sign you get a 360° spin).

**When retargeting goes wrong**, the symptoms and causes:

| Symptom | Cause |
| --- | --- |
| limbs inside out / backward knees | rest pose not captured, or bind orientation ignored |
| character spins wildly | quaternion sign flip between keys |
| sinking into floor / floating | hips translation not scaled by height ratio |
| arms clamped to sides | missing bone in the map, so the source pose leaks into it |
| whole body tiny or huge | node scale from FBX (×0.01) baked twice |

Successfully retargeted: `mixer.clipAction(retargeted).play()` reproduces the
performance on the new proportions. Verify with the audit and the contact test.

## 4. Locomotion blend space

Do not crossfade by hand with timers. Build a 1D/2D blend tree:

```ts
const clips = { idle, walk, run, sprint };         // all retargeted
const actions = Object.fromEntries(
  Object.entries(clips).map(([k, c]) => [k, mixer.clipAction(c)]),
);

// every action runs, weights are the only control
Object.values(actions).forEach((a) => { a.play(); a.setEffectiveWeight(0); });

function updateLocomotion(speed: number, dt: number) {
  const w = {
    idle:   clamp01(1 - speed / 1.4),
    walk:   smoothPulse(speed, 0.0, 1.4, 2.6),
    run:    smoothPulse(speed, 1.4, 2.6, 5.0),
    sprint: smoothPulse(speed, 4.0, 6.0, 9.0),
  };
  // normalise + setEffectiveWeight, with a 0.15 s weight slew so no pop
}
```

- **Phase matching**: walk and run cycles must be aligned so feet alternate at
  the same phase. A mismatched phase at 50/50 weight makes the character
  moonwalk. Fix by syncing `walk.time = run.time * (walkDur / runDur)` when
  weights cross, or by using `action.syncWith()`.
- **Playback rate follows speed**: `action.timeScale = speed / referenceSpeed`
  (reference speed = the clip's authored metres/second, measured from the
  root motion or the stride length). This is the cheapest and most effective
  anti-slide fix.
- **Turn in place** when the angle delta > 100°: a pivot clip or a 0.15 s
  procedural lean.
- **Foot step audio and dust** should be driven by animation **events**, not a
  fixed timer — `mixer` `'loop'` plus a sampled foot-plant frame index per clip.

## 5. One-shots, additive layers, crossfades

```ts
function playOneShot(name: string, fadeIn = 0.08, fadeOut = 0.2) {
  const a = actions[name];
  a.reset().setLoop(THREE.LoopOnce, 1);
  a.clampWhenFinished = true;
  a.fadeIn(fadeIn).play();
  // return to locomotion, never snap
  a.crossFadeTo(locomotionAction, fadeOut, false);
}
```

- **`LoopOnce` + `clampWhenFinished`** for jump-land, vault, hit reactions.
- **Fade times by action, not one global**: hits 0.05 s, weapon draw 0.1 s,
  idle↔walk 0.2 s. Snapping is the tell.
- **Additive upper body**: aim, reload, IK look-at, breathe. Put a mask on the
  layer (`AnimationUtils.makeClipAdditive`, then add on top of the locomotion
  weights) so legs keep walking while the chest aims. In three.js: play a
  second action with weight and an additive clip; mask bones by zeroing
  tracks for the lower body.
- **Never leave a character in T-pose**: the idle action must be playing with
  weight ≥ 0 at all times, and on load, call `mixer.update(0)` before the
  first render.
- **`mixer.timeScale`** for hit-stop (0.15 for 60 ms on impact) — a tiny detail
  that makes combat feel expensive.

## 6. Foot sliding and foot IK

Foot sliding is the most common animation tell. Three tiers, apply all three:

1. **Speed-matched playback** (above). Kills most of it.
2. **Stride matching**: measure the clip's stride length (distance the hips
   travel per cycle in the authored motion) and set the character's move speed
   to `strideLength / cycleDuration` while that clip dominates. Change speed
   with weight, not by scaling everything.
3. **Two-bone foot IK** for the last 10 cm: raycast down from each foot,
   adjust the foot's world Y, solve knee with the law of cosines, and rotate
   the foot to the ground normal. Blend IK weight to 0 above 0.5 m/s of
   vertical motion (jumps) and on stairs it earns its keep.

```ts
// ground probe per foot, 2 m ray, ignore self
const hit = raycaster.intersectObject(groundMesh, false)[0];
const targetY = hit ? hit.point.y + soleOffset : hipY - legLength;
footIkWeight = damp(footIkWeight, hit ? 1 : 0, 12, dt);
```

Pelvis offset: if both feet need to go up on uneven ground, lower the hips by
the max correction rather than bending knees unnaturally.

## 7. Root motion

Two modes, pick one per game and be consistent:

- **In-place clips + code-driven movement** (easiest, best for a free camera):
  root track stripped at import, capsule moves, feet solved by IK. Default.
- **Root motion** (best for cinematic, dodge rolls, vaults): read the root
  bone's delta each frame, apply it to the capsule, cancel it from the pose.
  Requires the clip to have a clean root track; Mixamo's "in place" variants
  do not.

For attacks, **motion warping**: scale the root translation over the first
30% of the clip so the attack lands on the target regardless of distance. This
is what makes melee feel like a AAA game rather than a whiff.

## 8. NPCs and crowd

- **`SkeletonUtils.clone`** for every instance of a skinned mesh — a plain
  `.clone()` shares the skeleton and all NPCs move identically.
- **Share the `AnimationMixer` clips**, not the actions; one mixer per instance
  is required.
- **Animation LOD**: NPCs beyond 15 m update at 15 Hz, beyond 40 m at 5 Hz,
  beyond 80 m swap to a static or 2-frame baked pose. This is the difference
  between 8 and 80 NPCs.
- **Variety without more assets**: swap clips, vary `timeScale` ±6%, vary
  proportions via bone scale on a copy, swap material tints.

## 9. Verification

Run these before calling animation done. Record results in `ANIMATION.md`.

| Check | Method | Pass |
| --- | --- | --- |
| Every clip plays | loop all clips at weight 1, assert `mixer` has an active action and no NaN in bone matrices | all |
| No T-pose frame | screenshot frame 0 and frame 1 of load | posed |
| Loop seam | compare first and last keyframe per quaternion track | Δangle < 2° |
| Foot contact | at walk/run, raycast each foot; log frames where the planted foot moves | ≤ 3 cm/frame slip |
| No sinking | lowest foot vertex vs ground plane over a 10 s walk | \|Δ\| < 2 cm |
| Crossfade pop | log max per-frame bone angular velocity during transitions | no spike > 4× median |
| Retarget sanity | render the source and target side by side at 3 poses | same silhouette |
| Frame cost | mixer update time for N characters | < 1.5 ms for 20 |

`scripts/glb_audit.py --loop-check` gives you the seam numbers and the clip
inventory for free. The foot-contact test is 30 lines in the game's debug
harness (see `references/controls.md` § Telemetry).
