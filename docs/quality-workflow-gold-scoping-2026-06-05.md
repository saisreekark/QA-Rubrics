# Scoping: Quality + Workflow gold scoring (the "6-driver" extension)

**Status:** scoped 2026-06-05, **deferred** — next priority after the current
4-driver round (aggregator fix-v2 + 3.1-pro standardization + Pooja numbers +
prod model switch). Tracked as a task. This doc is the spec to execute against.

## Why

Today the evaluator scores **4 of the 6** frameworks (TTR, Reopen, Escalation,
DSAT — the "driver" frameworks). Quality and Workflow are excluded because the
matching path is built for a single Primary/Secondary L1→L2→L3 verdict, and the
gold loaders only know the driver tab. Pooja wants overall + per-framework
numbers; covering all 6 makes "overall" complete. **Note this is orthogonal to
fix-v2** — Quality/Workflow bypass the agent4 aggregator (notebook:
`if framework_name in ["Quality","Workflow"]: <dynamic drivers> else: <agent4>`),
so the attribution gate cannot move them; this is purely added coverage.

## What exists (verified 2026-06-05)

Gold sheet `1_MvXAMTIUcHS9ne9vJHnA_l9wviNW87mcmgNYnGkXlg` has **three** tabs, not
one:
- `DSAT/Reopen/Escalation/TTR` — the driver tab we already score.
- `Quality` (142 rows).
- `Workflow & Compliance` (2,683 rows).

Bot side already exists in the live output tab `RCA_Analysis_Output_1`
(`1Lmo5la…`): columns `Quality_RCA_Output` and `Workflow_RCA_Output` are
populated for ~all cases (17,676), as JSON `{"driver_1": {"L1","L2","L3","Justification"}, "driver_2": …}`.
`evaluator/config.py` already maps `out_quality`/`out_workflow`.

The I/O sheet (`1Lmo5la…`) is **bot data, not gold**: `Cases for Summary` = the
pipeline input (regen reads it); `RCA_Analysis_Output_1` = the bot's predictions
(already the bot side of the qa2026 join). It cannot serve as ground truth.

## Quality tab — schema & findings

Columns: `Case_Number, stage, accuracy-L2, completeness-L2, relevance-L-2,
communication skills L-2, responsiveness L-2, question_comment (L3),
Critical/Non-critical error, WC, LOB, issue_category__c, Month`.

- **Multi-label, dimension-graded.** Five quality dimensions are each graded
  independently — value is `no error` or a specific **L2** error string. A case
  can have errors in several dimensions at once. The `communication skills L-2`
  field can hold **comma-separated multiple** L2s (e.g.
  `"did not structure response,asked for information repeatedly or unnecessarily"`).
- **Error counts** (of 142): accuracy 33, completeness 17, relevance 19,
  **communication skills 65** (dominant), responsiveness 13.
- **Stage** = `"Stage1 RCA"`. `Critical/Non-critical error` flags severity — can
  weight critical errors.
- **Month dist:** `Mar'26 50, Jan'26 38, Apr'26 35, Feb'26 19`. Applying the
  March-onward cutover ⇒ **~85 usable rows** (Mar 50 + Apr 35). Small N — CIs
  will be wide; treat as directional.
- **Join:** 142/142 `Case_Number` present in the bot output. Clean.
- Bot `Quality_RCA_Output` example: `{"driver_1": {"L1":"People Gap",
  "L2":"Communication Skills", "L3":"Did not use language correctly …"}}` — a
  dynamic driver list with L1/L2/L3 that map onto the same dimensions.

**Metric:** multi-label detection per dimension. For each gold dimension in
error, did the bot emit a driver whose **L2 == that dimension** (detection) and
**L3 == the specific error** (classification)? Report per-dimension + case-level
hit, and **precision/recall** (the bot over-emits drivers, so precision matters).
Critical-only variant using `Critical/Non-critical error`.

## Workflow & Compliance tab — schema & findings

Columns: `qplus_review_date, Case_ID, stage, workflow adherence & compliance
audits, compliance:data integrity & legal guidelines, closed_date, WC,
task_owner, LOB, Agent Name, Question Comments, Month, issue_category,
quality_ reviewer, additional_fields, Error Status`.

- **Two dimensions, heavily imbalanced.**
  - `workflow adherence & compliance audits`: **2,519 "no error"** vs ~**164
    errors** across types — `missing vector case hygiene fields` (105),
    `incorrectly captured the case status` (29), `didn't send the correct canned
    response` (18), `incorrectly tagged the RSO(s)` (4), plus comma-combined
    multi-errors. This is the **real signal** (~6% positive class).
  - `compliance:data integrity & legal guidelines`: **2,681 "no error"** vs **2**
    errors. Effectively **dead — drop it** (no learnable signal).
