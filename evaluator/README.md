# Rubrics evaluator — LLM-as-judge

Automated QA proxy for the Rubrics bot. For each closed case + bot RCA
output it runs a Gemini judge against the same L1/L2/L3 hierarchy the bot
was supposed to follow, and emits a Pass / Fail verdict per (case,
framework). Aggregates to the May-14-locked accuracy metric (`Correct ÷
Total Audited`, primary driver weighted).

This is the **inner loop** for prompt iteration — it lets us A/B prompt
changes in minutes instead of waiting days for Zaidul's QA team to
manually review columns N+ of the I/O sheet. It is **not** a replacement
for Zaidul's review; the outer loop still goes to him for sign-off.

## Layout

```
evaluator/
├── prompts/judge.md     # single generic judge prompt, framework-parameterised
├── gold/cases.csv       # ~30 Zaidul-validated rows (calibration anchor)
├── config.py            # sheet IDs, model name, paths
├── schemas.py           # JudgeVerdict pydantic model
├── hierarchy.py         # parses HIERARCHY_CONFIG from notebook cell 4
├── judge.py             # one async Gemini call per (case, framework)
├── runner.py            # CLI: load rows → fan out judges → write CSV
├── aggregate.py         # CSV → accuracy metric + per-framework breakdown
└── runs/                # timestamped CSVs (gitignored)
```

## Auth

The runner reads its OAuth token from `GOOGLE_OAUTH_TOKEN`. Never hardcode
the token in this directory.

```
export GOOGLE_OAUTH_TOKEN="$(gcloud auth print-access-token)"
```

The longer-term fix (service-account) tracks the same migration as the
notebook's cell 7.

## CLI

```
# Smoke — 5 cases, one framework (from-scratch judge on the live I/O sheet)
python3 -m evaluator.runner --sample 5 --framework Quality

# Real iteration loop — 200 most-recent cases, all frameworks
python3 -m evaluator.runner --sample 200
python3 -m evaluator.aggregate evaluator/runs/<latest>.csv

# Calibration — run only the Zaidul-validated rows in gold/cases.csv
python3 -m evaluator.runner --gold
python3 -m evaluator.aggregate evaluator/runs/<latest>.csv
```

### Label-match mode (`--match-labels`) — preferred

Scores bot predictions against the QA dump's **human ground-truth
labels** (`docs/connect-2026-05-29.md`) instead of judging from scratch.
It joins the dump's `RCA_Analysis_Output` (bot) to the per-framework
label tabs (human) on case number, then asks the matcher whether the
bot's L1/L2/L3 agrees with the human's. Supports the four driver
frameworks **TTR / Reopen / Escalation / DSAT** (Quality/Workflow are a
scored-match follow-on).

```
export GOOGLE_OAUTH_TOKEN="$(gcloud auth print-access-token)"
python3 -m evaluator.runner --match-labels --framework TTR --sample 200
python3 -m evaluator.aggregate evaluator/runs/<latest>.csv
```

Pieces: `gold_dump.py` (loader + real-case-id filter), `prompts/judge_match.md`
(matcher prompt), `judge.match_case_framework`. Sampling is a seeded
random draw, not the tail — the dump's tail is placeholder test rows.

## Inner-loop workflow

```
edit prompts/<framework>/*.md
    │
    ▼
python3 scripts/inject_prompts.py
    │
    ▼
run notebook (locally on the sample, or push to prod scheduler for full)
    │
    ▼
python3 -m evaluator.runner --sample 200
python3 -m evaluator.aggregate evaluator/runs/<latest>.csv
    │
    ▼
gate: did per-framework accuracy improve?
    │
    ▼  yes — take the delta to Zaidul as the outer loop
    ▼  no — revert the .md edit
```

## Notes / known limits

- The judge's own accuracy is the floor on what we can measure. First
  gold-calibration run sets the baseline; aim for ≥ 70% judge↔human
  agreement before trusting per-framework deltas.
- `runs/*.csv` is gitignored — diffing happens via the sidecar
  `summary.json` for each run.
- The hierarchy is parsed live from `notebook/content.ipynb` cell 4. If
  HIERARCHY_CONFIG ever moves to a standalone JSON, repoint
  `hierarchy.load_hierarchy`.

## Where this fits

`docs/execution-plan.md` Phase 2 (stand up evaluator) and Phase 5 (the
prompt-iteration loop). Use this README for the CLI; use the execution
plan for sequencing across the project.
