# Core Techniques

A synthesis of current guidance from Anthropic, OpenAI, Google, and Microsoft. Use it as the reference layer behind `SKILL.md`; the workflow there is the default, this file explains why.

## 1. Clarity beats cleverness

Every vendor says some version of the same thing: state the task plainly and specifically, then remove anything that could be interpreted two ways.

- Anthropic: "Think of Claude as a brilliant but new employee who lacks context on your norms and workflows." Its key test: show the prompt to a colleague with minimal context; if they would be confused, the model will be too.
- Microsoft: "Be specific. Leave as little to interpretation as possible. Restrict the operational space."
- Google: "Be precise and direct"; define ambiguous terms and parameters.
- OpenAI: match the prompt to the model. Reasoning models can take a high-level goal; faster GPT models need more explicit task logic.

**Practical rule:** every sentence should either add information, remove an ambiguity, or specify a check. If it does none of those, cut it.

## 2. Add context and explain the why

Context is what the model cannot discover. Explaining the reason behind an instruction lets the model generalize correctly when a new case appears.

| Less effective | More effective |
|---|---|
| `NEVER use ellipses` | `Your response will be read aloud by a text-to-speech engine, so never use ellipses; the engine cannot pronounce them.` |
| `Create an analytics dashboard` | `Create an analytics dashboard. Include as many relevant features and interactions as possible; go beyond the basics to a fully featured implementation.` |
| `Fix the login bug` | `Users report login fails after the session times out. Look at token refresh in src/auth/, write a failing test that reproduces it, then fix it.` |

The last pair is from Anthropic's Claude Code guidance and shows the general pattern: name the file, the symptom, and what "fixed" looks like.

**Do not over-supply context.** Anthropic's context-engineering guidance treats context as a finite resource: aim for "the smallest possible set of high-signal tokens." Long context degrades recall ("context rot") and dilutes attention. Point to sources; do not paste everything.

## 3. Structure with one consistent delimiter system

Structure helps when a prompt mixes instructions, data, examples, and variable inputs. It hurts when it becomes decoration.

- **Claude:** XML-style tags are explicitly supported and useful for nesting (`<instructions>`, `<context>`, `<example>`). Use consistent, descriptive names.
- **OpenAI:** recommends sections for Identity, Instructions, Examples, and Context, using Markdown headers and lists, with XML tags for content boundaries and metadata.
- **Google:** recommends either XML-style tags or Markdown headings — consistently, not mixed. Its template is:

```xml
<role>...</role>
<instructions>...</instructions>
<constraints>...</constraints>
<output_format>...</output_format>

<context>...</context>
<task>...</task>
<final_instruction>...</final_instruction>
```

- **Microsoft:** recommends clear syntax and separators (`---`, uppercase section labels) and notes that models are trained on plenty of Markdown and XML, so either is a safe choice.

**Rules of thumb:**

1. One concern per section, named for the decision it governs.
2. Nest only when there is a real hierarchy (documents inside `<documents>`).
3. Do not use three delimiter styles in one prompt.
4. Keep section names stable across a prompt family; they become reference points.

## 4. Role prompting is optional and should be small

A single sentence — "You are a senior backend engineer working in this repository" — can focus tone and expertise. A multi-paragraph biography usually adds tokens without adding behavior.

Use a role when it changes a real decision: expertise level, audience, standards, or stance. Do not use it to smuggle in instructions that belong in the objective or constraints.

## 5. Examples are the strongest format control

Few-shot examples outperform adjectives for format, tone, and boundary cases.

- Anthropic recommends 3–5 relevant, diverse, structured examples; wrap them in `<example>` / `<examples>`.
- OpenAI recommends several diverse input/output pairs and identical formatting.
- Google recommends "specific and varied examples", identical tags and whitespace, and warns that too many can overfit.
- Microsoft shows that a few examples can teach a label category the model was not explicitly given.

**Use examples when:** the output shape matters, the judgment boundary is subtle, or the model keeps drifting. **Do not use them when:** a clear schema or one sentence already specifies the result.

For judgment calls, a contrastive pair is stronger than either example alone:

```text
Good: "The migration is blocked by two failing tests: auth_refresh and session_expiry."
Bad:  "There are some issues with the tests." — vague; gives no actionable target.
```

## 6. Reasoning: ask for the outcome, not a script

The right amount of reasoning depends on the model.

- **Reasoning models** (GPT-5-class, Gemini 2.5/3+, Claude with extended thinking) already plan internally. Give them a clear goal, scope, and success criteria; do not prescribe "think step by step" unless you need visible reasoning for auditability. OpenAI explicitly warns that generic "be maximally thorough" scaffolding can cause redundant work.
- **Non-reasoning or smaller models** benefit from decomposition: number the steps, ask for a plan before the answer, or request a short rationale.
- **When visible reasoning matters** (regulated work, debugging, teaching), separate it from the answer: "Reason in `<thinking>` tags, then give the final answer in `<answer>` tags."
- **Do not demand hidden chain-of-thought** from a model or provider that exposes only a reasoning summary; ask for a brief rationale instead.

