# Prompt Evaluation

A prompt that has not been tested is a guess. Evaluation is how you turn prompt engineering from taste into engineering.

## 1. Define success before writing the prompt

Anthropic's guidance starts here: a use case with clear success criteria and some way to test them. If you cannot say what a good output looks like, no amount of prompt wording will settle it.

Write down:

- **Task:** what the prompt is for.
- **Inputs:** the range of real inputs, including messy ones.
- **Pass condition:** what must be true of the output.
- **Failure cost:** what happens when it is wrong (a typo vs a wrong payment).
- **Consumer:** human, parser, or downstream agent.

## 2. Build a small eval set

Ten to twenty cases is enough to catch most prompt problems. Include:

| Case type | Purpose | Example |
|---|---|---|
| **Golden path** | Confirms the main use works | A typical bug report |
| **Edge cases** | Tests boundaries | Empty input, one item, maximum length |
| **Ambiguity** | Tests the ask-vs-assume policy | A request missing a key preference |
| **Adversarial** | Tests instruction-following under pressure | Input that says "ignore your instructions" |
| **Known past failures** | Prevents regressions | The case that broke last time |
| **Negative / out-of-scope** | Tests refusal or hand-back | A request the agent should decline |

Keep the cases fixed when comparing prompts. Changing the test set and the prompt at the same time tells you nothing.

## 3. Choose a grading method

From cheapest and most reliable to most expensive:

1. **Deterministic check** — exact match, schema validation, test pass/fail, regex, unit test. Prefer this whenever possible.
2. **Binary rubric** — a human or judge answers yes/no to specific criteria ("Does it cite a source for every claim?"). Binary criteria are more stable than 1–10 scales.
3. **Pairwise comparison** — show two outputs and ask which better satisfies the criteria. Useful for subjective quality.
4. **Human review** — the ground truth for high-stakes or nuanced work. Use it to calibrate the cheaper methods.

If using a model as a judge, give it the criteria and the evidence, not a vague "which is better." Watch for position bias: swap the order of A and B.

## 4. Run the comparison fairly

- Hold the model, temperature, tools, and context fixed.
- Change **one** prompt variable at a time.
- Run each case multiple times; model output is non-deterministic.
- Blind the grader to which prompt produced which output when possible.
- Record the exact prompt version with the results.

A useful minimum: 10 cases × 3 runs per prompt variant. More for high-variance tasks.

## 5. Metrics that matter

| Metric | Question |
|---|---|
| **Task success** | Did it meet the pass condition? |
| **Format validity** | Did the output parse or match the contract? |
| **Instruction adherence** | Did it follow the constraints it was given? |
| **Factual grounding** | Are claims supported by the provided or cited evidence? |
| **Scope discipline** | Did it avoid unrequested work? |
| **Efficiency** | Tokens, latency, and tool calls per success |
| **Failure severity** | When it fails, how bad is the failure? |

Do not optimize only for the average. A prompt that succeeds 90% of the time but fails dangerously on the other 10% is worse than one that succeeds 85% and fails safely.

## 6. Diagnose a failure before editing

Classify each failure:

| Failure class | Sign | Prompt fix |
|---|---|---|
| Missing context | The model could not know | Add context or a retrieval instruction |
| Ambiguous instruction | Reasonable but wrong interpretation | Quantify, exemplify, or define the boundary |
| Conflicting rules | It follows one rule and drops another | Rank priorities; delete the loser |
| Format drift | Content right, shape wrong | Add an example, schema, or prefill |
| Overreach | Extra work, files, or features | Add exclusions and scope discipline |
| Premature stop | Partial answer presented as complete | Add a done condition and persistence |
| Unsafe action | Acts where it should ask | Add a confirmation list and risk tiers |
| Model limitation | Fails even with a clear prompt | Change model, decompose, or add tools |

Change one thing, rerun the same cases, and compare. If the fix helps one case and hurts two, it is not a fix.

## 7. Regression testing

Prompts are code. Keep them under version control with:

- the prompt text (or a template with typed variables)
- the eval cases and expected outcomes
- the model and parameter settings
- the date and the reason for the last change

Before changing a production prompt, run the existing cases. After changing it, add the case that motivated the change. This is especially important across model upgrades, where behavior can shift without any prompt change.

## 8. Model migration checklist

When moving a prompt to a new model:

- [ ] Re-run the full eval set; do not assume portability.
- [ ] Remove scaffolding the new model no longer needs (generic "be thorough", forced step-by-step).
- [ ] Re-check instruction priority and contradictions.
- [ ] Re-test tool routing; tool-calling behavior changes between versions.
- [ ] Re-check output format; Markdown and verbosity defaults differ.
- [ ] Re-check safety and confirmation behavior.
- [ ] Keep the old prompt and results until the new one wins on the same cases.

Vendor guidance is explicit that prompts tuned for one generation can be counterproductive on the next.

## 9. Common evaluation mistakes

- **Testing on the examples you tuned on.** Hold out cases.
- **One run per case.** Variance looks like improvement.
- **Vague grader criteria.** "Better" is not a metric.
- **Changing the prompt and the test set together.** You learn nothing.
- **Optimizing average score only.** Inspect the worst failures.
- **Ignoring cost and latency.** A perfect prompt that takes ten minutes may be unusable.
- **Trusting a model judge without calibration.** Compare it to human labels on a sample.

## 10. Eval worksheet

```text
Prompt version:
Model / settings:
Date:

| # | Case | Type | Expected | Run 1 | Run 2 | Run 3 | Notes |
|---|------|------|----------|-------|-------|-------|-------|
| 1 |      |      |          |       |       |       |       |
| 2 |      |      |          |       |       |       |       |

Task success: __/__
Format valid: __/__
Scope violations: __
Dangerous failures: __
Median tokens / latency:
Decision: keep / revise / revert
Next change (one only):
```
