---
name: prompt-engineering
description: Write, diagnose, and improve prompts for AI agents and LLMs. Use when the user wants a prompt created for coding, research, browser, writing, automation, or game-building work; when a prompt produces vague, inconsistent, or overreaching results; or when designing agent tool use, planning, verification, and acceptance criteria. Draws on Anthropic, OpenAI, Google, and Microsoft guidance plus patterns from production agent prompts.
metadata:
  version: "2"
  updated: "2026-11-19"
---

# Prompt Engineering

A prompt is a specification for work, not a wish. Write for a competent stranger: someone with the tools and skill to do the job, but none of your context.

Perfect is not the goal; reliable is. The strongest prompt is usually the smallest one that consistently produces the outcome you can verify.

This skill produces **task prompts** — what a person pastes into an agent to get work done. It is not for writing a product's persistent system prompt, persona, or safety policy. If the user asks for a system prompt, say so and adapt: keep deployment-wide policy out of the task prompt.

## When this skill applies

Use it to:

- turn a rough request into a prompt for a coding, research, browser, or general agent
- write or repair prompts for game prototypes, vertical slices, mechanics, levels, art passes, or game UI — where "fun" and "AAA" must become measurable
- repair a prompt that is vague, overlong, contradictory, or unreliable
- add planning, tool-use, verification, or stop conditions to an agent brief
- define acceptance criteria, output contracts, and autonomy boundaries
- review prompts against current vendor guidance

Do not use it to help bypass safety controls, extract hidden system prompts, or make prompts deceptive.

## Step 1 — Classify the task

Ask only the questions whose answers change the prompt. If the user already supplied enough, state assumptions and proceed.

| Dimension | Question | Why it changes the prompt |
|---|---|---|
| Task type | One answer, a tool-using agent, or long-horizon work? | Determines planning, state, and verification |
| Domain | Is this a game or playable build? | Adds player-facing acceptance, performance budgets, asset/licence policy, and phase gates (see [Game prompts](references/game-prompts.md)) |
| Evidence | Can the result be played, run, or diffed? | Prefer a play trace and self-test over a written claim |
| Stakes | Reversible, or destructive / external / shared? | Determines autonomy and confirmation rules |
| Inputs | Files, links, screenshots, data, prior attempts? | Determines the context block and retrieval strategy |
| Done | How will success be checked? | Determines acceptance criteria and evidence |
| Consumer | Human reader, parser, or another agent? | Determines the output contract |
| Model | Claude, GPT, Gemini, local, or unknown? | Determines structure and reasoning guidance |

If an answer is unavailable, choose a sensible default, label it as an assumption, and continue. Do not interrogate the user for preferences that have an obvious default.

Also decide whether the deliverable is **one-off** or **reusable**. A one-off prompt inlines the actual file names, copy, and constraints the user supplied. A reusable prompt uses bracketed placeholders and ends with a short "fill these in" list. Never leave placeholders in a one-off prompt.

## Step 2 — Fill the seven slots

| # | Slot | What to write |
|---|---|---|
| 1 | **Role and objective** | Who the agent acts as, the observable outcome, and why it matters. One or two sentences. |
| 2 | **Context and inputs** | What the agent needs and where it is; decisions, constraints, prior attempts, and unknowns. |
| 3 | **Success criteria** | "Done when…" plus the command, evidence, or rubric that proves it. |
| 4 | **Method** | Phases and order; tool routing; parallel vs sequential work; retry cap; stop conditions. |
| 5 | **Boundaries** | In scope, out of scope; ask-vs-assume policy with defaults; risky actions needing confirmation. |
| 6 | **Output contract** | Format, structure, length, citations, tone, and how to express uncertainty. |
| 7 | **Examples** | One good example; add an anti-example when the boundary is a judgment call. |

**Short form** (most one-shot tasks): slots 1, 2, 3, 6.
**Agent form** (tools, multiple steps, or side effects): add 4 and 5.
**Format-sensitive or high-stakes form**: add 7.

Do not include a slot that carries no information. An empty heading teaches the model that headings are decoration.

### How to write each slot

**Objective.** Use a verb with an observable result — "reduce p95 latency below 200 ms", "produce a five-row comparison", "rewrite for a 12-year-old". Not "improve", "optimize", "make it good".

**Context.** Include only what the agent cannot discover by looking: a decision made in a meeting, a deploy step that lives in someone's head, a preference between two reasonable options, a prior attempt that failed. Do not restate the repository, the document, or the obvious. For long material, point to it (`src/auth/`, the attached log) and say what to look for.

**Success.** Say "done when" and name the evidence. Prefer a runnable check: a test command, a build exit code, a diff against a fixture, a screenshot beside a mockup. If the goal is subjective, give a 3–5 criterion rubric with what a top score looks like.

