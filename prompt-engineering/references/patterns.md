# Pattern Library

Copyable skeletons for common jobs. Each pattern lists when to use it, the prompt shape, and the failure it prevents.

| If the job is… | Use |
|---|---|
| Underspecified but important | Spec interview |
| A bug with a reproducible symptom | Repro → failing test → fix → verify |
| A feature in an existing codebase | Explore → plan → execute → verify |
| Behavior-preserving cleanup | Refactor under invariants |
| A document, article, or message | Deliverable contract |
| A question requiring sources | Research brief with evidence |
| Unstructured input into fields | Extract to schema |
| Subjective quality with a bar | Rubric-driven generation |
| A diff or proposal that needs scrutiny | Adversarial review |
| A task too big for one prompt | Prompt chain |
| Output that must improve over attempts | Evaluator-optimizer |
| An edit that must preserve voice | Constrained rewrite |
| An agent with several tools | Tool policy block |
| Work spanning context windows | Long-horizon state block |
| One input that must go down one path | Classification / routing |
| A playable game, prototype, or vertical slice | Game brief with phase gates |
| A mechanic that must feel right | Feel spec with telemetry |
| A build that must be judged, not praised | Playtest review |

## 1. Spec interview

**Use when:** the user knows the goal but not the details, or the cost of a wrong assumption is high.

```text
I want to <goal>, but I have not specified it fully. Interview me until you could write a precise spec.
Ask one question at a time, prefer multiple-choice where possible, and focus only on choices that would change the implementation.
When you have enough, write the spec to SPEC.md with: goal, users, in scope, out of scope, acceptance criteria, open questions.
```

**Prevents:** building the wrong thing confidently. Pairs well with a fresh session for implementation.

## 2. Repro → failing test → fix → verify

**Use when:** a bug has a symptom but no reliable reproduction.

```text
Bug: <symptom>. Expected: <...>. Actual: <...>.
Steps: <...>. Relevant area: <paths>.

1. Reproduce the bug; report the exact command and output.
2. Write a failing test that demonstrates it.
3. Fix the root cause, not the symptom.
4. Rerun the test and the surrounding suite.
5. Report: root cause, changed files, test evidence, and any residual risk.

Do not modify unrelated tests. Do not claim a fix without a passing reproduction test.
```

**Prevents:** symptom patching, unverified "fixed", and test weakening.

## 3. Explore → plan → execute → verify

**Use when:** a feature touches unfamiliar code or multiple files.

```text
Task: <feature>.
Success: <observable behavior + check command>.

Phase 1 — Explore: read the closest existing implementation and the relevant tests. Do not edit yet.
Phase 2 — Plan: list files to change, the approach, risks, and verification. If two approaches are materially different, state the trade-off and pick one with a reason.
Phase 3 — Execute: implement in small steps, following existing patterns. Keep the diff scoped.
Phase 4 — Verify: run <tests/lint/build>; exercise the golden path and <edge case>. Report evidence.

Stop exploring when you can name the exact files and functions to change.
```

**Prevents:** editing before understanding, and finishing without proof.

## 4. Refactor under invariants

**Use when:** restructuring code without changing behavior.

```text
Refactor <target> to <target structure>.

Invariants:
- Public API and behavior unchanged.
- Existing tests pass without modification.
- No new dependencies.
- <Performance / compatibility / style invariant>.

Work incrementally. After each step, run <check>. If an invariant would break, stop and explain rather than improvising.
Report: what moved, what stayed, and the evidence that behavior is unchanged.
```

**Prevents:** refactors that silently change behavior or balloon in scope.

## 5. Deliverable contract

**Use when:** writing an article, report, email, proposal, or documentation.

```text
Write <deliverable> for <audience>.
Purpose: <what the reader should do or believe afterward>.
Voice: <tone, person, formality>. Match this sample: <short sample>.
Must include: <points>.
Must avoid: <claims, clichés, jargon, length>.
Length: <words/paragraphs/sections>.
Structure: <headings/bullets/prose>.
If a fact is uncertain, mark it as uncertain rather than asserting it.

Return only the deliverable; no preamble.
```

**Prevents:** generic prose, wrong register, and unrequested commentary.

## 6. Research brief with evidence

**Use when:** the answer depends on sources, recency, or conflicting claims.

```text
Question: <precise question>.
Scope: <time range, geography, population>.
Sources: prefer <tier 1>; allow <tier 2>; exclude <tier 3>.
For every factual claim, cite the source inline.
When sources disagree, report the disagreement and the strongest evidence on each side.
Label each finding: verified / inferred / unknown.
Stop when each major claim has two independent sources, or when new searches return nothing new.
If the evidence cannot answer the question, say so and name what would settle it.
```

**Prevents:** unsourced synthesis, false confidence, and endless searching.

## 7. Extract to schema

**Use when:** converting documents, transcripts, or pages into structured data.

```text
Extract the following fields from <input>: <field list>.
Return valid JSON matching this schema: <schema>.
Rules:
- Use null when a field is absent or not stated. Do not guess.
- Preserve original wording for quoted fields.
- Include a `source` pointer (page, paragraph, timestamp) for each record.
- If the input is ambiguous, add a `notes` field rather than resolving it silently.
```

**Prevents:** fabricated values and unparseable output. Use the provider's structured-output feature when available.

## 8. Rubric-driven generation

**Use when:** quality is subjective but a high bar is definable (design, copy, plans).

```text
Produce <deliverable>.
Before writing, define a private rubric with 5–7 criteria that a top-tier result must satisfy: <example criteria>.
Draft, score yourself against each criterion, and revise until every criterion is met.
Do not show the rubric or the scoring.
Favor <simplicity / boldness / clarity> over safe defaults.
```

