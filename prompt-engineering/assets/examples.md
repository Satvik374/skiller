# Worked Examples

Six before/after rewrites. Each shows the failure, the rewritten prompt, and the design choices.

## 1. Coding agent — bug fix

**Before**

```text
fix the login bug
```

**Why it fails:** no symptom, no location, no reproduction, no definition of fixed, no evidence requirement. The agent must guess, then declare victory.

**After**

```text
Act as a senior engineer working in this repository. Fix the login failure that occurs after a session times out.

Context:
- Users report being redirected to the login page after ~30 minutes of inactivity, even with "remember me" enabled.
- Auth code lives in src/auth/; session handling is in src/auth/session.ts.
- The bug reproduces in staging, not locally.

Success criteria:
- A new test in tests/auth/ reproduces the timeout failure.
- The test passes after the fix.
- The existing auth suite still passes.
- No change to the public auth API.

Method:
1. Read src/auth/session.ts and the existing auth tests. Do not edit yet.
2. Write a failing test that demonstrates the bug.
3. Fix the root cause, not the symptom. Keep the diff minimal and match existing patterns.
4. Run the new test, then the full auth suite. Report the commands and output.

Boundaries:
- Do not modify unrelated tests, rename files, or add dependencies.
- If the root cause is outside src/auth/, stop and explain before expanding scope.

Output:
Report: root cause, files changed, test evidence, residual risk.
```

**What changed:** observable symptom + location + reproduction + a runnable done condition + scope guard + evidence requirement.

## 2. Research agent — market question

**Before**

```text
research the EV market and write a report
```

**Why it fails:** no question, geography, time range, source standard, or output shape. The result will be a generic summary with no way to check it.

**After**

```text
Research the following question: How did global passenger EV sales and average battery pack prices change from 2022 to 2025, and what are the two most credible explanations for the trend?

Scope:
- Global, with China, Europe, and the US called out separately.
- Prefer primary sources: IEA, BNEF, national statistics agencies, company filings. Industry blogs only for leads, not final claims.
- Include data published through 2026.

Method:
- For each major claim, cite the source inline with a link and publication date.
- Where sources disagree, report the disagreement and the strongest evidence on each side rather than averaging it.
- Label each finding as verified, inferred, or unknown.
- Stop when each major claim has two independent sources, or when further searching returns nothing new.

Output:
- One-paragraph answer.
- A table: year, region, sales, average pack price, source.
- Three bullets on the most credible explanations, each with evidence.
- A short "what would change this conclusion" section.

If the evidence cannot answer part of the question, say so explicitly and name what would settle it. Do not fill gaps with plausible guesses.
```

**What changed:** a precise question, explicit scope, source hierarchy, citation rule, disagreement handling, uncertainty vocabulary, and a parseable output shape.

## 3. Writing — launch announcement

**Before**

```text
write a blog post about our new feature
```

**Why it fails:** no audience, purpose, voice, length, or must-include facts. The model defaults to generic marketing prose.

**After**

```text
Write a 600–800 word blog post announcing <feature> for <product>.

Audience: existing users who are technical but not specialists.
Purpose: they should understand what changed, why it matters, and how to try it in under five minutes.
Voice: direct, concrete, lightly conversational. Match this sample: <paste 2–3 sentences>.
Must include:
- The problem the feature solves.
- One concrete before/after example.
- How to enable it, including the exact menu path.
- One limitation and who should not use it yet.
Must avoid: superlatives, "revolutionary", "seamless", em-dash-heavy lists, and claims not in the notes below.
Facts: use only the notes below; mark anything uncertain as "not yet confirmed".

Output: Markdown with a title, three or four H2 sections, and no preamble. Do not add a conclusion that repeats the introduction.
```

**What changed:** audience and purpose, a voice sample, hard content requirements, a banned-phrase list, a length budget, a fact boundary, and an output contract.

## 4. Ops agent — clean up a downloads folder

**Before**

```text
clean up my downloads folder
```

**Why it fails:** "clean up" is undefined and destructive. The agent decides what is junk, and the user finds out afterward.

**After**

```text
Act as a careful file-operations assistant. Propose a cleanup plan for C:\Users\me\Downloads. Do not delete or move anything yet.

Rules:
- Read-only inspection first. Produce a plan and a dry-run summary.
- Group files by type and age: installers, archives, images, documents, duplicates, unknown.
- Never touch: .git folders, source-code directories, files modified in the last 30 days, anything with "invoice", "tax", or "backup" in the name, and any folder containing a .git directory.
- Identify duplicates by content hash, not filename alone.
- Do not open or upload file contents.

Plan output:
| Group | Count | Total size | Proposed action | Risk |
Then list every file proposed for deletion with its full path and reason.

Ask for confirmation before executing. When confirmed:
- Move deletions to a quarantine folder, do not permanently delete.
- Write a manifest of every move (source, destination, timestamp).
- Report what changed and how to undo it.

If a file is ambiguous, leave it and list it under "needs review".
```