**Method.** Specify sequence only where order matters. For agents, route by intent: which tool answers which question, when *not* to use a tool, what can run in parallel, and when exploration is sufficient. Cap repair loops and say what happens at the cap.

**Boundaries.** State the ask-vs-assume policy explicitly: "infer 1–2 reasonable assumptions from existing conventions and note them; ask only when truly blocked" or "ask before choosing among materially different approaches". Name the default for each likely ambiguity. State exclusions, not just inclusions. For anything hard to reverse, require confirmation and list examples.

**Output.** Match the consumer. Quantify length ("under 150 words", "five bullets", "one fenced block"). If a parser reads it, give the schema or an exact template. Say what "I don't know" or "not found" should look like. State whether to include reasoning, a summary, or evidence.

**Examples.** Use 1–3 realistic, diverse examples. Keep formatting identical across them. For judgment calls, show a good and a bad example with a one-line reason. Examples are the most reliable way to fix format drift.

## Step 3 — Draft with the smallest structure that works

Start from [the prompt template](assets/prompt-template.md). Prefer plain prose plus a short output contract. Add sections only when the task has separable concerns.

- Put stable context first and the specific request last when the prompt is long. Models attend strongly to the end.
- Use one delimiter system consistently: Markdown headings or XML-style tags, not both for the same hierarchy.
- Explain the reason behind non-obvious rules. "Use flowing prose because this will be read aloud" generalizes better than "NEVER use bullets".
- Phrase constraints positively where possible: say what to do, not only what to avoid.
- When two instructions could conflict, rank them explicitly ("correctness over speed"; "existing tests win over new abstractions").

## Step 4 — Red-team the prompt

Run the quality gates before delivering. Fix every failure or call it out as a deliberate trade-off.

- [ ] A competent colleague with no context could execute it.
- [ ] The objective names an observable outcome, not an adjective.
- [ ] "Done" is checkable, or has a written rubric.
- [ ] Every vague term is quantified or exemplified.
- [ ] No two instructions conflict; priority is stated if tension is unavoidable.
- [ ] The ask-vs-assume rule and the important defaults are explicit.
- [ ] Out-of-scope work and forbidden shortcuts are named.
- [ ] Tool routing says when to use which tool and when not to.
- [ ] Irreversible, external, or shared actions require confirmation.
- [ ] The output contract matches the consumer.
- [ ] Uncertainty has an allowed expression ("not found", "I don't know", confidence).
- [ ] At least one example exists for format-sensitive or judgment-heavy work.
- [ ] Every sentence carries information; removing it would lose something.
- [ ] No secrets, credentials, stale dates, or environment facts that belong in runtime context.

## Step 5 — Deliver

Return, in this order:

1. **Assumptions** — only the ones that affect the result.
2. **The prompt** — one fenced block, ready to paste, no commentary inside.
3. **Why it works** — 2–4 bullets mapping choices to the seven slots. Skip if the user only wants the prompt.
4. **Test cases** — 3–5 short inputs, including one edge case, with expected behavior.
5. **Optional variant** — a shorter or model-specific version only when it adds value.

When the user is iterating, ask for the actual output and the exact failure. Change one variable at a time. Do not rewrite the whole prompt to fix a local problem.

### Improving an existing prompt

When the user supplies a prompt to fix:

1. **Infer intent first.** State what the original is trying to achieve. Do not silently change the goal.
2. **Diagnose with the table below.** Name the specific failure, not "it's vague".
3. **Preserve what works.** Keep wording, constraints, and examples that are doing a job.
4. **Rewrite the minimum.** Fix the diagnosed cause; do not add a full scaffold to a prompt that needed one clause.
5. **Show the change.** Return a before/after diff or a short "what changed and why" list, plus the full revised prompt.
6. **Add a test.** Give one input that should now behave differently and say what correct looks like.

## Game prompts

Game work needs one extra translation before the seven slots: adjectives into
checks. "Fun", "immersive", "smooth" and "AAA graphics" are not acceptance
criteria, and a prompt that uses them licenses the agent to stop at a static
screenshot.

- Name the **player-facing outcome** and the **platform/hardware**. They set
  the input scheme and every performance budget.
- Convert each quality word into evidence: a play trace, an input/telemetry
  test, landmark screenshots, or p95 frame time.
- State the **asset and licence policy** whenever visible content is produced;
  without it the agent invents primitives or ships unlicensed assets.
- Split anything larger than one mechanic into **phases with gates**, and scope
  the prompt to what one turn can verify. A full game is a plan, not a prompt.
- Require a **runnable build plus measured numbers** and a PASS/FAIL/NOT TESTED
  report. "Polished" is not a finding.