**Prevents:** mediocre first drafts and vague "make it good" instructions. OpenAI's GPT-5 guide documents this "hidden rubric" pattern for zero-to-one work.

## 9. Adversarial review

**Use when:** you need real defects found, not reassurance.

```text
Review <artifact> against <spec / requirements / threat model>.
Report only issues that affect correctness, safety, or the stated requirements. Skip style and speculative improvements.
For each finding: severity, file/line, concrete failure scenario, and the smallest fix.
If you find nothing material, say so. Do not invent findings to fill a quota.
```

**Prevents:** nitpick avalanches and false confidence. The "skip style" clause matters: a reviewer asked to find problems will always find something.

## 10. Prompt chain

**Use when:** one prompt is trying to do research, decide, write, and check at once.

```text
Step 1 — <extract / summarize>: output <artifact A>.
Step 2 — <analyze / critique>: input A; output <artifact B>.
Step 3 — <produce>: input A + B; output <final artifact>.
```

Use a programmatic gate between steps when the output must meet a schema or threshold. Keep each step narrow; pass forward only what the next step needs.

**Prevents:** diluted attention and compounding ambiguity.

## 11. Evaluator-optimizer

**Use when:** a clear rubric exists and iteration measurably improves the result.

```text
Generator: produce <artifact> for <goal>.
Evaluator: score the artifact against <rubric>; list concrete defects with evidence.
Loop: revise only the defects; stop when the score is <threshold> or after <N> rounds.
Return the final artifact plus the evaluator's last report.
```

Do not loop on vague criteria; the evaluator will oscillate. Anthropic recommends this pattern when evaluation is clear and iterative refinement helps.

## 12. Constrained rewrite

**Use when:** editing text while preserving voice, facts, or structure.

```text
Rewrite <text> to <goal: shorten / simplify / change tone / fit length>.
Preserve: <facts, terminology, voice, structure, examples>.
Change only: <what may change>.
Constraints: <word budget, reading level, banned words>.
Show the rewrite only. If preserving a fact conflicts with the goal, keep the fact and note the conflict.
```

**Prevents:** silent fact changes and voice drift.

## 13. Tool policy block

**Use when:** the agent has overlapping tools or a history of choosing wrong.

```text
Tool policy:
- <intent A> → <tool A>.
- <intent B> → <tool B>. Do not use <tool A> for B because <reason>.
- Read before edit. Batch independent reads; sequence writes.
- Stop exploring when <condition>.
- If a tool fails twice, report the error instead of retrying variants indefinitely.
```

**Prevents:** tool thrash, duplicate calls, and unnecessary latency.

## 14. Long-horizon state block

**Use when:** the task will span many steps or multiple context windows.

```text
Maintain <PROGRESS.md / task list> with: completed work, current state, open questions, next step.
Update it after each meaningful milestone. Record decisions and why, not just actions.
Before context is compacted, save anything a fresh session would need.
Work in verified increments. Do not stop early because the task is long.
On resume: read the progress file, the test state, and the git log before acting.
```

**Prevents:** repeated work, lost decisions, and premature stops.

## 15. Classification / routing

**Use when:** one input must be sent down one of several paths.

```text
Classify <input> into exactly one of: <labels>.
Definitions: <one line per label, including the boundary case>.
If no label fits, return `unclear` and the reason.
Return only the label.
```

Add one example per boundary if labels are commonly confused. For high-stakes routing, ask for a confidence and route low-confidence cases to a human.

## 16. Game brief with phase gates

**Use when:** the user wants a playable game, prototype, or vertical slice.

```text
Build <player-facing outcome> for <platform/hardware>, <session length>.
Genre/camera: <...>. Scope: <map size, systems, screens>.
Art direction: <realism / stylised realism / explicit stylised look>.
Assets: <ladder + licence policy; no primitives in a shipped frame>.

Done when:
- <60 s scripted path completes, no console errors>
- <p95 frame time / draw calls / tris at named landmarks>
- <camera, foot-slide, fps-independence, no T-pose checks>
- <landmark screenshots show materials, lighting, shadows>
Evidence: <self-test output, perf JSON, screenshots, clip>.

Method: use the game-builder phase gates. Finish and verify one phase before
the next. If a gate fails twice, stop and report the blocker.

Boundaries: out of scope <...>. Ask before <publish/spend/delete>.
Return: runnable build, PLAN.md, PERF.md, CREDITS.md, REPORT.md with a
PASS/FAIL/NOT TESTED table and measured numbers.
```

**Prevents:** "fun" as a stop condition, grey-box shipped as final, and a
full game attempted in one turn.

## 17. Feel spec with telemetry

**Use when:** a mechanic works but feels wrong, and "make it smoother" would be
a guess.

```text
Make <mechanic> feel like <reference trait>. Current: <symptom>.
Targets: <speed / acceleration / latency / camera distance / cooldown>.
First expose metrics behind ?debug=1: <what to log>.
Change one tuning value, re-measure, max 3 iterations.
Report a before/after table with the measured numbers and the exact clip.
Do not change unrelated systems, content, or visuals.
```

**Prevents:** tuning by vibe, shotgun rewrites, and unverified "feels better".

## 18. Playtest review

**Use when:** you need a judgement of a build before spending more on it.

```text
Play from a fresh save for <duration>. Do not fix anything.
Record: time to first control, time to first objective, softlocks/deaths,
frames where input was ignored, camera clips, and three moments of confusion.
For each finding: timestamp, screenshot, severity, and the smallest fix.
If you find nothing material, say so; do not invent findings.
```

**Prevents:** reviews that mutate the build, and nitpick lists with no evidence.

