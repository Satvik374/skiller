# Prompt Template

Copy the form that matches the task. Replace every `<...>`; delete sections that carry no information.

## Full form — tool-using or multi-step agent

```text
# Role and objective
You are acting as <role>. <Outcome: one observable result>. This matters because <reason or downstream use>.

# Context
- <What is known, decided, or already tried>
- <Where the relevant material is: files, links, attachments>
- <Constraints that are not discoverable from the material>
- Unknown: <what is genuinely unavailable>

# Success criteria
Done when:
1. <Observable criterion>
2. <Observable criterion>
Evidence: <test command / rubric / diff / screenshot> must show <expected result>.

# Method
1. <Understand: what to read or inspect first>
2. <Plan: what to produce before acting, if anything>
3. <Execute: the order of work>
4. <Verify: the check to run and what passing looks like>

Tool policy:
- Use <tool> for <intent>; do not use it for <competing intent>.
- <Independent reads may run in parallel; dependent steps must be sequential.>
- Stop exploring when <sufficient-context condition>.

If a fix fails, retry at most <N> times, then <escalate / report the blocker>.

# Boundaries
- In scope: <...>
- Out of scope: <...> Do not add <features, refactors, dependencies> that were not requested.
- If details are missing, infer <1–2> reasonable assumptions from <source of truth>, note them, and continue. Ask only when <blocking condition>.
- Before <irreversible / external / shared action>, ask for confirmation. Examples: <...>.

# Output
Return <format>. Keep it <length/word/line budget>. Include <citations/evidence/commands>. If something cannot be determined, say "not found" and explain what is missing rather than guessing.

# Examples
<Only when format-sensitive or judgment-heavy.>
Good: <short example>
Bad: <short example> — because <reason>
```

## Short form — one-shot task

```text
<Role and outcome in one sentence.>

Context: <what the model cannot infer>
Input: <the material, or where to find it>
Done when: <observable criterion or rubric>
Output: <format, length, evidence, uncertainty policy>
```

## Snippet library

### Ask vs assume

```text
If details are missing, infer 1–2 reasonable assumptions from <conventions / the provided context>, state them briefly, and proceed. Ask only when the ambiguity changes the outcome or the action is hard to reverse.
```

```text
Before implementing, ask about any choice that would materially change the result: <examples>. Do not ask about cosmetic details; choose a sensible default and note it.
```

### Risk and confirmation

```text
Take local, reversible actions freely. Before an action that is destructive, hard to reverse, visible to others, or affects shared systems, ask for confirmation. Examples: deleting files, force-pushing, publishing, sending messages, changing infrastructure. Never use a destructive shortcut to get past an obstacle.
```

### Tool routing

```text
Choose tools by intent, not habit:
- <intent A> → <tool A>
- <intent B> → <tool B>; do not use <tool A> for this.
Read before editing. Run independent reads in parallel; run writes and dependent calls sequentially. Stop gathering context once <condition>.
```

### Verification gate

```text
Before declaring the task complete, run <check>. Report the exact command and its output. If it fails, fix the cause and rerun, up to <N> attempts. Do not claim success without evidence.
```

### Output contract

```text
Output exactly:
<section 1>
<section 2>

Rules: <length>, <tone>, <citation style>, <what not to include>. Do not add a preamble or summary unless asked.
```

### Uncertainty

```text
If the evidence is insufficient, say so explicitly and name what is missing. Do not fill gaps with plausible guesses. Distinguish "verified", "inferred", and "unknown".
```

### Scope guard

```text
Do what was asked; nothing more. Do not refactor, rename, reformat, or add dependencies outside the stated scope. If you notice an unrelated problem, report it separately instead of fixing it.
```

### Long-horizon state

```text
This task may outlast one context window. Keep <progress file / task list> current with completed work, open questions, and the next step. Before context is compacted, save decisions and unfinished work. Continue until the success criteria are met; do not stop early because the task is long.
```

## Filling notes

- **Order matters.** Stable context first; the specific request last in a long prompt.
- **One delimiter system.** Use Markdown headings or XML tags consistently.
- **Quantify.** Replace "concise", "fast", "thorough", and "robust" with numbers, examples, or checks.
- **No duplicates.** If two sections say the same thing, delete one.
- **No empty sections.** A heading with no content invites the model to invent content.
- **No secrets.** Reference where credentials live; never paste them.
