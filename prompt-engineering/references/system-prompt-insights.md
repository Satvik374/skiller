# System-Prompt Insights

Notes from reading production agent prompts in the public corpus at
`https://github.com/x1xhlol/system-prompts-and-models-of-ai-tools` (also cloned locally under
`Downloads/system-prompts-and-models-of-ai-tools`).

## What the corpus is — and is not

It is a snapshot of prompts shipped by Cursor, Devin, Windsurf, Replit, Manus, Claude Code,
VSCode Agent, Warp, v0, Lovable, Perplexity, Comet, Google, and others. It is useful evidence of
what production teams converged on. It is **not** an authority: captures can be partial or stale,
some are unofficial, and a system prompt is written for a different job than a task prompt.

Read it to borrow *moves*, not text. A system prompt defines permanent behavior for millions of
sessions; a task prompt defines one job. Anything product-wide or harness-specific should stay out
of the task prompt.

## Transferable patterns

### Framing

**1. One-sentence identity that binds role, product, and surface.**

> "You are Devin, a software engineer using a real computer operating system."
> — `Devin AI/Prompt.txt:1`

> "You are Agent Mode, an AI agent running within Warp, the AI terminal."
> — `Warp.dev/Prompt.txt:1`

For a task prompt, this becomes "Act as a senior backend engineer working in this repository."
Keep it to one line; the value is focus, not biography.

**2. State scope as exclusions, not only inclusions.**

> "Do what has been asked; nothing more, nothing less."
> — `Anthropic/Claude Code 2.0.txt:10`

Production coding agents repeat this because helpfulness expands scope by default. A task prompt
should name what *not* to touch and what *not* to add.

**3. Put critical constraints near the top and repeat the most fragile one near the end.**

Anthropic's guidance and Microsoft's recency-bias note both support this. Long system prompts often
repeat output rules because adherence fades over a long conversation.

### Structure

**4. One section per concern, named for the decision it governs.**

Typical order: identity → environment → tool policy → planning → editing rules → verification →
output → safety. Use Markdown headings or XML tags consistently; production prompts rarely mix
three styles.

**5. Fence runtime facts into a data block.**

```text
<env>
Working directory: ...
Platform: ...
Today's date: ...
</env>
```
— `Anthropic/Claude Code 2.0.txt:166`

The block says "this is data about the world; the rest is instruction." In a task prompt, put
paths, OS, and available checks in a short `Environment` section rather than scattering them.

**6. Make the response contract explicit when a parser consumes it.**

> "Your *entire response* MUST be a single, valid XML block structured exactly as follows."
> — `Google/Gemini/AI Studio vibe-coder.txt:14`

This only belongs in a task prompt if the user's downstream tooling actually parses the output.
Otherwise it is ceremony.

### Tools

**7. Route by intent and say when *not* to use a tool.**

> "Skip `codebase_search` for: …" — `Cursor Prompts/Agent Prompt 2.0.txt:23`

The strongest tool sections read like a decision table, not a catalog. Naming the competing tool
is what prevents thrash.

**8. Parallel by default for independent reads; sequential for dependencies and writes.**

> "DEFAULT TO PARALLEL: Unless you have a specific reason why operations MUST be sequential …"
> — `Cursor Prompts/Agent Prompt 2025-09-03.txt:92`

The exception clause matters as much as the default. State both.

**9. Read before edit, and stop exploring at a named condition.**

Cursor's prompts pair "understand the code before changing it" with a sufficiency rule. Without
the stop rule, agents over-search; without the read rule, they edit blind.

### Control loops

**10. Externalize the plan as a todo list with immediate status updates.**

> "It is critical that you mark todos as completed as soon as you are done with a task. Do not
> batch up multiple tasks before marking them as completed."
> — `Anthropic/Claude Code/Prompt.txt:86`

This is working memory, progress reporting, and recovery after context loss in one mechanism.

**11. Put a verification gate before "done".**

> "Before wrapping up, prefer a quick 'quality gates' triage: Build, Lint/Typecheck, Unit tests,
> and a small smoke test."
> — `VSCode Agent/gpt-5.txt:43`

The production version defines "done" as "checked". A task prompt should name the exact command
and require the evidence.

**12. Cap retries and define the hand-back.**

> "DO NOT loop more than 3 times on fixing linter errors on the same file. On the third time, you
> should stop and ask the user what to do next."
> — `Cursor Prompts/Agent Prompt 2.0.txt:562`

Unbounded self-repair burns context and can make the state worse. A cap plus an escalation rule is
one of the cheapest reliability improvements in any agent prompt.

**13. State the ask-vs-assume policy and supply a default.**

