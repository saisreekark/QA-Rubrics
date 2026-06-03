# Prompt-engineering strategy

The one job for the next 5 weeks: **lift accuracy from ~50% to ~80%** by the
3rd week of June, with full launch in July. The architecture is frozen.

## Why we're at 50%

Hypotheses based on a first read of `prompts/**/*.md`:

1. **Prompts are long but unconstrained.** Most are 3–6 KB of prose. The
   model can interpret them many ways, especially around ambiguous L2/L3
   pairs ("Did not seek confirmation" vs "Did not answer all questions"
   overlap heavily).
2. **No few-shot examples.** Every prompt is zero-shot. Gemini 2.5 Pro
   handles examples well; we have hundreds of QA-labelled historical cases
   (Q3/Q4 2025) to mine.
3. **Output schema is enforced only by prose**, not by `response_schema`.
   Cell 10 wraps the agent output in `json.loads(...)` inside a try/except;
   parsing failures are silently scored 0.
4. **Multi-agent handoff** is sequential, but the second/third agent only
   sees text — there's no structured handoff envelope, so context drifts.
5. **Validation is fully manual.** Each iteration waits on Zaidul's QA team
   to review outputs; the feedback loop is days-long.

## Levers — in priority order

### 1. Tighten the output schema (highest ROI, lowest effort)

Today: agents emit free-form JSON. Sometimes nested, sometimes flat.

Move to `vertexai.generative_models.GenerationConfig(response_schema=...)`
with an explicit pydantic-style schema:

```python
{
  "drivers": [
    {"L1": "<enum>", "L2": "<enum>", "L3": "<enum>", "evidence": "<str>"}
  ]
}
```

Cuts parsing failures to zero, forces the model into the known L1/L2/L3
enum set, and surfaces JSON-format failures as retryable errors instead of
silent zeros.

### 2. Add few-shot examples per driver

The I/O sheet's columns N+ contain QA-validated labels (Zaidul's team
corrected the bot's output). For each L3 with ≥10 historical examples,
pick 2–3 representative cases and inject them into the relevant agent's
prompt as `### EXAMPLES`. Especially helpful for the L3 pairs that overlap
in prose.

### 3. Live working sessions with Zaidul (May 14 reality)

The May 14 Connect locked validation as **synchronous live sessions with
Zaidul**, not async comment threads on prompt docs. Daily standup cadence
for the next week.

The **`evaluator/` LLM-as-judge module is the inner loop**, Zaidul's
sessions are the outer loop. Use the evaluator to converge per-framework
locally (`python3 -m evaluator.runner --sample 200 && python3 -m
evaluator.aggregate evaluator/runs/<latest>.csv`), then take a small
focused diff to Zaidul for human sign-off — rather than the full 18-prompt
diff. The evaluator does not replace him; it stops us burning his time on
hypotheses that are easy to disprove locally.

### 4. Test on small batches

Zaidul's guidance: always validate on 100–200 cases before running the full
~3000-case sweep. If a prompt change costs 90 min on the full batch, 3
iterations is a half-day lost. The notebook already supports this via the
commented-out `input_df = input_df.iloc[:700].copy()` line in cell 10 — wire
this into a `DEV_MODE` flag.

The accuracy metric is now defined (case-level, primary driver weighted,
secondary as tiebreaker), so the regression target on the small batch is
**"% of cases where the primary driver matches the gold label"**.

### 5. Per-framework error profiling

Before tuning all 6 frameworks, profile error rates per framework on the
historical set. Likely one or two frameworks dominate the error budget —
fix those first.

## Iteration loop (target)

```
1. Identify a target framework (highest error contribution) — read it
   off `evaluator/aggregate.py` per-framework breakdown.
2. Edit prompts/<framework>/agentN.md.
3. python3 scripts/inject_prompts.py
4. Run notebook locally on a 100–200 case sample.
5. python3 -m evaluator.runner --sample 200 --framework <fw>
   python3 -m evaluator.aggregate evaluator/runs/<latest>.csv
6. If +5pp or more, take diff + delta to Zaidul; on his sign-off push
   (./scripts/push_notebook.sh) and re-run on the full set.
7. If regressed, revert the .md file and try the next hypothesis.
```

## Don't do these (yet)

- **Don't migrate to a different model.** Gemini 2.5 Pro is set; switching
  costs token economics renegotiation.
- **Don't add new L3s** without Zaidul. He owns the rubric — the May 14
  diff (Product Gap, Quarter freeze / planning, KSI rule, plus the
  yet-to-enumerate additions across TTR/Reopen/DSAT/Escalation) is the
  only sanctioned change set right now.
- **Don't bust Vertex Context Caching** unintentionally. The cached
  content is the static SOP / rule corpus on the `use_cache: True` agents
  — preserves token / latency budget.

Quality's 5-agent layout (previously flagged as "don't touch") is now
**fair game for consolidation** — Zaidul accepted this on May 14 provided
the output still enumerates each metric.
