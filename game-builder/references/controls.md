# Controls, camera, and the feel that is not a bug

Players forgive a texture. They do not forgive a camera that clips through a
wall, a jump that eats input, or a character that moonwalks. Movement and
camera are the highest-risk part of the project and the part most likely to be
shipped untested — so this file gives concrete numbers and a harness.

## Contents

1. Input abstraction
2. Character controller (Rapier)
3. Movement tuning table
4. Jump feel
5. Camera rig
6. Feel layer (shake, FOV, hit-stop)
7. Gamepad and rebinding
8. Telemetry harness
9. Verification checklist

---

## 1. Input abstraction

Never read `event.code` in gameplay code. Map physical input → **actions**:

```ts
type Action = 'move' | 'look' | 'jump' | 'sprint' | 'crouch' | 'interact' | 'aim' | 'fire';

interface InputState {
  move: THREE.Vector2;      // -1..1, already deadzoned and clamped to a circle
  look: THREE.Vector2;      // radians-ish delta this frame
  pressed: Set<Action>;     // this frame only
  held: Set<Action>;
  released: Set<Action>;
}
```

- **Pointer lock** for mouse look. Request it on click, handle
  `pointerlockerror`, show "click to play" and re-acquire on focus loss.
- **`movementX/Y` accumulate per frame and are consumed once** — never apply
  inside the event handler, or you get FPS-dependent camera speed.
- **Raw input**: set `unadjustedMovement: true` on `requestPointerLock` where
  supported (Chrome). It removes OS mouse acceleration, which is the difference
  between "feels like a game" and "feels like a webpage".
- **Gamepad**: poll with `navigator.getGamepads()` in the frame loop, radial
  deadzone 0.18, re-scale so 0.18→1 maps to 0→1, and remember the active
  device so prompts switch between keys and buttons.
- **Deadzone shape matters**: per-axis deadzones make diagonal movement
  lopsided. Use a radial one.
- **Buffer edge events**: `pressed` is cleared at the end of the frame, so a
  one-frame tap is never lost even if the physics substeps twice.

## 2. Character controller (Rapier)

Use the kinematic character controller, not a dynamic body. Dynamic capsules
tip over, jitter on stairs, and cannot be tuned precisely.

```ts
const controller = world.createCharacterController(0.01);
controller.setUp({ x: 0, y: 1, z: 0 });
controller.setMaxSlopeClimbAngle((50 * Math.PI) / 180);
controller.setMinSlopeSlideAngle((35 * Math.PI) / 180);
controller.enableAutostep(0.35, 0.2, true);        // maxHeight, minWidth, includeDynamic
controller.enableSnapToGround(0.3);
controller.setApplyImpulsesToDynamicBodies(true);
controller.setCharacterMass(80);
```

```ts
// per physics step
const desired = new RAPIER.Vector3(vel.x * dt, vel.y * dt, vel.z * dt);
controller.computeColliderMovement(collider, desired);
const corrected = controller.computedMovement();
const grounded = controller.computedGrounded();
body.setNextKinematicTranslation({
  x: pos.x + corrected.x, y: pos.y + corrected.y, z: pos.z + corrected.z,
});
```

- **Fixed timestep** at 1/60 with an accumulator (max 3 substeps), interpolate
  the render transform. Never step physics with the raw frame delta.
- **Capsule**: radius 0.35, half-height 0.55 (≈1.8 m total), origin at the
  centre. Feet = `y - (halfHeight + radius)`.