- **`Error Status` semantics are unclear** — `Yes` 2031, `''` 519, `No` 133 — but
  only ~166 rows actually have a dimension error. So `Error Status="Yes"` does
  **NOT** mean "has an error" (maybe "reviewed/applicable"). **OPEN Q for
  Zaidul** before using it as a label.
- **Join key is `Case_ID`** (not `Case_Number`); 2,678/2,683 match the bot output
  — so it joins fine, just remember the rename.
- **Month dist:** `Apr'26 661, Jan'26 619, Mar'26 481, Feb'26 466, May'26 456`.
  Workflow has **May'26** rows (the driver tab stops at April). March-onward ⇒
  **~1,598** (Mar+Apr+May) IF bot preds + workflow taxonomy cutover allow May
  (confirm: does the workflow taxonomy cut over in March like the drivers? Likely
  not the same Quarter-Freeze cutover — verify before including pre/post).
- Bot `Workflow_RCA_Output` example: `{"driver_1":{"L1":"People Gap",
  "L2":"Workflow Adherence Error","L3":"Incorrectly handled the re-open
  ticket"}}`. **L1 is sometimes `"Unmapped"`** — the workflow taxonomy resolver
  has gaps; this will depress L1/L2 matching and should be investigated.

**Metric:** **error-detection** on the workflow-adherence dimension. Because ~94%
is "no error", raw accuracy is meaningless — report **precision/recall/F1 on the
error class**, plus error-type classification accuracy on the true positives.

## What to build

1. **Loaders** in `evaluator/gold_dump.py`:
   `load_quality_labels_2026(spread, months)` and
   `load_workflow_labels_2026(spread, months)`. Handle the distinct columns;
   convert `Month` (`"Mar'26"`) → window filter; normalize `"no error"`/blank;
   split comma-separated multi-L2s; for Workflow use `Case_ID` as the join key and
   drop the compliance sub-dimension.
2. **Scorer** (new path, NOT the primary/secondary judge):
   - Parse the bot JSON driver list (`driver_1..n` → list of (L1,L2,L3)).
   - **Quality:** multi-label match per dimension (L2 detection + L3 classification);
     emit per-dimension and case-level precision/recall.
   - **Workflow:** binary error detection on workflow-adherence + error-type match;
     emit precision/recall/F1 on the error class.
   - Consider a light **LLM judge** for L3 semantic equivalence (mirror
     `judge.match_case_framework`) but at dimension granularity; or start
     deterministic (string/normalized match) and add the judge only if needed.
3. **Calibrate** each new scorer against a hand-read sample (~30–45 cases), same
   bar as the 4 driver matchers (`docs/gold-audit-2026-06-05.md` precedent).
4. **Wire** into `runner.py` (`--framework Quality Workflow`) and decide whether
   `ab_measure` includes them (separate path — they're not in
   `regen.DRIVER_FRAMEWORKS`; either extend it or add a parallel scorer).
5. **Report** Quality + Workflow alongside the 4 drivers for an all-6 picture
   (keep them on their own metric — detection P/R, not the driver verdict — so
   they're not silently averaged into the driver accuracy).

## Open questions for Zaidul

- **`Error Status` (Workflow):** what does `Yes`/`No`/blank mean? It doesn't track
  the dimension-error columns.
- **May'26 inclusion + workflow cutover:** is the workflow taxonomy stable across
  Jan–May (i.e. not subject to the March driver-taxonomy cutover)? If stable, we
  can use the full Jan–May window for Workflow (much larger N).
- **Compliance sub-dimension:** confirm it's genuinely near-empty and can be
  dropped, or whether more compliance gold is coming.
- **Quality severity weighting:** should scoring weight Critical errors over
  Non-critical?
- **Bot `"Unmapped"` L1 in Workflow:** is this a known taxonomy-resolver gap to
  fix in the pipeline, or expected?

## Resources

- Gold: `1_MvXAMTIUcHS9ne9vJHnA_l9wviNW87mcmgNYnGkXlg` → tabs `Quality`,
  `Workflow & Compliance`.
- Bot side: `1Lmo5la…` → `RCA_Analysis_Output_1` cols `Quality_RCA_Output`,
  `Workflow_RCA_Output`.
- Existing driver path to mirror: `evaluator/gold_dump.py`
  (`load_labels_2026`, `join_bot_and_labels_2026`), `evaluator/judge.py`
  (`match_case_framework`), `evaluator/config.py` (`QA2026_*`, `COL_MAPPING`).
