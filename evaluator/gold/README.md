# Gold calibration set

> **As of 2026-05-29 the primary gold source is the QA dump sheet**
> (`1tbrQ…`), consumed via label-match (`evaluator/runner.py
> --match-labels`). It holds thousands of human-reviewer L1/L2/L3 labels
> per framework — far more than manual curation could. See
> `docs/connect-2026-05-29.md` and the evaluator README.
>
> This file (`cases.csv`) is now **optional**, for the small set of
> hand-blessed rows used to *calibrate the matcher itself* (does it agree
> with a human on borderline L3 pairs?). The verdict-curation recipe
> below is the legacy `--gold` path.

~30 Zaidul-validated rows that anchor the judge. We compare the judge's
verdicts against these labels to catch drift between prompt edits.

## How to curate

1. Open the I/O sheet `RCA_Analysis_Output_1` tab.
2. Find rows where Zaidul's QA team has filled in columns N+ (Correct /
   Incorrect / why) for one or more frameworks.
3. Pick ~5 rows per framework — bias toward rows that exercise the new
   May-14 L3s (Product Gap on Reopen, Quarter freeze / planning across
   RCAs, KSI rule).
4. Append to `cases.csv` with columns:

   ```
   case_number, framework, gold_primary_correct, gold_secondary_correct,
   gold_verdict, gold_note
   ```

   - `gold_verdict` must be one of `Correct`, `Incorrect`, `Borderline`,
     `NotApplicable` (matches the judge schema).
   - `gold_primary_correct` and `gold_secondary_correct` are booleans
     (`true` / `false`) or blank if not applicable.

## How to use

```
python3 -m evaluator.runner --gold
python3 -m evaluator.aggregate evaluator/runs/<latest>.csv
```

The aggregator prints judge↔human agreement on the overlap. Target ≥ 70%
on the first calibration; if below, the judge prompt needs work before any
prompt-iteration numbers from the evaluator are meaningful.

## When to refresh

After every live session with Zaidul where new rubric guidance lands.
Stale gold = false confidence.