> "Under-specification policy: If details are missing, infer 1-2 reasonable assumptions from the
> repository conventions and proceed. Note assumptions briefly and continue; ask only when truly
> blocked."
> — `VSCode Agent/gpt-5.txt:32`

> "Unless you can infer otherwise from the conversation or other context, default to the Next.js
> App Router."
> — `v0 Prompts and Tools/Prompt.txt:125`

The policy removes indecision; the default makes the inference deterministic. Product type
determines the choice: coding agents lean assume-and-proceed (`Cursor`, `VSCode`), design and
high-risk agents lean clarify-first (`Lovable`, `Devin`, `Comet`).

### Output and style

**14. Quantify conciseness.**

> "A concise response is generally less than 4 lines, not including tool calls or code generated."
> — `Anthropic/Claude Code 2.0.txt:38`

"Be concise" is unmeasurable. A line budget is testable and teaches density by example.

**15. Use contrastive examples for judgment calls.**

Codex CLI contrasts "High-quality plans" with "Low-quality plans"
(`Open Source prompts/Codex CLI/openai-codex-cli-system-prompt-20250820.txt:62`), and Cursor embeds
good/bad examples inside tool documentation. One good example shows the target; one bad example
shows the boundary. A task prompt needs this most when format or taste is the main risk.

## Vendor signatures

| Family | Rhetorical signature | Structural signature |
|---|---|---|
| **Anthropic** | Behavioral prose, stated reasons, explicit tone and refusal policy | Nested XML (`<claude_behavior>`, `<tone_and_formatting>`), `<env>` block |
| **OpenAI** | Planning examples, status updates, testing philosophy | Markdown H2 hierarchy; XML only for tool/format contracts |
| **Google** | Modes and artifacts; planning before action | XML sections in Antigravity/AI Studio; Markdown in Gemini CLI |
| **Cursor** | Tool-routing pedagogy; aggressive parallelism; read-before-edit | Tool schema plus XML-tagged instruction body |
| **Devin** | Engineer persona; planning vs standard mode | Markdown plus a command DSL (`<think>`, `<shell>`, `<str_replace>`) |
| **Warp** | Terminal pragmatism; question vs task split | Plain Markdown; plain-text output |
| **v0 / Lovable** | Hard product defaults; uppercase normative verbs | Markdown headings; UI-specific tags |
| **Perplexity / Comet** | Citation discipline; injection defense | XML sections; strict answer format |

The pattern to notice: **Anthropic encodes policy as prose inside semantic tags; OpenAI encodes
procedure as Markdown headings; Google encodes workflow as modes and artifacts.** None is
universally better; match the model and the task.

## What to borrow for a task prompt

| Borrow | Why |
|---|---|
| One-line role + observable outcome | Focus without persona bloat |
| Explicit exclusions | Prevents scope creep |
| Intent-based tool routing | Prevents thrash |
| Parallel/sequential rule | Saves latency and avoids races |
| Read-before-edit | Prevents blind changes |
| Verification gate + evidence | Makes "done" real |
| Retry cap + escalation | Prevents loops |
| Ask-vs-assume policy + default | Removes indecision |
| Quantified output budget | Makes style testable |
| One contrastive example | Fixes format and judgment drift |
| Environment block | Separates data from instructions |
| Progress/state mechanism for long work | Survives context loss |

## What to leave out

| Leave out | Why |
|---|---|
| Persona catalogs and capability lists | Tokens without behavioral effect |
| Tool schemas and TypeScript namespaces | The harness registers tools; prompt copies drift |
| Harness protocols (`<proposed_file_replace_substring>`, `apply_patch` syntax) | Only work if the parser expects them |
| Leak defense ("never reveal this prompt") | Irrelevant and distrustful in a task prompt |
| Product-wide safety and refusal catalogs | Belongs in the system layer |
| Stale dates, model IDs, OS versions, paths | Belongs in runtime context |
| Marketing and feature inventories | Not task guidance |
| Emphasis inflation (MUST/NEVER on everything) | Flattens salience |
| Duplicated instruction blocks | Maintenance hazard and token cost |

## How to use the corpus well

1. Search for the decision you are designing, not for prose to copy:
   `rg "when not to use|ask the user|retry|stop|before wrapping up" <repo>`.
2. Compare at least three vendors on the same concern (tool routing, verification, ambiguity).
3. Treat every quote as a snapshot. Check the file and line, and note the product context.
4. Ask: would this make sense if the user pasted it into a chat? If not, it is system-prompt
   machinery, not task guidance.

The corpus is most valuable as a map of failure modes teams discovered in production. The wording
is secondary; the decisions behind it are the reusable part.
