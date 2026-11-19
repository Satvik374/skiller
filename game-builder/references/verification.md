# Verification — proving it instead of claiming it

Every phase in this skill ends with a gate, and every gate is a list of things
you can check without asking anyone's opinion. This file defines the whole
verification pass, the harness that automates it, and the honesty policy for
reporting.

## Contents

1. Definition of done
2. The harness
3. Asset audit pass
4. Runtime smoke test
5. Movement and camera tests
6. Animation tests
7. World tests
8. Settings tests
9. Performance capture
10. Visual review
11. Reporting

---

## 1. Definition of done

A build is done when all of these are true, not when it "looks good":

**Looks**
- [ ] No primitive/untextured geometry is visible in any shipped frame
- [ ] Every material has albedo + normal + (roughness or packed ORM)
- [ ] HDRI lighting, ACES tonemapping, and a colour LUT are active
- [ ] Post stack at the shipped tier: AO, bloom, AA, and (if budget) volumetrics
- [ ] Shadow bias tuned: no peter-panning on character feet
- [ ] Decals present on large surfaces; no flat, unbroken 20 m wall

**Moves**
- [ ] Walk/sprint/jump/crouch with coyote time, buffer, variable height
- [ ] Camera spring arm with collision, shoulder offset, damped per-frame
- [ ] Locomotion blend with no pop, no foot slide > 3 cm/frame
- [ ] One-shots crossfade; never returns to T-pose

**World**
- [ ] Map traversable end to end, no holes, no stuck spots
- [ ] Streaming holds the hitch budget
- [ ] 6 landmark screenshots read as composed places
- [ ] Story completable from a fresh save

**UI**
- [ ] Settings match `references/settings-menu.md` § 10
- [ ] HUD legible at 1080p and at the max UI scale
- [ ] Title → play → pause → settings → quit works with keyboard and gamepad

**Perf**
- [ ] p95 frame time under budget at every landmark
- [ ] Resolution scale adapts and recovers without pumping
- [ ] First playable frame under 8 s on a warm cache

## 2. The harness

One command, one report. Put it in `package.json`:

```json
{
  "scripts": {
    "verify": "npm run verify:types && npm run verify:assets && npm run verify:build && npm run verify:smoke && npm run verify:perf",
    "verify:types": "tsc --noEmit",
    "verify:assets": "python3 ../game-builder/scripts/glb_audit.py public/assets --recursive --budget preset:prop --json assets/audit.json",
    "verify:build": "vite build",
    "verify:smoke": "node scripts/smoke.mjs",
    "verify:perf": "node scripts/perf.mjs"
  }
}
```

`verify` must exit non-zero on any failure, and CI must not swallow it (no
`| tail`, no `|| true`). A verification step that cannot fail is decoration.

**`scripts/smoke.mjs`** (Playwright):

```js
import { chromium } from 'playwright';
const browser = await chromium.launch({ args: ['--use-gl=angle', '--enable-unsafe-swiftshader'] });
const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
const errors = [];
page.on('console', (m) => m.type() === 'error' && errors.push(m.text()));
page.on('pageerror', (e) => errors.push(String(e)));

await page.goto(process.env.PREVIEW_URL ?? 'http://127.0.0.1:5173/?debug=1');
await page.waitForFunction(() => window.__game?.ready, null, { timeout: 30000 });

const result = await page.evaluate(() => window.__game.runSelfTest());
await page.screenshot({ path: 'shots/smoke.png' });

const failed = result.filter((l) => l.startsWith('FAIL'));
console.log(result.join('\n'));
await browser.close();
if (errors.length || failed.length) {
  console.error('console errors:', errors);
  process.exit(1);
}
```

Expose `window.__game` only under `?debug=1` — it is a test affordance, not a
gameplay API, and it must not be reachable in a production build (strip it with
a build flag).

### Serving the build for review

Two things break a built game that runs fine in `vite dev`:

- **Subpath hosting.** A build served from `/demo/dist/` needs `base: "./"`
  *and* runtime asset URLs built from `import.meta.env.BASE_URL`. `base` only
  rewrites the bundle's own references; your `loader.load("/assets/x.glb")`
  strings still point at the server root and 404 silently.
- **Host allowlists.** Vite (5.4+) rejects unknown `Host` headers with a 403 and
a blank page. Allow the preview hostname per environment, not in the tracked
  config:

  ```js
  server: { host: "0.0.0.0", allowedHosts: process.env.PREVIEW_HOST ? [process.env.PREVIEW_HOST] : [] }
  ```

Never `allowedHosts: true`. A 403 from a `.style.dev` / tunnel hostname is an
allowlist problem, not a broken app; check `127.0.0.1` with the same `Host`
header before concluding anything about the render.

**`scripts/perf.mjs`**: navigate, wait ready, warm 3 s, sample 20 s of
`requestAnimationFrame` deltas, report p50/p95/max plus
`renderer.info.render.{calls,triangles}` and `memory.textures`, write
`shots/perf.json`. Compare against `PERF.md` and fail on regression > 15%.

## 3. Asset audit pass

```bash
python3 ../game-builder/scripts/glb_audit.py public/assets --recursive \
  --budget preset:prop --json assets/audit.json
```

Read the table, don't just take the exit code. What to look for beyond pass/fail:

| Signal | Meaning |
| --- | --- |
| tris ≫ 100k on a prop | scan or photogrammetry; simplify before shipping |
| 4096² textures | VRAM blowout; downscale to 1024/2048 |
| many materials on one mesh | draw-call explosion; merge by material |
| bbox height 0.01 or 120 | wrong units — fix at import, not with scale hacks |
| `clips: 0` on a character | it is a statue; it cannot animate |
| bones > 120 | retarget cost and skinning cost; use fewer |
| Draco/meshopt extension present | ensure the decoder is actually wired up |
| missing image reference | the model will render magenta/naked |

For every asset, confirm `assets/registry.json` has a licence and author, and
that `CREDITS.md` regenerated. An unlicensed asset in a build is a legal bug.

## 4. Runtime smoke test

Fast, catches the catastrophic:

- page loads, no console errors, no unhandled rejections
- first frame renders (not a black canvas — sample the pixels)
- spawn point is above ground, player capsule exists, camera exists
- all GLBs in the manifest load (`Promise.allSettled` → report failures)
- audio context can start on first user gesture
- no 404s (log every failed request; a missing texture is usually a 404)

## 5. Movement and camera tests

Use `runControlsTest` from `references/controls.md` § 8. Required outcomes:

| Test | Assertion |
| --- | --- |
| forward speed | within ±10% of the tuned value |
| wall blocked | no penetration through a 0.2 m wall at sprint |
| stairs climbed | 30 cm risers ascend without jumping |
| slope limit | 45° walkable, 60° slides |
| camera collision | 0 frames with camera inside geometry over a 10 s sweep |
| fps independence | travel distance within 5% at 30/60/144 Hz |
| coyote time | jump works 100 ms after leaving a ledge |
| jump buffer | jump pressed 120 ms before landing fires |
| landing | no floor penetration at terminal velocity |
| pointer lock | acquire, release, re-acquire, no stuck state |

Also record a 60-second **input replay** (timestamped actions) and assert the
final position is within 5 cm across two runs. That is your regression test for
the entire controller.

## 6. Animation tests

From `references/animation.md` § 9, automated where possible:

- clip inventory matches `ANIMATION.md` (no missing `jump_land`)
- loop seams under 2° per track (`glb_audit.py --loop-check`)
- foot contact slip ≤ 3 cm/frame at walk and run
- no T-pose in the first 5 frames after spawn
- crossfade: max bone angular velocity during a transition < 4× median
- 20 characters on screen: mixer cost < 1.5 ms

## 7. World tests

- **Spline flythrough**: fixed path at 40 m/s, log unloaded tiles under the
  camera → 0 frames, max hitch < 100 ms.
- **Walkability**: run the road graph from start to each POI with the real
  controller, assert completion.
- **Collision coverage**: 200 random ground samples, downward ray, expect a hit
  within 0.5 m; ≥ 99%.
- **Story run**: a scripted route that completes every quest objective with no
  console errors. This is the only test that proves the game is a game.
- **Landmark frames**: 6 screenshots, same time of day, same camera pose, stored
  in `shots/world/` so regressions are visible.

## 8. Settings tests

- For each control: change it, assert the renderer/scene value actually changed
  (not just the store), then assert persistence after reload.
- Preset → Custom transition on any individual override.
- Corrupt the settings file (`{"resolutionScale":0}`) and boot: must fall back
  to safe values without a black screen.
- Keyboard-only and gamepad-only passes through every tab.
- Revert countdown fires and restores the previous display mode.

## 9. Performance capture

Measure at **each landmark**, not once:

```
Landmark        p50    p95    max    calls  tris      GPU
harbour         9.1    12.4   18.9   412    1.4M      integrated
market          11.8   15.2   24.1   690    2.1M      integrated
tower_view      8.4    11.0   15.2   301    1.8M      integrated
```

Rules: warm up 3 s, sample 20 s, report p95 (not average), record the hardware,
and never quote a single-frame number. Store in `PERF.md` with the settings tier
used. When a landmark fails, the fix order is: draw calls → shadow cascades →
transparency → post chain → resolution scale.

## 10. Visual review

Screenshots are not optional, and neither is looking at them. For each phase,
capture at 1920×1080:

1. spawn view
2. the hero landmark at golden hour
3. a close-up of a hero asset (material check)
4. a character in motion (mid-stride, 3/4 view)
5. the settings screen
6. a HUD-in-context frame

Then compare against your reference images and write down three specific
differences. "The wall texture is 1024² where the reference wall reads as 2048²
with a normal map" is a finding; "looks good" is not.

## 11. Reporting

`REPORT.md` gets a table that a reader can audit:

| Area | Check | Result | Evidence |
| --- | --- | --- | --- |
| Assets | 42 GLBs audited, all under budget | PASS | `assets/audit.json` |
| Movement | 10/10 controller tests | PASS | `shots/selftest.txt` |
| Camera | 0 clipped frames / 600 | PASS | `shots/selftest.txt` |
| Animation | 2 clips over budget on tris | WARN | `ANIMATION.md` § 4 |
| World | max streaming hitch 84 ms | PASS | `shots/perf.json` |
| Settings | gamepad nav untested (no pad) | NOT TESTED | — |
| Perf | p95 15.2 ms at market | FAIL | needs -2 ms |

And in the final chat message: what works, what is approximate, what was
substituted for licence reasons, what you could not test and why, and the
measured numbers. **Never report a check as passing if you only compiled it.**
Never write "verified" next to something you did not run. If the environment
cannot run a browser, say exactly that and hand the harness to the user.