Full guidance, an adjective-to-check table, asset blocks and copyable briefs for
prototypes, vertical slices, mechanics, levels, art passes, settings screens and
performance work: [Game prompts](references/game-prompts.md). When the
`game-builder` skill is available, point the prompt at its phase plan and
references instead of restating their contents.

## Model adjustments

These are starting points, not laws. Verify against current vendor docs before relying on model-specific behavior.

| Model family | Lean on | Avoid |
|---|---|---|
| **Claude** | Explicit role and goal, XML or Markdown sections, diverse examples, positive phrasing, stated reasons | ALL-CAPS rule piles; assuming it will infer scope; forcing visible chain-of-thought when extended thinking is available |
| **GPT-5 / reasoning models** | Clear goal, scope, stop criteria, tool boundaries, explicit assumptions, concise output specs | "Be maximally thorough" scaffolding; prescribed internal reasoning scripts; contradictory rules |
| **Gemini** | Consistent delimiters, long context first and task last, explicit output format, a simple "think hard" nudge for difficult reasoning | Mixing XML and Markdown; assuming it will add detail unless asked |
| **Smaller / faster models** | Numbered steps, one instruction per line, examples, tight scope, short context | Implicit judgment calls, many competing goals, long documents |

## Diagnose a failing prompt

| Symptom | Likely cause | First fix |
|---|---|---|
| Generic output | Objective is an adjective; no audience or ambition | Name the outcome, audience, and scope |
| Wrong format | Format described but not shown | Add one example or prefill the opening |
| Misses requirements | Requirements buried in prose | Convert to numbered acceptance criteria |
| Overreach / scope creep | Only inclusions stated | Add exclusions and "nothing more" |
| Stops early | No persistence or done condition | Add "continue until…" and a check command |
| Loops forever | No retry cap or escalation rule | Cap attempts; define what to do at the cap |
| Wrong tool or ignores tools | No routing rules | Intent → tool table; "when not to use" |
| Contradictory behavior | Conflicting rules | Rank priorities; delete the losing rule |
| Fabrication | No uncertainty path | Allow "not found"; require citations or evidence |
| Too verbose | "Concise" is unquantified | Give a line/word budget and an example |
| Too cautious | No permission to act under uncertainty | State which assumptions may be made and noted |
| Game feels lifeless | Acceptance is adjectives; no loop or feedback spec | Define the 60-second loop, feedback timing, and one meaningful choice |
| Looks like a tech demo | Art direction and asset policy missing; primitives accepted | Add material/lighting gates and an asset source policy |
| Controls feel wrong | No numeric feel targets or telemetry | Specify speeds, camera rig, input latency, coyote/buffer, fps-independence tests |
| Game scope explodes | No phase gates or out-of-scope list | One phase per prompt; add a stop condition and exclusions |

## Anti-patterns

- **Vague praise adjectives** — "high quality", "robust", "comprehensive", "world-class".
- **Instruction piles** — stacking every technique without a failure it fixes.
- **Emphasis inflation** — MUST/NEVER/CRITICAL on ordinary preferences; salience flattens.
- **Persona theater** — a biography instead of a role and an outcome.
- **Kitchen-sink context** — dumping everything instead of pointing to sources.
- **"Never ask" absolutism** — expensive assumptions sold as autonomy.
- **Hidden contradictions** — speed plus exhaustive coverage; minimal diff plus full refactor.
- **Unverifiable acceptance** — "make it production-ready".
- **Mixed delimiters** — XML and Markdown used for the same hierarchy.
- **Stale facts** — model names, dates, paths, and versions baked into reusable prompts.
- **"Fun" as a requirement** — unmeasurable; replace it with the loop, feedback timing, and evidence.
- **"AAA" as an adjective** — name the materials, lighting, motion, and UI craft you mean.
- **A full game in one prompt** — multiplayer + open world + story cannot share one gate.
- **No asset policy** — guarantees placeholder geometry or licence debt.

## References

- [Core techniques](references/core-techniques.md) — official guidance from Anthropic, OpenAI, Google, and Microsoft, with examples and sources.
- [Agent prompt design](references/agent-prompts.md) — tool policy, planning, autonomy, verification, and long-horizon work.
- [Pattern library](references/patterns.md) — copyable patterns for common jobs.
- [Evaluation](references/evaluation.md) — test prompts, diagnose failures, and prevent regressions.
- [Game prompts](references/game-prompts.md) — playable-build briefs, adjective-to-check translation, assets and licences, phase gates, and playtest prompts.
- [System-prompt insights](references/system-prompt-insights.md) — what production agent prompts do, what to borrow, and what to leave out.
- [Prompt template](assets/prompt-template.md)
- [Worked examples](assets/examples.md)
