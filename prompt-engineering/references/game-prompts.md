# Game Prompts

A game prompt is a production brief, not a wish. The deliverable is an
*experience over time*, so "fun", "immersive" and "AAA" are not acceptance
criteria — they are adjectives that let the agent declare victory without
playing anything. Translate each one into something a build can pass or fail.

This is the game layer on top of `SKILL.md`. It borrows the production plan from
the `game-builder` skill; when that skill is available, point the prompt at it
instead of restating its phase details.

## 1. What makes game prompts different

| Property | Consequence for the prompt |
| --- | --- |
| The result is played, not read | Success needs a play trace and telemetry, not a file listing |
| Feel is the product | Input, camera and animation must have numeric checks |
| Scope expands by default | Exclusions, map size, system list and a stop condition are mandatory |
| Assets are legal and technical dependencies | Source policy, licence and attribution rules belong in the prompt |
| Work spans hours and context windows | Phase gates, `PLAN.md` and a progress file |
| "Looks done" is easy to fake | Screenshots, frame-time p95 and a self-test harness are the evidence |

The single highest-leverage line in any game prompt is a runnable self-test the
agent can execute. Give it one and it can close the loop; leave it out and it
will report "polished" from a static screenshot.

## 2. Classify the game prompt

Most game requests are one phase of a larger plan. Name the phase before writing
the prompt; a jam slice and a vertical slice need different boundaries.

| Type | Tell | The prompt must add |
| --- | --- | --- |
| Concept / design brief | "ideate a game", "what should the loop be" | player fantasy, loop, reference titles, one-screen pitch, what to cut |
| Jam prototype | hours, one mechanic, throwaway code | a hard timebox, one mechanic, explicit non-goals, no asset pipeline |
| Vertical slice | "show what the game is", one polished level | one mechanic + one environment + one UI screen, shipped-quality bar |
| Full game | many systems, story, menus | phase gates, scope contract, per-phase acceptance, `PLAN.md` |
| Feature / mechanic | "add a grapple", "make combat feel good" | the player-facing outcome, tuning numbers, feel tests, regression risks |
| Level / world | "build a city", "open world" | map size in metres, POI count, traversal path, streaming budget |
| Art / asset pass | "make it look AAA" | asset source policy, lighting/material gates, reference frames |
| UI / settings | "settings menu", "HUD" | information architecture, control types, persistence, gamepad nav |
| Bug / performance | "it stutters", "camera clips" | reproduction, target hardware, measured baseline, pass threshold |
| Playtest / review | "is it fun", "review the build" | observation protocol, evidence format, what not to fix |

If the user asks for a full game in one turn, say what fits in one turn: usually
a playable vertical slice. Write the rest as a plan, not as a prompt the agent
will fail to finish.

## 3. The game brief — the seven slots adapted

### 1. Role and objective

Name the player-facing outcome, not the technology:

- Weak: "build a 3D game with three.js."
- Strong: "Build a 10-minute vertical slice where the player crosses a flooded
  district to restart a lighthouse, using third-person traversal and one
  interaction verb."

Add a reference contract: which title's *feel* to match and which traits to
copy. "Like <game>" must name 3–5 concrete traits (camera, traversal, combat
pacing, UI density) and state what not to copy (assets, characters, names).

### 2. Context and inputs

Include only what the agent cannot discover:

- **Platform and hardware.** Desktop browser, integrated GPU, 1080p, 60 Hz —
  or mobile/console. This sets every budget.
- **Stack.** Existing repo and version, or the default from `game-builder`
  (three.js + Rapier + Vite).
- **Genre, camera, and scale.** First/third person, map size in metres, player
  count, session length.
- **Art direction.** Realism, stylised realism, or an explicit stylised look.
  "Low-poly" is only valid as a user decision, never as an agent shortcut.
- **Asset situation.** Available token/account, licensed packs, constraints.
- **Prior attempts and what failed.** "The camera clipped in the last build" is
  context; "make it better" is not.
- **What is out of scope.** Multiplayer, mobile, save systems, monetisation,
  procedural worlds — name the ones that are excluded.