- **Gravity**: `-22 m/s²` for a game (Earth's 9.81 feels floaty), terminal
  velocity −55.
- **Never disable the collider to fix a stuck player.** If the player gets
  stuck, fix the collider or add a depenetration nudge (0.02 m/s for 3 frames).

## 3. Movement tuning table

Values for a grounded, third-person action-adventure. Tune per project, but
start here — these numbers have the right relationships.

| Parameter | Value | Note |
| --- | --- | --- |
| Walk speed | 1.6 m/s | matches a 1.6 s walk cycle |
| Run speed | 4.6 m/s | default traversal |
| Sprint | 7.2 m/s | with stamina or infinite |
| Crouch | 1.1 m/s | capsule height ×0.6 |
| Ground accel | 55 m/s² | reaches run speed in ~0.09 s |
| Ground decel | 65 m/s² | slightly faster stop than start |
| Air accel | 14 m/s² | limited control, not zero |
| Air drag | 0.15 | |
| Rotation speed | 900 °/s | character faces move dir; lerp, don't snap |
| Turn assist | 25% | when moving at speed, blend character yaw toward camera |

Acceleration-based (not instant velocity) is what separates a game from a
viewer. The **accel/decel asymmetry** is most of the "weight" feel.

## 4. Jump feel

Six small things, all standard in AAA, all missing from demos:

1. **Coyote time** 0.12 s — jump still works just after leaving a ledge.
2. **Jump buffer** 0.15 s — a jump pressed before landing fires on landing.
3. **Variable height** — release the button early and cut upward velocity
   (`vy *= 0.45`), plus a min jump time of 80 ms so a tap is not a stub.
4. **Apex hang** — apply `gravity * 0.65` while `|vy| < 1.5 m/s`. Makes jumps
   feel controllable without changing the arc.
5. **Landing squash** — 0.08 s camera dip + foot-plant animation.
6. **Separation of jump vs. vault** — if a ledge is within 1.2 m above and you
   are moving into it, play the vault. Nothing feels more AAA than the
   character handling the geometry for you.

```ts
if (grounded) { coyote = COYOTE; jumpBuffer = 0; } else coyote -= dt;
if (input.pressed.has('jump')) jumpBuffer = BUFFER;
if (jumpBuffer > 0 && coyote > 0) { vy = JUMP_V; jumpBuffer = 0; coyote = 0; }
```

## 5. Camera rig

The camera is the player's body. Build it as a rig, not a `lookAt`:

```
target (head/pivot, y = eye height)
└── yawPivot (rotate Y from input)
    └── pitchPivot (clamp -75°..+70°, rotate X)
        └── springArm (length 3.2 m, spherecast, min 0.6)
            └── camera (+ shoulder offset 0.55 m right, 0.15 up)
```

- **Collision**: spherecast from the pivot along the boom direction, pull the
  camera to `hitDistance - 0.2`, and sway it back out over 0.25 s. Never let
  the near plane cross geometry — that is the first thing a player notices.
- **Frame-rate independent damping**: `x = damp(x, target, lambda, dt)` with
  `damp = 1 - Math.exp(-lambda * dt)` (lambda 12–18 for the boom, 25 for the
  shoulder). Lerping with a raw `0.1` factor is FPS-dependent and is a bug.
- **Pitch clamp** per state: gameplay 75°, aiming 55°, cinematic 40°.
- **No camera roll** during gameplay; a tiny (≤ 2°) roll on turns adds life,
  but never more.
- **Occlusion fade**: when the boom is shorter than 1.2 m, fade the player
  mesh to 30% alpha — do not let the camera go inside the head.
- **Mouse sensitivity is in cm/360°**, not arbitrary. Store `0.022 °/count`,
  expose 0.005–0.10, and multiply by an ADS factor (0.6 for 1x, 0.4 for 4x).
  Add an invert-Y toggle and a separate gamepad sensitivity.
- **First person variant**: eye height 1.68 m, head bob 0.02 m at walk
  (disable-able in Accessibility), weapon/hands on a separate camera layer so
  they never clip walls.

## 6. Feel layer

- **Camera shake** as trauma: `trauma = clamp(trauma + amount)`, shake =
  `trauma² * noise(t)`, decay 1.8/s. Squared trauma is why AAA shake feels
  punchy instead of nauseating. Cap at 2° / 4 cm.
- **FOV kick**: +6° while sprinting, +4° on landing, lerp over 0.2 s.
  Never change FOV abruptly.
- **Hit-stop**: 40–80 ms of `timeScale 0.15` on impact.
- **Recoil**: camera pitch impulse with recovery over 0.15 s, additive to
  input pitch so it never fights the player.
- **Audio**: footsteps by material (raycast down → surface tag), whoosh on
  fast turns, a low "air" layer when falling. Sound is half of feel.
- **Accessibility**: screen-shake scale, FOV cap, hold vs. toggle, auto-sprint,
  and a "motion reduction" mode that removes bob/shake/FOV kick. Ship these in
  the settings menu, not in a code comment.

## 7. Gamepad and rebinding

- **Rebinding table** with conflict detection: if a key is already bound, swap
  or clear, and show which action it belonged to.
- **Presets**: WASD / arrows / AZERTY, Xbox / PlayStation button glyphs.
- **Two bindings per action** (primary/secondary) is the AAA standard.
- **Gamepad UI navigation**: focus ring, D-pad/left-stick, A/Cross confirm,
  B/Circle back, and the whole settings menu operable without a mouse.
- **Store the layout** in settings; reset to default per action.

## 8. Telemetry harness

Ship a debug module behind `?debug=1` that can prove movement works. This is
how you verify without playing for an hour.

```ts
// debug/selfTest.ts
export async function runControlsTest(game: Game) {
  const out: string[] = [];
  const expect = (name: string, ok: boolean, detail: string) => {
    out.push(`${ok ? 'PASS' : 'FAIL'}  ${name}  ${detail}`);
  };

  // 1. input reaches the character
  const p0 = game.player.position.clone();
  game.input.inject({ move: new THREE.Vector2(0, 1), held: new Set(['sprint']) });
  await game.advance(1.0);                       // fixed 60 steps
  const travelled = game.player.position.distanceTo(p0);
  expect('forward speed', travelled > 5.5 && travelled < 8.0, `${travelled.toFixed(2)} m/s`);

  // 2. no wall penetration on a straight run
  game.teleport('test_wall_arena', new THREE.Vector3(0, 0, 8));
  game.input.inject({ move: new THREE.Vector2(0, 1), held: new Set(['sprint']) });
  await game.advance(2.0);
  expect('wall blocked', game.player.position.z > 0.5, `z=${game.player.position.z.toFixed(2)}`);

  // 3. step-up
  const before = game.player.position.y;
  await game.advance(1.5);
  expect('stairs climbed', game.player.position.y > before + 0.5, `dy=${(game.player.position.y - before).toFixed(2)}`);

  // 4. camera never inside geometry
  let camInside = 0;
  for (let i = 0; i < 600; i++) {
    game.input.inject({ look: new THREE.Vector2((i % 40) * 0.01, 0) });
    await game.advance(1 / 60);
    if (game.cameraInsideGeometry()) camInside++;
  }
  expect('camera collision', camInside === 0, `${camInside} bad frames`);

  // 5. frame-rate independence
  const a = await game.simulate(1.0, 1 / 30);
  const b = await game.simulate(1.0, 1 / 144);
  expect('fps independence', Math.abs(a - b) < 0.15, `30Hz=${a.toFixed(2)} 144Hz=${b.toFixed(2)}`);

  // 6. jump feel
  expect('coyote time', await game.testCoyote(), 'ledge jump allowed');
  expect('jump buffer', await game.testJumpBuffer(), 'buffered jump fired');

  console.table(out);
  return out;
}
```

Points 2, 3 and 5 catch the overwhelming majority of real movement bugs. Run
this in CI (headless) and print it in the debug overlay.

## 9. Verification checklist

- [ ] 60 s free run: no clipping, no falling through the floor, no stuck spots
- [ ] 30 fps, 60 fps, 144 fps give the same travel distance and jump height
- [ ] Camera: full 360° sweep in a corner, a tight corridor, and against a wall
      — never inside geometry, never flips
- [ ] Pointer lock: click to play, Esc releases, re-click re-locks, alt-tab
      returns cleanly
- [ ] Gamepad: move, look, jump, and full menu navigation with a real pad
- [ ] Rebinding persists after reload and after a version bump
- [ ] Invert Y, sensitivity, ADS multiplier, deadzone, motion reduction all work
- [ ] No input is eaten during a 0.5 s hitch or a chunk load
- [ ] Character faces movement, animation matches speed, feet do not slide
      (see `references/animation.md` § 9)