**What changed:** read-only first, explicit protected categories, a dry-run artifact, confirmation before action, reversible execution, and an undo path. Destructive tasks need all five.

## 5. Debugging a prompt — website request

**Before**

```text
make me a good website
```

**Diagnosis:**

| Symptom | Cause |
|---|---|
| Generic result | "Good" is undefined; no audience or purpose |
| Unbounded scope | No page list, content, or constraints |
| Unverifiable | No definition of done |
| Format drift | No technical constraints or output shape |

**After**

```text
Build a one-page marketing site for <product>, a <one-line description>.

Audience: <who>; the page should convince them to <action>.
Content: use the copy in <file/link>; do not invent claims.
Required sections: hero, three benefits, one testimonial, pricing summary, footer with contact.
Technical constraints:
- Single index.html with embedded CSS; no build step, no frameworks.
- Responsive at 360px, 768px, and 1280px.
- Semantic HTML, visible focus states, AA contrast.
- No external images; use CSS shapes or provided assets in assets/.

Done when:
- The page opens directly from disk with no console errors.
- All three breakpoints render without horizontal scroll.
- Every link and button has a target or is explicitly marked as a placeholder.

Output: the full index.html in one fenced block, then a short list of what you would improve with more time.
```

**What changed:** audience and conversion goal, supplied copy, a section list, technical constraints that can be checked, three breakpoints, a done definition, and an output contract.

## 6. Game build — vertical slice

**Before**

```text
make me a fun 3D game with nice graphics
```

**Why it fails:** "fun" and "nice graphics" are unmeasurable; there is no
platform, scope, stack, asset policy, or evidence requirement. The agent will
build a grey-box demo, screenshot it, and call it done.

**After**

```text
Build a 10-minute third-person vertical slice in three.js + Rapier + Vite for a
mid-range laptop (integrated GPU, 1080p, 60 Hz). The player crosses a flooded
district to restart a lighthouse; one traversal kit (sprint/jump/vault) and one
interaction verb.

Context:
- New repo. Grounded realism, not low-poly.
- Map: one 300×300 m district. Session length: 10 minutes.
- Feel reference: <game> for camera distance and traversal speed only — do not
  copy assets, characters, names, or logos.
- Assets: use the ladder (Sketchfab token → Mixamo → Poly Haven → ambientCG →
  Khronos → paid → author). No untextured primitives in a shipped frame. Keep
  SKETCHFAB_TOKEN in .env, server-side only.

Done when:
- Spawn → bridge → lighthouse completes in one 60-second scripted run with zero
  console errors and zero stuck frames.
- p95 frame time ≤ 14 ms at the three landmarks; draw calls ≤ 400; on-screen
  triangles ≤ 1.5 M.
- Camera stays outside geometry for a 10-second 360° sweep in the test corner.
- Walk/run/jump/crouch work at 30, 60 and 144 Hz with travel distance within 5%.
- No T-pose on load; foot slip ≤ 3 cm/frame at walk and run.
- Landmark screenshots at golden hour show PBR materials, HDRI lighting and
  shadows; no grey-box geometry is visible.
Evidence: shots/selftest.txt, shots/perf.json, shots/landmarks/*.png, 60 s clip.

Method:
- Use the game-builder phase gates: contract → pipeline spike → movement slice
  → world → characters → systems → UI → verify.
- Finish and verify one phase before starting the next. If a gate fails twice,
  stop and report the blocker; do not add content to compensate.
- Tune movement one value at a time, max 3 iterations, with before/after numbers.

Boundaries:
- Out of scope: multiplayer, mobile, saves, monetisation, procedural world,
  localisation. Do not add them.
- Never ship primitive geometry, disable the player collider to fix a stuck
  spot, or lower resolution silently to hide a perf problem.
- Ask before publishing, spending money, or deleting files.

Output:
- Runnable build (`npm run dev`), plus PLAN.md, PERF.md, CREDITS.md,
  assets/registry.json, and REPORT.md with a PASS/FAIL/NOT TESTED table.
- Screenshots: spawn, hero landmark, material close-up, character mid-stride,
  settings screen, HUD in context.
- Final message: what works, what is approximate, what was substituted and why,
  what could not be tested, and measured p95 — no adjectives.
```

**What changed:** a playable outcome, platform and stack, a bounded map and
session, an asset/licence policy, an IP boundary, four evidence families with
numbers, phase gates with a stop condition, and a report contract. Nothing says
"fun"; the prompt is far more likely to produce a game that is.