### 3. Success criteria

Use four evidence families. A game prompt with only one of them is incomplete.

| Family | "Done when…" | Evidence |
| --- | --- | --- |
| **Playable** | the start→objective→end path completes with no console errors | scripted play trace, `runSelfTest()` output |
| **Feel** | input reaches the character; camera never enters geometry; feet do not slide; physics is frame-rate independent | telemetry table, input replay, recorded clip |
| **Look** | no untextured primitive appears in a shipped frame; landmark screenshots read as composed places | screenshots at named viewpoints, material audit |
| **Performance** | p95 frame time under budget at every landmark on the target hardware | 20 s sample, `renderer.info`, `PERF.md` |

Write the numbers into the prompt, not into a reference:

```text
Done when:
- A 60-second scripted run (spawn → bridge → lighthouse) completes with zero
  console errors and zero stuck frames.
- p95 frame time ≤ 14 ms at the three landmarks on integrated graphics,
  1080p; draw calls ≤ 400; on-screen triangles ≤ 1.5 M.
- Camera stays outside geometry for a 10-second 360° sweep in the test corner.
- Walk/run/jump/crouch work at 30, 60 and 144 Hz with travel distance within 5%.
- No T-pose frame on load; foot slip ≤ 3 cm/frame at walk and run.
- Landmark screenshots at golden hour show PBR materials, HDRI lighting and
  shadows; no grey-box geometry is visible.
Evidence: `shots/selftest.txt`, `shots/perf.json`, `shots/landmarks/*.png`,
and a 60-second screen recording.
```

If the user cannot supply a reference or hardware target, state an assumption
("mid-range laptop, integrated GPU, 1080p") and mark it in the plan.

### 4. Method

For anything larger than one mechanic, give phases with gates. The default is
the `game-builder` plan:

```
0 contract → 1 pipeline spike → 2 movement slice → 3 world
→ 4 characters/animation → 5 story/systems → 6 UI/settings → 7 verify
```

The prompt should say: finish one phase, run its gate, report, then continue.
"Do not start the next phase to escape a failing gate" is the line that stops
the agent from burying a broken controller under more content.

For a single mechanic, use: reproduce the current feel → instrument it → change
one tuning value → re-measure → report the delta. Cap tuning loops at 3.

### 5. Boundaries

Copy the shape, fill the values:

```text
In scope: <systems, map area, screens>.
Out of scope: multiplayer, mobile, monetisation, procedural world, save system,
  localisation. Do not add them.
Asset policy: authored or licensed assets only; no untextured primitives in a
  shipped frame; no image-to-3D for hero characters. Record every asset's
  source and licence; surface attribution in-game.
Forbidden shortcuts: grey-box geometry in a shown frame, disabling the player
  collider to fix a stuck spot, deleting/weakening a failing test, hiding a
  perf problem by lowering resolution silently.
Ask before: publishing, spending money, downloading a paid asset, changing
  account/store settings, deleting the user's files.
Default when ambiguous: infer from the existing repo and the stated reference;
  note the assumption. Ask only when a wrong guess costs more than one round-trip.
```

Add the legal boundary once, plainly: do not clone a trademarked character,
logo, or distinctive trade dress. Match mechanics and feel, not protected
assets.

### 6. Output contract

Games need more artifacts than a code diff:

```
Deliver: a runnable build (`npm run dev`), plus PLAN.md, PERF.md,
ANIMATION.md, CREDITS.md (licences + authors, also shown in-game),
assets/registry.json, and REPORT.md with the verification table.
Screenshots: spawn, hero landmark, close-up material, character in motion,
settings screen, HUD in context.
Final message: what works, what is approximate, what was substituted and why,
what could not be tested, and the measured p95 frame time. No adjectives.
```

The report format is part of the prompt. If you do not ask for a PASS/FAIL/NOT
TESTED table, you will get prose that reads like one.

### 7. Examples

Use a reference frame or a short clip when look or feel is contested. For scope,
use a contrastive pair:

```text
Good: "Vertical slice: one 300×300 m district, one traversal mechanic, one
interaction verb, one settings screen. 10 minutes of play."
Bad: "Open-world RPG with crafting, multiplayer, day/night cycle and a
20-hour story" — unbuildable in the requested turn; no gate can pass.
```

## 4. Translate the adjectives

| The user says | Write instead |
| --- | --- |
| "fun" | A 60-second loop with a clear goal, feedback within 100 ms of input, one meaningful choice per minute, and a reason to replay. Ask the playtest question the loop answers. |
| "smooth controls" | Input-to-motion latency; camera collision over a 360° sweep; coyote time 0.12 s; jump buffer 0.15 s; travel distance within 5% at 30/60/144 Hz. |
| "AAA graphics" | No untextured primitive in a shipped frame; albedo + normal + roughness on every material; HDRI + ACES + shadows; post stack at the shipped tier; p95 within budget; landmark screenshots. |
| "open world" | A traversable 1×1 km map with 6–8 POIs, a road loop, streaming hitch < 100 ms, and a scripted route from spawn through every POI. |
| "immersive" | Name the systems: positional audio by surface, camera shake/FOV kick, no HUD in the default view, ambient animation density (per 100 m²), one authored story prop per POI. |
| "polished UI" | Six settings categories from `game-builder`, every setting changes a real renderer/scene value and persists, full keyboard and gamepad navigation, revert countdown on display changes. |
| "like <game>" | 3–5 named traits to match (camera distance, traversal speed, combat cadence, UI density); explicitly do not copy assets, characters, names or logos. |
| "optimised" | p95 frame time at named landmarks on named hardware; draw calls and triangle ceilings; resolution-scale behaviour; first playable frame < 8 s. |

If you cannot find a check for an adjective, the adjective is not a requirement.
Ask one question or replace it with a concrete behaviour.

## 5. Asset and licence block

Games fail legally and technically on assets. Put this in every prompt that
produces visible content:

```text
Assets:
- Source order: Sketchfab (user token) → Mixamo → Poly Haven → ambientCG →
  Khronos samples → Quaternius/Kenney (only for a stylised direction) → paid
  pack → author it.
- No untextured primitives, no primitive-only scenes, no image-to-3D hero
  characters. A kitbashed authored kit is acceptable; boxes are not.
- SKETCHFAB_TOKEN lives in .env, server-side only. Never in client code, the
  repo, a log or chat. If it is missing, ask once and continue with the ladder.
- Every asset gets an entry in assets/registry.json with source, author,
  licence and audit numbers. CC-BY attribution ships in-game and in CREDITS.md.
- NC assets cannot ship commercially; ND assets cannot be optimised or
  retargeted, so treat them as unusable.
- Do not reproduce trademarked characters, logos or trade dress.
```

If the prompt omits this, the agent will either invent geometry or download
something it cannot legally ship. Both are expensive to undo.

## 6. Verification and playtest prompts

A game prompt must name the harness, not just the goal:

```text
Expose window.__game under ?debug=1 only. Provide runSelfTest() that returns
PASS/FAIL lines for: load, first frame non-black, spawn above ground, all GLBs
loaded, input reaches character, wall blocked, stairs climbed, camera never
inside geometry, fps independence, coyote time, jump buffer, settings persist.
Wire it into `npm run verify`; the command must exit non-zero on failure.
```

For a review or playtest prompt, specify observation over opinion:

```text
Play for 10 minutes from a fresh save. Record: time to first control, time to
first objective, deaths/softlocks, frames where input was ignored, camera
clips, and three moments where you were unsure what to do. Do not fix anything;
report findings with timestamps and screenshots.
```

Then a second prompt fixes one finding at a time with a before/after measurement.
A review that also rewrites the game produces neither a clean finding nor a
clean fix.

## 7. Copyable prompt shapes

### A. Jam prototype (timeboxed)

```text
Build a <genre> prototype in <engine> that runs in one turn.
Core loop: <one sentence>. One mechanic only: <mechanic>.
Success: the loop is playable for 60 seconds from `npm run dev`, with
<specific feedback> and no console errors. Use primitive geometry deliberately
and say so; do not start an asset pipeline.
Out of scope: menus, saves, audio polish, story, mobile.
Return: the build, a 5-line controls list, and what you would cut next.
```

### B. Vertical slice

```text
Build a 10-minute vertical slice of <game> for <platform/hardware>.
One mechanic, one 300×300 m environment, one UI screen, shipped-quality look.
Use the phase gates in the game-builder skill: contract → pipeline spike →
movement slice → world → characters → systems → UI → verify.
Done when <the four evidence families with numbers>.
Asset policy: <block from §5>.
Return: runnable build, PLAN.md, PERF.md, REPORT.md, screenshots.
Stop and report if a gate fails; do not add content to compensate.
```

### C. Mechanic / feel spec

```text
Make <mechanic> feel like <reference trait>. Current behaviour: <symptom>.
Target: <numbers — speed, acceleration, cooldown, latency, camera response>.
Instrument it first: log <metrics> behind ?debug=1.
Change one tuning value at a time, re-measure, max 3 iterations, then report a
before/after table. Do not change unrelated systems or visuals.
```

### D. Level / POI

```text
Build <POI> inside the existing map at <coordinates>, <size>.
Traversal requirement: <route> completable with the real controller.
Composition: one hero landmark visible from spawn, 2 storytelling props,
<density> per 100 m², 3 authored variants per repeated prop.
Done when: route completes, no holes/stuck spots, 6 landmark screenshots at
<time of day>, p95 still within budget.
Do not expand the map or add new mechanics.
```

### E. Art / asset pass

```text
Raise the frame from tech-demo to shipped-quality. Do not change gameplay.
Targets: no untextured primitives; PBR on every material; HDRI + ACES +
shadows; <post stack>; decals on large surfaces; consistent texel density.
Use the asset ladder; record every replacement in assets/NOTES.md.
Done when: before/after screenshots at 3 named viewpoints, asset audit passes,
p95 within <budget>. Report substitutions and visible differences.
```

### F. Settings / UI screen

```text
Build the settings screen to the anatomy in game-builder's
references/settings-menu.md: six categories, measured row heights, one accent,
tabular values, Apply/Revert, revert countdown on display changes, persistence
with schema version and clamp-on-load.
Every control must change a real value and be operable by mouse, keyboard and
gamepad. No cosmetic presets.
Done when: the verification checklist in that reference passes; screenshot the
result next to 3 reference screenshots and list the differences.
```

### G. Bug / performance

```text
Symptom: <what the player sees>. Reproduce: <steps>, on <hardware>.
Measure a baseline first: p50/p95/max, draw calls, triangles, at <landmark>.
Fix the cause, not the symptom. Re-measure with the same method.
Pass: p95 ≤ <target> and the repro no longer occurs; no visual regression in
the landmark screenshot. Report the before/after numbers and files changed.
```

## 8. Long-horizon and multi-agent

- **One phase per prompt/session.** Cross-phase prompts dilute the gate.
- **`PLAN.md` is the contract**, updated at each gate with what passed, what
  failed, and the next step. A fresh session reads it first.
- **Subagents get narrow briefs**: "audit these 12 GLBs and return a table" or
  "dress this 100 m street and return screenshots + a prop list". The lead owns
  synthesis and final verification.
- **Context is finite.** Point at `game-builder/references/*` and the repo; do
  not paste tables of tuning values the agent can read.
- **Stop conditions**: gate fails twice → stop and report the blocker; do not
  spend the budget on a different subsystem.

## 9. Anti-patterns

- **"Make it fun" as acceptance.** No check, no failure, no fix.
- **"AAA" as an adjective.** It means materials, lighting, motion and UI craft;
  say which.
- **Grey-box in the final frame.** Allowed only as a movement-test scaffold.
- **"Low-poly" as an escape hatch.** A valid art direction the user chooses,
  never a reason not to source or author assets.
- **Full-game scope in one turn.** Multiplayer + open world + story + mobile.
- **Engine ambiguity.** "Use whatever" when deployment, assets or tooling
  depend on the choice.
- **Prescribing internals over outcomes.** "Use an ECS with 14 systems" is not
  a requirement; "20 NPCs under 1.5 ms mixer cost" is.
- **No asset/licence policy.** Guarantees either placeholders or legal debt.
- **No evidence requirement.** Produces confident false reports.
- **A review prompt that also fixes.** Findings and fixes blur; nothing is
  measured.
- **Asking for a copyrighted clone.** Match mechanics and feel; refuse assets,
  names and logos.

## 10. Model adjustments

| Family | Lean on | Avoid |
| --- | --- | --- |
| **Claude** | Phase gates, explicit evidence, XML/Markdown sections, stated reasons | Massive rule piles; forcing visible chain-of-thought for a long build |
| **GPT-5 / reasoning models** | Goal, scope, stop criteria, tool boundaries, concise output contract | "Be maximally thorough"; prescribed internal reasoning |
| **Gemini** | Stable context first, task last, one delimiter system, explicit format | Mixed XML/Markdown; assuming it will add polish detail |
| **Smaller / faster models** | One mechanic per prompt, numbered phase checklist, a single runnable test, tight context | Whole-game prompts; implicit quality bars |

## 11. Worked before/after

**Before**

```text
make me a fun 3D game with nice graphics
```

**Why it fails:** "fun" and "nice graphics" are unmeasurable; there is no
platform, scope, stack, asset policy or evidence requirement. The agent will
build a grey-box demo and call it done.

**After**

```text
Build a 10-minute third-person vertical slice in three.js + Rapier + Vite for
a mid-range laptop (integrated GPU, 1080p, 60 Hz). The player crosses a flooded
district to restart a lighthouse; one traversal mechanic (sprint/jump/vault)
and one interaction verb.

Context: <repo or new>; art direction is grounded realism, not low-poly; assets
follow the ladder in the attached asset policy; <reference game> is the feel
reference for camera distance and traversal speed only.

Done when:
- spawn → bridge → lighthouse completes in one 60 s scripted run with no console
  errors and no stuck frames;
- p95 ≤ 14 ms and ≤ 400 draw calls at the three landmarks;
- camera outside geometry for a 10 s sweep; no foot slip > 3 cm/frame;
- no T-pose on load; travel distance within 5% at 30/60/144 Hz;
- three landmark screenshots show PBR materials, HDRI lighting and shadows;
- no untextured primitive appears in any shipped frame.
Evidence: shots/selftest.txt, shots/perf.json, shots/landmarks/*.png, 60 s clip.

Method: use the game-builder phase gates (contract → pipeline spike → movement
slice → world → characters → systems → UI → verify). Finish and verify one
phase before the next. If a gate fails twice, stop and report the blocker.

Boundaries: no multiplayer, mobile, saves, monetisation or procedural world.
Do not expand the map past 300×300 m. Ask before spending money or publishing.

Return: runnable build, PLAN.md, PERF.md, CREDITS.md, REPORT.md with a
PASS/FAIL/NOT TESTED table, and the measured numbers in the final message.
```

**What changed:** a playable outcome, a platform and stack, an asset and IP
boundary, four evidence families with numbers, phase gates, stop conditions and
an output contract. Nothing in it says "fun" — and it is far more likely to
produce a game that is.

## 12. Pointers into game-builder

| The prompt needs… | Read |
| --- | --- |
| asset sourcing, licences, audit thresholds, fallback ladder | `game-builder/references/assets.md` |
| lighting, materials, post stack, quality tiers | `game-builder/references/rendering.md` |
| controller numbers, camera rig, feel tests | `game-builder/references/controls.md` |
| retargeting, blend spaces, foot contact | `game-builder/references/animation.md` |
| map scale, streaming, modular kits, set dressing | `game-builder/references/world.md` |
| settings IA, tokens, apply/revert, persistence | `game-builder/references/settings-menu.md` |
| definition of done, harness, perf capture, honest reporting | `game-builder/references/verification.md` |

Do not paste those references into the prompt. Name the file and the decision
the agent should take from it.