A useful middle ground for any model: "Before answering, identify the assumptions and the evidence you need. Then answer." This improves quality without forcing a verbose transcript.

## 7. Control output deliberately

| Goal | Technique |
|---|---|
| Exact structure | Provide a schema or a filled template; for parsers, require valid JSON/XML only |
| Consistent tone | One short role sentence plus one example |
| Shorter output | A concrete budget ("under 120 words", "five bullets") and an example of the desired density |
| No preamble | "Skip the preamble; begin with the answer." Prefill the opening where the API allows it |
| Markdown vs prose | State the medium and the reason; match your own prompt's style to the desired output |
| Citations | Require inline citations next to each claim, not a bibliography at the end |
| Uncertainty | Define the exact phrase: "If the answer is not in the sources, respond `not found`." |

Anthropic's formatting guidance favors positive requests over prohibitions: "Your response should be composed of smoothly flowing prose paragraphs" works better than "Do not use Markdown." Microsoft makes the same point about giving the model an "out."

## 8. Order and recency

- For long documents, Google recommends supplying all context first and placing the specific request at the end, optionally bridged with "Based on the information above…".
- Microsoft notes recency bias: the end of the prompt can carry more weight, so repeating a critical instruction at the end is worth testing.
- Anthropic recommends putting stable, reusable content first for prompt caching, with changing input later.

**Practical rule:** stable context → examples → the specific request → the output contract. Repeat only the one instruction that is most likely to be forgotten.

## 9. Ground, cite, and permit uncertainty

Hallucination is usually a prompt-design problem before it is a model problem.

- Provide the source material, or require retrieval before answering.
- Require evidence next to each claim. Microsoft observes that inline citations are stronger than end-of-document citations because the model must anticipate the citation while writing the claim.
- Explicitly allow "not found" or "insufficient evidence". This is one of the highest-leverage lines in any factual prompt.
- For extraction, require `null` rather than a guess, and specify the schema.
- Separate "verified", "inferred", and "unknown" when the reader will act on the answer.

## 10. Iterate empirically

Google: "Prompt engineering is iterative." Anthropic's overview starts with success criteria and a way to test before touching the prompt. Microsoft warns that a prompt that works in one scenario may not generalize.

A workable loop:

1. Write the smallest prompt that could work.
2. Run it on 5–10 representative inputs, including edge cases.
3. Classify each failure: missing context, ambiguous instruction, wrong format, conflicting rule, or model limitation.
4. Change one thing.
5. Re-run the same cases. Keep a regression set.

Do not add technique after technique preemptively. Add a technique because a specific failure demands it.

## 11. Chain when one prompt is doing too much

If a task has cleanly separable stages, a chain is more reliable than one giant prompt:

- summarize → critique the summary → revise
- extract facts → verify each fact → write
- plan → implement → review against the plan

Anthropic's agent guidance distinguishes workflows (fixed code paths) from agents (the model directs its own process), and recommends starting with the simplest option. A chain is a workflow; use it when predictability matters more than flexibility.

## 12. Vendor emphasis at a glance

| Vendor | Strongest emphasis | Signature advice |
|---|---|---|
| **Anthropic** | Clarity, examples, XML structure, stated reasons, agentic verification | "Brilliant but new employee"; explicit success criteria; give the agent a check it can run |
| **OpenAI** | Matching prompt style to model type, roles/authority, sections, coding and agentic prompts | Reasoning models get goals; GPT models get explicit logic; define stop criteria and tool boundaries |
| **Google** | Empirical iteration, context ordering, output format, agentic planning | Context first, task last; use one delimiter system; "think hard" for difficult reasoning |
| **Microsoft** | Prompt components, grounding, clear syntax, few-shot, output structure | Be specific; give the model an out; inline citations; repeat critical instructions at the end |

## Sources

Accessed 2026-11-19.

- Anthropic — Prompting best practices: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices
- Anthropic — Prompt engineering overview: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/overview
- Anthropic — Best practices for prompt engineering (blog): https://claude.com/blog/best-practices-for-prompt-engineering
- Anthropic — Building effective agents: https://www.anthropic.com/engineering/building-effective-agents
- Anthropic — Effective context engineering for AI agents: https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- Anthropic — Claude Code best practices: https://code.claude.com/docs/en/best-practices
- OpenAI — Prompt engineering guide: https://developers.openai.com/api/docs/guides/prompt-engineering
- OpenAI — GPT-5 prompting guide: https://developers.openai.com/cookbook/examples/gpt-5/gpt-5_prompting_guide
- Google — Gemini prompting strategies: https://aistudio.google.com/docs/prompting-strategies
- Microsoft — Prompt engineering techniques: https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/prompt-engineering
