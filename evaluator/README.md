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
├── multilabel_score.py  # deterministic detection scorer for Quality + Workflow
├── runner.py            # CLI: load rows → fan out judges → write CSV
├── aggregate.py         # CSV → accuracy metric + per-framework breakdown
├── gold_dump.py         # gold loaders (driver + multilabel) + bot joins
├── gold_audit.py        # gold quality/coverage audit (+ --multilabel)
├── calibrate_matcher.py # hand-read calibration for the driver LLM matcher
├── calibrate_multilabel.py  # hand-read calibration for the multilabel scorer
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
frameworks **TTR / Reopen / Escalation / DSAT**. (Quality / Workflow use a
different metric — see "Multi-label frameworks" below.)

```
export GOOGLE_OAUTH_TOKEN="$(gcloud auth print-access-token)"
python3 -m evaluator.runner --match-labels --framework TTR --sample 200
python3 -m evaluator.aggregate evaluator/runs/<latest>.csv
```

Pieces: `gold_dump.py` (loader + real-case-id filter), `prompts/judge_match.md`
(matcher prompt), `judge.match_case_framework`. Sampling is a seeded
random draw, not the tail — the dump's tail is placeholder test rows.

### Multi-label frameworks (Quality + Workflow) — the "6-driver" path

Quality and Workflow don't fit the Primary/Secondary L1→L2→L3 verdict: the bot
emits a **dynamic driver list** (`driver_1..n` of L1/L2/L3, which **bypasses the
agent4 aggregator**) and the gold is graded **per dimension / per error class**.
So they use a **deterministic detection scorer** (`multilabel_score.py`), not the
LLM matcher, and report **precision / recall / F1** — kept *separate* from the
driver Correct/Incorrect accuracy (a detection metric must never be averaged into
the driver number).

- **Quality**: 5 dimensions (Accuracy / Completeness / Relevance / Communication
  Skills / Responsiveness). The gold column name == bot **L2** (dimension); the
  cell value == bot **L3** (specific error, comma-split, paren-aware). Metric =
  per-dimension **detection** P/R/F1 + **L3 classification** accuracy on the true
  positives, with a Critical-only variant. Window: **Mar–Apr 2026** (~85 cases).
- **Workflow**: one live dimension (workflow adherence; the compliance
  sub-dimension is dead and dropped). ~94% "no error" → metric = **P/R/F1 on the
  error class** + error-type classification on the TPs. Join key is `Case_ID`.
  Window: **Mar–May 2026** (~1,595 cases; May joins clean and carries the most
  errors — confirmed by `gold_audit --multilabel`). `Error Status` is NOT used as
  a label (open Q for Zaidul).

```
export GOOGLE_OAUTH_TOKEN="$(gcloud auth print-access-token)"

# Frozen-live preds (prod 2.5-pro). Use a big --sample for Workflow (rare class).
python3 -m evaluator.runner --match-labels --framework Quality --framework Workflow --sample 2000

# Audit / re-verify the gold window + join health (settles the May question)
python3 -m evaluator.gold_audit --multilabel

# Calibrate the deterministic scorer by hand (L3 / error-type match decisions)
python3 -m evaluator.calibrate_multilabel --sample 45

# Regen on 3.1-pro for apples-to-apples with the driver fix-v2 run, then score
python3 -m evaluator.regen --sample 200 --framework Quality Workflow --no-cache --temperature 0
python3 -m evaluator.runner --match-labels --gold-source regen \
  --regen-csv evaluator/runs/regen_<stamp>.csv --framework Quality --framework Workflow
```

Outputs go to `runs/multilabel_<fw>_<stamp>.{json,csv}` (aggregate + per-case).
`ab_measure` stays **driver-only** (its OVERALL pooling is a driver-accuracy
instrument); measure Quality/Workflow via the regen + runner path above.

### Measuring a prompt/driver/model change (regen + N-run CIs)

`--match-labels` scores *frozen* predictions, so a prompt edit changes
nothing it measures. `regen.py` re-runs the **real pipeline** locally with
the current notebook (prompts + `HIERARCHY_CONFIG`) on the QA-2026 gold
cases; `ab_measure.py` does that N times and reports **mean ± 95% CI**
(the pipeline is non-deterministic — one run isn't signal).

```
# one regen pass, then score it
python3 -m evaluator.regen --sample 80 --framework Reopen TTR --no-cache --temperature 0
python3 -m evaluator.runner --match-labels --gold-source regen \
  --regen-csv evaluator/runs/regen_<stamp>.csv --framework Reopen

# N-run A/B (run on NEW notebook, then pull_notebook.sh the OLD one, run again).
# --force-global puts the BOT on the global quota pool so it doesn't self-saturate
# the regional bucket the matcher uses; then raise REGEN_CONCURRENCY (env, default 2).
REGEN_CONCURRENCY=6 python3 -m evaluator.ab_measure --label NEW --runs 5 --sample 120 \
  --framework TTR Reopen --temperature 0 --force-global
```

Key flags: `--no-cache` (token can't read KB docs locally), `--temperature 0`
(pins **all** agents incl. the aggregator — see `docs/execution-plan.md` 2.7),
`--force-global` (bot → global endpoint, separate quota pool; matcher stays
regional), `--model gemini-3.1-pro-preview` (routes the **bot** via the global
endpoint; matcher stays fixed). Env `REGEN_CONCURRENCY` tunes bot concurrency.

**Operational notes (2026-06-04):** Gemini quotas are **per-minute** (self-heal)
— the old "depletion" nans were really the **bot + matcher saturating the same
regional bucket** (use `--force-global`) and a **global-endpoint auth bug** (the
static token 401s under concurrency; fixed — the global client now uses
auto-refreshing ADC creds). **Endpoint caveat:** regional ≠ global 2.5-pro (same
prompts scored 17.8% vs 11.1%) — **hold the endpoint constant across an A/B.**

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
