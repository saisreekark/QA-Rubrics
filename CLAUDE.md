# GTM QA Rubrics — project context for Claude Code

## What this is

An automated QA auditor for GTM support cases. A scheduled Gemini job reads
closed cases from a Google Sheet, runs **6 audit frameworks** (Reopen, TTR,
Escalation, DSAT, Quality, Workflow) through a multi-agent prompt pipeline,
and writes per-case Root Cause Analysis (RCA) results back to the sheet. A
downstream MIS dashboard visualises the output.

It replaces today's manual ~15% sampling with **100% case coverage**.

## Problem statement

Manual QA today samples ~15 % of closed support cases against a six-framework
rubric, leaving most cases unaudited. Feedback latency to product / process
owners is days, coverage is uneven, and signal back to the business is weak.
The Rubrics auto-auditor runs the same rubric on **100 % of closed cases
daily** through a multi-agent Gemini pipeline. The pipeline is **in
production** but its classification accuracy sits at ~50 %, well below the
bar Zaidul's QA team needs to trust the output.

## Objectives

In rough priority order — the first one gates the June demo, everything
else sequences around it.

1. **Lift accuracy toward ~80 % across all 6 frameworks.** For the **4 driver
   frameworks** (TTR/Reopen/Escalation/DSAT) the metric is case-level
   `Correct ÷ Total Audited`, primary driver weighted over secondary, pass
   threshold `score ≥ 90` (**Stage 1** = 3.1-pro + fix-v2 = OVERALL **22.4%**, up
   from the ~12.9% prod anchor). **Quality + Workflow are now also in-scope
   accuracy targets** (Sai 2026-06-07), but on a **detection P/R/F1** metric
   (per-case accuracy is meaningless at ~94% "no error"); Stage 1 = Quality F1
   ~39% / Workflow F1 ~12%. There is **no single all-6 accuracy** — the two metric
   families don't combine (see the **STAGE 1 combined scorecard** at the top of
   `docs/execution-plan.md`, the one tracker that keeps the 4-driver wins + Q/W
   together). **The Q/W over-firing prompt fix is DONE + measured (2026-06-07,
   §9):** it cuts over-emission (Workflow drivers/case 1.53→1.13, re-open 17→10%)
   and lifts Quality L3-classification (+7pp) but **does NOT move headline F1**.
   **The two F1 bottlenecks were RE-DIAGNOSED 2026-06-08 (spike, §10) — they are NOT
   the Zaidul rubric questions they looked like:** the **Workflow hygiene** lever is
   **field-emptiness hallucination** (the bot fabricates empty `Root_Cause`; actual
   empty-rate 1%, bot claims empty on ~87%) → fix is **deterministic code-grounding**
   (task 4.7), not a prompt — **STAGE 2: BUILT + MEASURED 2026-06-08, staged-not-pushed:
   Workflow detection F1 17.0→23.9% (+6.9pp), recall held 100%, 27 hallucination-FPs
   killed** (`evaluator/hygiene_ground.py` + notebook cell-9 `ground_workflow_hygiene`,
   gated `GROUND_WORKFLOW_HYGIENE`; gold confirms empty `Next_Steps` is the operative
   defect → literal rule 9; residual precision gap = the quantified Zaidul confirm); the
   **Quality structure-error** lever is **under-emission
   of an existing rule** (a prompt clarity rewrite raised emission 0→11%) → mostly
   local + a one-line Zaidul semantic confirm. Both spike edits were **reverted**
   (Stage 1 untouched). See `docs/session-2026-06-05-6driver.md` §10;
   `docs/execution-plan.md` Phase 5.Q/W + task 4.7; `docs/prompts-strategy.md`
   lever #6; task #13.
2. **Encode the confirmed framework updates** in `prompts/` +
   `HIERARCHY_CONFIG` — new combined L1 **"Product/Tools Gap"** (L2s:
   Product Limitation, Product Bugs) and new L3 **"Quarter Freeze / YoY
   Planning & Implementation"** under Process Gap, both across
   TTR / Reopen / DSAT / Escalation. **ENCODED (Stage 1) + wording APPROVED by Zaidul
   2026-06-08 + spell-checked clean — question CLOSED.**
3. **Implement the KSI auto-close rule** so known-issue cases with future
   resolution dates stop polluting TTR / SLA metrics. **Zaidul 2026-06-08: a case
   resolved/aged `< 7 days` is NULL for TTR** ⇒ **DONE + staged 2026-06-08: cell-9 trigger
   `Case_Aging_in_Days > 5` → `>= 7`.** **Full qualifier — DEFINITION CLOSED 2026-06-09
   (doc-derived; Zaidul delegated to the SOP/T&C docs):** a case is NULL for TTR when it carries
   a **known-systemic marker** (`KSI -`/`KSI:` tag in `Root_Cause_Description`, seen in prod data,
   or a `Bug_Id` whose fix is "under development/evaluation" — SOP "Outcome 3") **and** the fix
   is pending a **future/uncommitted resolution**. Implementation = a gated deterministic cell-9
   pre-LLM filter (task-4.7 pattern) — **BUILT 2026-06-09, staged-not-pushed**
   (`evaluator/ksi_ground.py` + cell-9 `is_ksi_excluded`, `EXCLUDE_KSI_FROM_TTR=True`, skips the
   TTR run for a KSI case). **Measured LIVE 2026-06-09 (`evaluator/ksi_measure.py`): fires on
   116/2,592 (4.5%) of TTR-audited cases (KSI-tag 101 / Bug_Id+pending 15); gold-validated —
   46/46 excluded TTR-gold cases are external-cause (35 Product/Tool + 8 Process + 3 User Gap,
   ZERO People Gap).** Fresh Mar–Apr TTR label-match: **17.6%→16.4% (Δ −1.2pp)** — the filter is
   **metric-VALIDITY (SLA/breach hygiene), NOT an RCA-accuracy lever** (the bot coincidentally
   matches the external driver on 39% of KSI cases, so the headline dips slightly). Open nuance for
   Zaidul: the gold still *audits* KSI cases with external drivers rather than NULLing them. See
   `docs/session-2026-06-09-ksi-kb.md`, [[reference_kb_source_docs]], `docs/open-questions.md`
   (RESOLVED 2026-06-09 #2).
4. ~~Stand up version control for `prompts/`/`docs/`~~ — **dropped**
   (2026-05-29): Sai is the sole contributor, so git hosting isn't
   needed.
5. **Replace the hardcoded `ya29.…` token** in notebook cell 7 with
   Sai's own short-lived token; plan service-account auth as the
   durable fix.
6. **Scope the Tricks → BigQuery migration** in parallel with accuracy
   work (Pooja sending SQL Miner + Colab paths).
7. **Be standby-ready** for the conceptual client presentation (~Tuesday
   2026-05-19).

Out of scope: dashboarding (parked), model swaps, scheduler refactors.

## Next steps

Shortest path to a demo-ready bot. Sequence first; dates land once the
sequence is agreed.

1. Schedule the **live working session with Zaidul** to lock the prompt
   diff (new L1/L3s, KSI rule, Quality consolidation shape).
2. **Read** `docs/connect-2026-05-14.md`, the Voice-of-Seller RCA
   Frameworks sheet, and the Feasibility doc end-to-end before the
   session.
3. **Rotate the OAuth token** in notebook cell 7 (avoid an in-flight
   scheduler failure).
4. **Run the LLM-as-judge evaluator** (`evaluator/`) on a 100–200 case
   sample to profile per-framework accuracy — find which framework
   dominates the error budget before tuning anything. The evaluator is
   the inner loop for prompt iteration; Zaidul stays the outer loop. See
   `evaluator/README.md`.
5. After the live session: **encode the framework diff** in
   `prompts/<framework>/agentN.md`, run `inject_prompts.py`, run the
   sample through the evaluator, measure delta, iterate.
6. ~~Decide a git venue~~ — **dropped** (solo contributor, no git needed).
7. ~~Run the label-match baseline~~ — **done 2026-05-29.** Case-level
   accuracy **12.93%** (95/735) vs the human QA dump; per framework TTR
   16.0% / DSAT 13.2% / Reopen 13.1% / Escalation 8.6%. Error budget is
   **systemic** — 88% of misses are full L1 mismatches, ~16% cite the
   un-encoded May-14 drivers. This strict full-primary-driver number is
   the anchor for all future deltas (it is *not* comparable to the prior
   "~50%"). See `docs/execution-plan.md` 2.5; memory
   `project_baseline_labelmatch.md`.
8. ~~Build the regen harness~~ — **DONE 2026-06-04** (`evaluator/regen.py`
   + N-run/CI `evaluator/ab_measure.py`). Re-runs the real pipeline on
   QA-2026 gold cases with the local prompts; `runner.py --gold-source
   regen` scores it. Also: driver diff **encoded + tightened locally**
   (Phase 4.1/4.2, not pushed); aggregator non-determinism fixed (agent-4
   temp 0.2→0 cut churn 84%→23%); Gemini **3.1-pro-preview** wired via the
   global endpoint (`--model`). See `docs/execution-plan.md` 2.7/2.9/2.10.
9. ~~Run the N-run A/B + calibrate the matcher~~ — **DONE 2026-06-04 (PM).**
   The "quota block" was mis-diagnosed (quotas are per-minute / self-heal); the
   nans were the **bot + matcher self-saturating the same regional bucket** +
   a **global-endpoint auth bug**. Both fixed: `ab_measure --force-global`
   (bot → global pool, matcher stays regional) + ADC auto-refresh creds in
   `_install_global_genai`. **First directional A/B (N=3×30, global bot):**
   prompt effect ≈0 (OLD-2.5 11.8% == NEW-2.5 11.8% on TTR); **model effect
   +21.5pp (NEW-3.1-pro 33.3%)** — the big lever. **Matcher calibrated for
   Reopen** (~90% judge↔human, PASS). See `docs/session-2026-06-04.md` §7–§11.
10. ~~Aggregator fix v2 + model lever~~ — **DONE 2026-06-05** (fix-v2 built +
    measured; staged, NOT pushed). fix-v2 = a **Root-Cause Attribution Gate** in
    `HIERARCHY_AGENT_4_PROMPT` (user/external causes win Primary over agent-blame
    unless clear independent agent failure). **N=5×120 A/B on 3.1-pro, clean CI
    separation:** OVERALL **15.4%→22.4%** (+7.0pp); Reopen 8.5→15.9, Escalation
    7.4→21.1, DSAT 0→11.4, TTR 24.6→29.0 (no regression). Harness now defaults the
    **bot to 3.1-pro** (matcher stays regional 2.5-pro), reports OVERALL pooled
    accuracy, and supports `--resume-file` (Cloud Shell idle-safe; `$HOME`
    persists). Prod notebook switched to 3.1-pro via an **additive gated** global
    path (rollback = set `agent_model` back to 2.5; `google-genai` added to pip) +
    genai KB caching w/ inline fallback — **validated locally, awaiting Sai's
    review before push** (accuracy still far below 80). A/B absolutes are `--no-cache`
    (KB 403 locally) so the **delta** is the signal; anchor stays ~12.9%. See
    `docs/session-2026-06-05-fixv2-ab.md`.
11. ~~Build the 6-driver (Quality + Workflow) scoring~~ — **DONE 2026-06-05.**
    Evaluator now scores all 6 frameworks. New `evaluator/multilabel_score.py`
    (deterministic detection scorer + `phrase_match` LLM-judge hook), gold loaders
    + joins in `gold_dump.py`, `runner --match-labels --framework Quality|Workflow`
    (P/R/F1, **separate** from driver accuracy → `runs/multilabel_*`), `regen`
    widened (`ALL_FRAMEWORKS`), `gold_audit --multilabel`, `calibrate_multilabel.py`.
    **Measured both bot sources.** Frozen-live (prod 2.5-pro): Quality F1 26.0% /
    L3-class 22.9%; Workflow F1 12.8% / error-type 60.6%. **Best (regen 3.1-pro):**
    Quality **F1 34.8%** / L3-class **60.0%** (fixes dead Accuracy dim 0/24→10/24);
    Workflow **F1 ~11%** / error-type **85.7%**. Model lifts classification/recall
    but NOT precision (Workflow still flags 346/350 — over-firing is a **prompt**
    problem). **Calibration DONE (hand-read):** deterministic scorer, **no LLM
    judge** (Workflow 19/19, Quality 13/13 after a scorer-side `client→user` synonym
    fold); driver path regression-checked clean. **What the bot emits:** rubber-
    stamps default drivers (Workflow: 85% get the same 2-driver pair; Quality:
    People Gap + 2 default L3s, can't even say the dominant gold error). Nothing
    pushed. See `docs/session-2026-06-05-6driver.md` (§3c bot behavior, §6b metric
    guide, §6c open decisions).
12. **METRIC NOTE:** there is **no single "all-6 accuracy"** — drivers = case-level
    Correct÷Audited (goal 80%, Stage-1 ~22.4%); Q/W = detection P/R/F1 (Stage-1 F1
    ~39%/~12%, **far from 90**). High Q/W numbers seen (recall ~100%, error-type
    85.7%, calib 19/19) are NOT bot accuracy. (Scope call resolved — A1 = **improve**
    Q/W; see #13.)
13. ~~Improve Q/W (over-firing prompt fix)~~ — **DRAFTED + MEASURED 2026-06-07,
    staged not pushed** (= **Stage 1** for Q/W; see `docs/execution-plan.md` top
    scorecard + `docs/session-2026-06-05-6driver.md` §9). Did the two no-Zaidul
    levers: **5.Q/W.1** (inline `Reopen_Counter>0` gate on `workflow/agent1` rule 6
    + metadata-gate instruction across all 6 sub-agents) and **5.Q/W.3** (reframe
    "None"; Workflow strong, **Quality softened** after the strong prior cratered
    Quality recall −19pp). **Clean same-cases OLD-vs-NEW on 3.1-pro, held-out
    month:** Workflow over-emission **1.53→1.13 drivers/case**, re-open **17→10%**
    (the "89%" was a 2.5-pro artefact — 3.1 self-corrects); Quality April F1 OLD
    40.8 → strong 35.6 → **softened (staged) 39.1** (~neutral) with **L3-class
    65→72% (+7)**. **Key result:** the no-Zaidul levers cut over-emission + improve
    sub-error classification but **do NOT clear the +5pp F1 gate**. **The two real F1
    levers were RE-DIAGNOSED 2026-06-08 (spike, §10) — both reverted, Stage 1
    untouched:** **5.Q/W.2** (Workflow hygiene) is **field-emptiness HALLUCINATION**,
    NOT a too-broad rule — narrowing the prompt left it firing 87% by fabricating empty
    `Root_Cause` (actual empty-rate 1%); fix = **deterministic code-grounding (task
    4.7)** — **DONE + measured 2026-06-08 (Stage 2): Workflow F1 17.0→23.9% (+6.9pp),
    staged-not-pushed.** **5.Q/W.4** (Quality structure-error)
    is **UNDER-EMISSION of an existing rule**, NOT a vocab gap — a prompt clarity rewrite
    raised emission **0→11%** + L3-class **+3.8**, but firings are FPs on held-out, so
    F1 was flat (40.9→37.5); the F1 gain needs a **one-line Zaidul semantic confirm**.
    **Zaidul answers (2026-06-08):** `Next_Steps`-empty **IS** always a defect (→ task-4.7
    grounding validated as-is; measured precision is gold-limited), and the framework-diff
    **wording is APPROVED + spell-checked clean (CLOSED).** **All remaining Zaidul questions —
    CLOSED 2026-06-09 (he delegated to the SOP/T&C docs; [[reference_kb_source_docs]]):** Quality
    rule-3 = doc-grounded definition adopted, but the 5.Q/W.4 rewrite is **parked** (held-out
    firings were FPs, no F1 gain → Quality stays Stage-2 F1 39.1%); KSI full qualifier = **defined**
    (see objective #3, build in Phase 4); gold-semantics = **adopt coded safe defaults** (ratified
    by delegation). **Pending build/push:** push the **Stage-1+2 bundle** (3.1-pro + fix-v2 +
    driver diff + Q/W discipline + task-4.7 hygiene grounding) after Sai's review; report all-6
    Stage-1/2 to Pooja. See `docs/open-questions.md` (RESOLVED vs STILL OPEN).
14. ~~Push the **drivers** in Phase 2~~ — **INVESTIGATED 2026-06-08, NULL result, edits
    reverted** (`docs/session-2026-06-08-driver-usergap.md`). Profiled the driver error budget:
    the dominant miss is **User Gap under-prediction** — gold's plurality/majority L1 in 3 of 4
    frameworks (Reopen 62%, Escalation 68%, TTR 41%), but the bot emits it only ~5–27%,
    defaulting to Process/People Gap (structural: 2 of 3 driver sub-agents are blame-oriented;
    `reopen/agent1` had no rule for *"Additional or different Query"* = 49% of Reopen gold).
    Tried a targeted lever (`reopen/agent1` New-Query rule + `agent4` user-over-external gate
    clause): User-Gap **L1 recall 27→33%** but **matcher accuracy did NOT move (17.9→16.0%,
    single-run noise)** — the model resists reclassifying (emits "Additional or different Query"
    ~13/150 vs gold ~49%). **Both edits reverted** (Stage 1/2 untouched). Re-confirms "prompts
    move drivers ≈0; the model was the lever." **ZAIDUL CONFIRMED 2026-06-08: a
    reopen-with-new-query IS "User Gap (New Query)"** (gold right, model wrong) → we **built +
    measured** the deterministic re-attribution (agent1 surfacing rule + a hard cell-9 override
    promoting a surfaced New-Query finding to Primary, bypassing agent4). **`ab_measure` 3×120
    Reopen: OLD 20.0% ±3.6 → NEW 22.5% ±6.2 = Δ +2.5pp, CIs OVERLAP → fails the +5pp gate →
    REVERTED.** Override beat the prompt-only null (agent4 demotion is *part* of the blocker) but
    is capped by the **surfacing wall** (agent1 emits New Query ~13/150). **Drivers stay at
    Stage-1 22.4%.** See [[project_driver_usergap_ceiling]]; `docs/session-2026-06-08-driver-usergap.md`.
15. ~~Phase-3: build the **dedicated New-Query detector**~~ — **BUILT 2026-06-08, NULL, reverted
    (`docs/session-2026-06-08-newquery-detector.md`).** Built exactly the prescribed lever (focused
    YES/NO classifier `REOPEN_NEWQUERY_DETECTOR_PROMPT` → cell-9 deterministic force-emit, bypass
    agent4, gated). **Measured detector-vs-gold (n=60 held-out April, 3.1-pro): YES rate 5%, gold
    New-Query 47%, recall 7%** — the dedicated classifier inherits the **exact same ~9% reluctance**;
    it does NOT break the wall. **ROOT CAUSE: the surfacing wall is a DATA-INSTRUMENTATION ceiling,
    NOT prompt/model** — the input has (1) **no `<<< SYSTEM LOG: CASE CLOSED >>>` marker** the prompts
    rely on, (2) **no reopen-trigger message** (reopen fires within seconds of close; recoverable for
    only 3/28 gold New-Query cases), (3) **no `Reopen_Reason` field**. The reviewer's "Additional or
    different Query" signal comes from a source the pipeline **doesn't ingest** ⇒ **~47% of Reopen gold
    is structurally unreachable** at the agent layer (explains every prior null at once). **Drivers stay
    22.4%.** The **real Phase-3 lever is UPSTREAM**: ingest the reopen reason / first post-reopen seller
    message into `Cases for Summary` (data-load / Tricks→BigQuery, Vikram/Pooja), then restore the
    detector from the KT doc. **Open for Zaidul/data:** which field do reviewers read to label
    "Additional or different Query"? See [[project_driver_usergap_ceiling]].
16. **✅ Phase-3 COMPLETE 2026-06-09 — Reopen prompt lift (P3-A v2): powered WIN, no regression,
    kept + staged** (`docs/phase3-experiments.md`; Stage-3 all-6 scorecard in `docs/stage-tracker.md`).
    After the detector null, a *reachable* prompt lever cleared the gate: (1) `reopen/agent1`
    PRIORITY-4 **"Additional or different Query" catch-all** (valid substantive reopen ⇒ default
    **User Gap → New Query**, encoding the reviewer convention without the un-ingested reopen text)
    + (2) `hierarchy/agent4` clause promoting that New-Query finding over the downstream external
    step (fixes the tie-breaker that ranked New Query last — why the Phase-2 agent1 rule alone moved
    ≈0). **Powered Reopen A/B (full pool, 3.1-pro, temp 0): April OLD 22.8% ± 1.3 → NEW 29.0% ± 3.0
    (+6.2pp); Mar–Apr OLD 19.5% ± 2.5 → NEW 24.6% ± 1.4 (+5.1pp) — CIs separated both → PASS.**
    **Regression found + fixed:** the *generic* agent4 clause (prefer any user-side) regressed
    **Escalation −3.2pp** (Mar–Apr powered, CIs separate) → **scoped the clause to the New-Query
    finding only** (= P3-A **v2**); re-measured Escalation **15.8→15.7% (neutral, fixed)**, Reopen
    win held. TTR neutral (+1.1, overlap); DSAT inconclusive (n≈51). **Methodology lesson:**
    April-only multi-framework runs were underpowered and masked **both** the win (n=51 OLD outlier)
    **and** the regression (n=13) — Mar–Apr per-framework powered runs were required. Q/W untouched
    (driver-only change). **Re-applied + injected (staged-not-pushed).** Restorable prompt blocks +
    all numbers in `docs/phase3-experiments.md`.

## Current goal (as of 2026-05-15 — post May 14 Connect, see `docs/connect-2026-05-14.md`)

- **Push prompt accuracy → 80%** before client demo. **Anchor baseline is the
  QA-2026 gold set**, windowed to **March–April 2026** — the updated taxonomy is
  only in use from **March** (Jan/Feb are old-taxonomy; Quarter Freeze = 0 before
  March confirms the cutover — see `docs/gold-audit-2026-06-05.md` and memory
  `project_taxonomy_cutover_march`). 1,778 clean usable gold cases (April is the
  latest labelled month). Re-baseline on this window (frozen production preds,
  `rebaseline_marapr_2026-06-05…csv`): **driver-level ~12.9%** — TTR 18.65 /
  Reopen 6.94 / Escalation 7.46 / DSAT 6.00 (1,415 audited). **Reopen is the
  floor** (Product/Tools Gap is genuinely rare in gold — 2 cases total — so that
  L1 won't move the needle). (Supersedes Feb/Mar `12.99%` and old-dump `12.93%`.)
- **✅ PHASE 2 COMPLETE (2026-06-08, LOCAL-ONLY by choice — NOT pushed).** The staged
  bundle = **Stage 1** (3.1-pro + fix-v2 + driver framework diff + Q/W emit-discipline)
  **+ Stage 2** (task-4.7 Workflow hygiene code-grounding **+** TTR `>=7` gate). Built,
  injected, verified in `notebook/content.ipynb`; **deliberately not deployed.**
  **Numbers — Drivers OVERALL 12.9% → 22.4%** (TTR 29.0 / Reopen 15.9 / Escalation 21.1 /
  DSAT 11.4; **no Phase-2 driver gain** — the User-Gap lever was measured +2.5pp/CIs-overlap
  and reverted); **Workflow detection F1 12.8 → 23.9% (+6.9pp via task 4.7)**; **Quality F1
  26→39%.** Two metric families, **no single all-6 number.** Running stage-by-stage log
  (Stage 0→1→2, changes + numbers): **`docs/stage-tracker.md`** (Phase-2 closeout block at
  top of Stage 2); combined scorecard also at top of `docs/execution-plan.md`. Deploy-when-ready
  note (Colab Enterprise UI; the scheduler's single-file-asset notebook repo has no public
  write API) in the stage-tracker. Prod untouched.
- **✅ REVIEWER-GRADE QA SEND (2026-06-10, biggest session — staged, NOT pushed).** The QA
  team grades a **~500-case sample** for **"is the RCA reasonable"**, not strict gold-match —
  so the target metric pivoted to the **from-scratch reasonableness judge** (`prompts/judge.md`
  / `judge_case_framework`) scored **gated** (`evaluator/gated_reason.py` mirrors the cell-9
  gates). This is a **THIRD metric family** (not driver case-acc, not Q/W F1; never averaged).
  Built a **prod-faithful local run**: Rishita's prod creds (from the notebook via Dataform
  `:readFile`) read all 4 real KB docs (197K, `evaluator/kb_snapshot_real.txt`);
  `evaluator/run_prod_kb.py` runs the tuned 3.1-pro pipeline with the real KB in **genai
  context caches** → 500 prod-faithful cases/27min. **Model lever is exhausted** (3.1-pro is
  the strongest published model). **Judge-fairness + Workflow-justification fix → Workflow
  23.6→71.9%.** **Two tuning passes; v2 KEPT** (v1→v2: **TTR 60→75.3, Quality 63→70.7, Esc
  84→94.7, Workflow 74→72.3, Reopen 32→32; overall 63.8→68.7%, ex-Reopen 72.9%, 4/6 frameworks
  ≥70%**); **v3's "regression" was 3.1-pro RUN-NOISE (v2↔v3 churn 15–30%, both ways), reverted;
  v4 = a DETERMINISTIC noise-proof "Unmapped" re-resolution (`evaluator/reresolve.py` + notebook
  `HierarchyResolver` patch — ~52 drivers the bot got right but the exact-match resolver dropped to
  Unmapped now resolve; noise-isolated proof TTR 6→Correct/0 lost, Workflow 13→Correct/2 lost):
  overall 68.7→71.7%, ex-Reopen 75.7%, TTR 84 / Workflow 79 / Reopen 38 — v4 is FINAL.** **Reopen
  (38% subsample / **46.7% full-pop**) is the documented DATA ceiling** (reopen-reason not ingested → upstream/Tricks→BigQuery fix). Deliverables:
  `evaluator/runs/QA_send_prodKB_500_v4.xlsx` (dev `RCA_Analysis_Output_1` format) +
  `QA_send_prompts_asrun.md` (as-run prompts → QA-review doc `1ALZRqSB`). v2/v3 prompts
  injected; prod untouched. Full record: `docs/session-2026-06-09-reasonableness-pivot.md`,
  `docs/stage-tracker.md` Stage 5; memory `project_reasonableness_prodkb`,
  `reference_rishita_creds_realkb`.
- **✅ DELIVERED TO QA (2026-06-10):** (1) the **500-case sample** pushed to a fresh Google Sheet
  in dev format — `https://docs.google.com/spreadsheets/d/1aCU9s-haBosPY4lhfbyWsFV2Nb8hxF3a1drLAhlME6c`
  (tabs `RCA_Analysis_Output_1` + `Cases for Summary`, QA cols blank; **not yet shared** — Sai
  shares with Zaidul's team); (2) the **18 as-run prompts** written into the QA-review doc
  `Prompts for all RCAs` (`https://docs.google.com/document/d/1ALZRqSB2tqTAYZs_HlfoqN-fDOxyXsA6GDbwPOUWpXc`,
  old version in Docs history). **Full-population judge (all 500, not the 200 subsample): Reopen
  46.7% / DSAT 63.6%** (both understated by the subsample). **v5** (deterministic Reopen/DSAT
  external→trigger demote, `evaluator/reopen_demote.py`) **BACKFIRED (Reopen NET −9) → reverted;
  v4 stands.** Reopen (~47%) / DSAT (~64%) are at their reachable ceilings.
- **Demo**: **2026-06-15** (firm deadline).
- **Full release**: July 2026.
- **Accuracy is measured per-case** (`Correct ÷ Total Audited`), with the
  *primary* driver weighted more than secondaries.
- **Pass threshold**: **score ≥ 90 = Pass**, **< 90 = Fail**.
- **Dashboarding is parked** — sole priority is prompt accuracy.
- **Tricks → BigQuery migration** moved from "parked" to **actively scoping**
  (Pooja sending SQL Miner / Colab paths).
- Pipeline architecture is otherwise frozen — no scheduler swaps. (Model swap to
  Gemini **3.1-pro** is now staged locally + measured (+7pp w/ fix-v2), awaiting
  review before any prod push — see Next steps #10.)

## Where the code lives

| Surface | Location |
|---|---|
| Live notebook | Pantheon Colab → Dataform repo `1b4ad4ee-53ba-4541-9492-1dc89d100607` (us-central1, project `gtm-cloud-helpdesk`), file `content.ipynb` |
| Local mirror | `notebook/content.ipynb` |
| Prompts (18, split out) | `prompts/<framework>/agentN.md` |
| Scheduler | `rubrics-automation-run` (id `1105207098007879680`), daily 12:00 IST |
| Output bucket | `gs://analytics_genai` |
| I/O sheet | [`1Lmo5la…J94juM`](https://docs.google.com/spreadsheets/d/1Lmo5laSelj8Yp-ANjuZ_cQVnVM3W9XB6mNRt_J94juM) → input tab `Cases for Summary`, output tab `RCA_Analysis_Output_1` |

## Evaluator & regen harness — the inner loop (read this; we use it every session)

The whole accuracy effort runs through `evaluator/`. It's read-only on sheets and
**never** writes pipeline config back to the prod notebook. Two distinct paths:

- **`--match-labels` (frozen)** scores the bot predictions *already sitting in a
  sheet* against gold. Use it to baseline production; it does **not** reflect any
  local prompt edit.
- **regen (the prompt-iteration loop)** re-runs the *real* pipeline locally with the
  *current local prompts* so a prompt/driver edit becomes measurable. **regen reads
  the prompts from `notebook/content.ipynb` (cells 2,4,5,6,8,9), NOT from
  `prompts/*.md`** → you must `python3 scripts/inject_prompts.py` after editing
  prompts, before regen sees the change. Fixed `random_state=42`, so the same
  `--sample N` on the same gold pool gives the **same cases** → OLD-vs-NEW is a clean
  same-cases A/B (run OLD, inject, run NEW; held-out month filtered at *scoring* time
  via `runner --months`).

| Artifact | What it is |
|---|---|
| `evaluator/config.py` | All IDs/tabs/column maps/month windows (`QA2026_MONTHS`=Mar–Apr drivers; `QA2026_QUALITY_MONTHS`=Mar–Apr; `QA2026_WORKFLOW_MONTHS`=Mar–May). `get_oauth_token()` reads `GOOGLE_OAUTH_TOKEN`. |
| `evaluator/gold_dump.py` | Gold loaders + bot-side joins (driver + multilabel, live + regen). |
| `evaluator/regen.py` | Re-runs the pipeline locally. Bot defaults to **gemini-3.1-pro-preview** via the global endpoint (google-genai, forces `--no-cache`); `--temperature 0` pins every agent incl. the aggregator (cell-9 source patch). `REGEN_CONCURRENCY` env (≤~24–32). `--kb-snapshot <file>` inlines a real KB snapshot into the `use_cache` agents (prod-faithful absolutes without live Drive). Writes `runs/regen_<stamp>.csv`. |
| `evaluator/dump_kb_snapshot.py` | Dumps the 4 static KB docs (SOP/T&C/Plan/DND) to a snapshot file, **assembled exactly as the pipeline does**. The KB **403s for the local `saisreekark@google.com` token** (Drive ACL, not scope), so run this from a KB-capable identity (Colab Enterprise runtime SA → GCS, then `gsutil cp` down) — see `--colab-cell` and `docs/kb-local-access-2026-06-08.md`. |
| `evaluator/runner.py` | Scores. `--match-labels` (drivers, via matcher); the **multilabel detection scorer** for Quality/Workflow; and **`--judge-source regen --regen-csv <f>`** = the from-scratch **reasonableness** judge on a TUNED regen CSV (joined w/ input transcript). `--gold-source qa2026\|regen\|dump`, `--regen-csv`, `--months`. |
| `evaluator/run_prod_kb.py` | **Prod-faithful run (2026-06-10).** Tuned 3.1-pro pipeline locally with the **real KB** (Rishita's creds, `~/.rishita_creds.json`) baked into **genai context caches** (the notebook's own caching, NOT regen's inline path) + prod gates/grounding → regen-shaped CSV. 500 cases/27min. See `reference_rishita_creds_realkb`. |
| `evaluator/gated_reason.py` | Scores a reasonableness verdict CSV **gated** (mirrors the cell-9 framework gates: Reopen_Counter>0 / aging>=7 & ¬KSI / Escalated / Survey=DSAT / Q+W always) → as-deployed per-framework `Correct ÷ Audited`. Also the curation table. |
| `evaluator/export_send.py` | Exports a (gated) regen CSV into the dev **`RCA_Analysis_Output_1`** send format (40 cols, 2 header rows, QA cols blank) + a `Cases for Summary` tab → xlsx. |
| `evaluator/merge_wffix.py` | Replaces a full 6-fw regen CSV's Workflow column with the justification-fixed one (`ground_hygiene_csv` output). |
| `evaluator/reresolve.py` | **v4 deterministic fix.** Re-resolves `Unmapped` drivers (bot emitted the right concept but a near-miss string — whitespace/trailing-period/`[L2]` bracket — the exact-match resolver dropped) via a normalized+fuzzy match against the real hierarchy. Post-filter on a regen CSV; also patched into the notebook `HierarchyResolver` (durable for prod). |
| `evaluator/multilabel_score.py` | Deterministic Q/W detection scorer (`bot_error` = any "Workflow Adherence Error" L2; per-dimension P/R/F1 + L3/error-type classification on TPs). No LLM judge (calibrated 19/19, 13/13). |
| `evaluator/ab_measure.py` | N-run **driver-only** A/B with 95% CIs + OVERALL pooled accuracy (`--resume-file` for Cloud-Shell idle-safety). |
| `evaluator/gold_audit.py` | Gold coverage/defect/cutover/join audit (`--multilabel` for Q/W). |
| `evaluator/calibrate_{matcher,multilabel}.py` | Hand-read calibration dumps for the scorers. |
| `evaluator/runs/` | All run artifacts (`regen_*.csv`, `multilabel_*.{json,csv}`, `ab_*.json`, `*.log`). |

**The measurement convention** (per `feedback_evaluator_workflow`): measure a
prompt-change delta **locally on a held-out split first**, then take the *confirmed*
delta to Zaidul — never a hypothesis. **WORKING MODE (decided 2026-06-08): KB-lite /
delta-only.** Local A/B absolutes are `--no-cache` because the **4 KB docs 403 for
every identity we can drive (local `saisreekark@google.com` token AND the runnable
SAs — Drive ACL, not scope; diagnosed 2026-06-08)** — so the **delta is the signal**
and the production anchor stays the 2.5-pro frozen ~12.9%. **Do NOT quote local
absolutes as "% toward 80%."** The prod-faithful **KB snapshot** path is built + proven
but **parked** (one ACL grant away: Viewer on the 4 files to
`653428233292-compute@developer.gserviceaccount.com`, then re-run
`gs://analytics_genai/kb_dump.ipynb` → `regen --kb-snapshot`); revisit only when a true
absolute is needed — see `docs/kb-local-access-2026-06-08.md`. Full CLI examples in
**Common commands** below and `evaluator/README.md`.

## Source-of-truth docs

Authoritative external references the project depends on. Raw IDs and the
full link table live in `docs/resources.md` — this surfaces the hot ones.

| Doc | Purpose |
|---|---|
| [Voice of Seller RCA Frameworks](https://docs.google.com/spreadsheets/d/1VXtXkbY9PkX2_7RODj2kco3SYSMzYpXyOMt1CPZfZ9Q) | Authoritative L1 / L2 / L3 hierarchy — source of the May-14 additions |
| [Rubrics — RCA Feasibility](https://docs.google.com/document/d/1zLLRxoBbFIMWdMy3pB9mVOKHitqOrpEMrqYdj4d5uBc) | Read-first approach / feasibility doc |
| [Q+ summary / AI Drivers](https://docs.google.com/document/d/1l5_uW4z-t_H_KdsGPV_88xiIsBd4W_qka1lS8dA2YHs) | Driver definitions reference |
| [QA-team prompt review](https://docs.google.com/document/d/1ALZRqSB2tqTAYZs_HlfoqN-fDOxyXsA6GDbwPOUWpXc) | Where Zaidul's QA team leaves comments after testing |
| [I/O sheet (Tricks)](https://docs.google.com/spreadsheets/d/1Lmo5laSelj8Yp-ANjuZ_cQVnVM3W9XB6mNRt_J94juM) | Live input + output for the daily run |
| [QA-2026 gold case set](https://docs.google.com/spreadsheets/d/1_MvXAMTIUcHS9ne9vJHnA_l9wviNW87mcmgNYnGkXlg) | **ADOPTED gold (2026-05-29).** Manual QA labels for recent (Jan–Apr 2026) cases in the *updated* taxonomy. Driver tab `DSAT/Reopen/Escalation/TTR` split by `Stage`; window **March–April 2026** (updated taxonomy is March-onward; Jan/Feb are old-taxonomy — see `docs/gold-audit-2026-06-05.md`). Evaluator default (`--gold-source qa2026`); bot side joins from the live output tab. |
| [QA dump — human ground-truth labels](https://docs.google.com/spreadsheets/d/1tbrQxJbjRLEn6yKB7djXsPfkFMKWHICKTy-X8Y5KzRY) | Older reviewer L1/L2/L3 labels + bot predictions. **Superseded as the driver baseline** by the QA-2026 sheet above (its labels predate the taxonomy update). Reachable via `--gold-source dump`. |
| [RCA labelling sheet — TBC](https://docs.google.com/spreadsheets/d/1LZ6z_csxzkWB5IARImKyifC81zJmJmqBf_nNKkdaZx4) | Purpose TBC — ask Zaidul |
| [Additional May-14 doc — TBC](https://docs.google.com/document/d/1W4GtzgvBhnJUghE4h5S7yUmavz8Wm7UDrhE3HpwsSsg) | Purpose TBC — ask Zaidul |
| KB docs loaded by the pipeline | `SOP_Guide`, `Terms_Conditions`, `Plan_Summary`, `Do_Not_Contact_Data` — IDs in `docs/resources.md` |

## Common commands

```bash
# Pull the latest notebook from Dataform
./scripts/pull_notebook.sh

# Extract prompts from notebook → prompts/*.md (do this after every pull)
python3 scripts/extract_prompts.py

# After editing prompts/, fold them back into the notebook
python3 scripts/inject_prompts.py

# Render the L1/L2/L3 hierarchy as Mermaid trees → docs/hierarchy-viz.md
python3 scripts/render_hierarchy.py

# Push the notebook back to Dataform (live — confirms before pushing)
./scripts/push_notebook.sh

# LLM-as-judge evaluator — inner loop for prompt iteration (read-only on the sheet)
# Auth gotcha: the token must carry the `drive` scope (covers Sheets), and the
# evaluator relies on the `gtm-cloud-helpdesk` quota project (config sends the
# `x-goog-user-project` header) — a bare token with no quota project 403s on the
# sheet. A plain `gcloud auth print-access-token` from the corp account satisfies
# both (it already includes `drive`); the `--scopes` flag is ignored there.
export GOOGLE_OAUTH_TOKEN="$(gcloud auth print-access-token)"
python3 -m evaluator.runner --sample 200          # all 6 frameworks, 200 cases
python3 -m evaluator.runner --sample 100 --framework Reopen   # single framework
python3 -m evaluator.runner --gold                # only Zaidul-validated rows
python3 -m evaluator.runner --match-labels --sample 2000              # label-match vs ADOPTED QA-2026 gold (March–April 2026, default --gold-source qa2026)
python3 -m evaluator.runner --match-labels --framework Quality --framework Workflow --sample 2000  # 6-driver: Quality/Workflow detection P/R/F1 (separate metric, not driver accuracy)
python3 -m evaluator.gold_audit                                       # audit gold coverage/quality (per-month counts, label defects, new-taxonomy presence, join health)
python3 -m evaluator.gold_audit --multilabel                         # audit Quality/Workflow gold (coverage, error-class counts, join health, May re-verify)
python3 -m evaluator.calibrate_multilabel --sample 45                # hand-read calibration for the Quality/Workflow detection scorer
python3 -m evaluator.runner --match-labels --gold-source dump --sample 200   # legacy big dump
python3 -m evaluator.aggregate evaluator/runs/<latest>.csv

# Regen harness — re-run the REAL pipeline locally with current prompts so a
# prompt/driver edit is measurable (--match-labels alone scores frozen preds).
# --no-cache required locally (KB docs not readable by personal token).
# --temperature 0 pins ALL agents incl. the aggregator (else ~84% churn).
# --model routes the bot through the global endpoint (Gemini 3.x) via google-genai.
python3 -m evaluator.regen --sample 80 --framework Reopen TTR --no-cache --temperature 0
python3 -m evaluator.runner --match-labels --gold-source regen \
  --regen-csv evaluator/runs/regen_<stamp>.csv --framework Reopen
# N-run A/B with 95% CIs (the pipeline is non-deterministic — one run ≠ signal).
# BOT now defaults to gemini-3.1-pro-preview (global); matcher stays regional 2.5-pro.
# ab_measure reports per-framework mean±CI AND an OVERALL pooled accuracy + audited n.
# Concurrency ceiling (empirical 2026-06-05): 3.1-pro-preview QPM is the constraint —
#   bot REGEN_CONCURRENCY ≤~24–32, MATCH_CONCURRENCY ≤24; 429s self-heal/retry, watch n.
# CAVEAT: regional ≠ global 2.5-pro (17.8% vs 11.1%) — keep the endpoint constant across
#   an A/B (for a 2.5 baseline: --model gemini-2.5-pro --force-global on BOTH branches).
# CLOUD SHELL: VM is reclaimed on ~20-min idle (kills the job) but $HOME/checkpoints
#   persist → launch detached + resume losslessly:
MATCH_CONCURRENCY=20 REGEN_CONCURRENCY=24 setsid nohup python3 -m evaluator.ab_measure \
  --label V2 --runs 5 --sample 120 --framework TTR Reopen Escalation DSAT \
  --temperature 0 > evaluator/runs/V2.log 2>&1 & disown     # 3.1-pro bot by default
# On disconnect, relaunch with the saved checkpoint to continue from the last run:
python3 -m evaluator.ab_measure --label V2 --runs 5 --sample 120 \
  --framework TTR Reopen Escalation DSAT --temperature 0 \
  --resume-file evaluator/runs/ab_V2_<stamp>.json

# Manually trigger one run of the scheduler (testing)
gcloud colab executions create \
  --display-name=manual-test \
  --region=us-central1 \
  --project=gtm-cloud-helpdesk \
  --notebook-runtime-template=projects/653428233292/locations/us-central1/notebookRuntimeTemplates/1413241877599092736 \
  --dataform-repository-source=projects/gtm-cloud-helpdesk/locations/us-central1/repositories/1b4ad4ee-53ba-4541-9492-1dc89d100607 \
  --gcs-output-uri=gs://analytics_genai
```

## Conventions

- **Don't hand-edit `notebook/content.ipynb`** — edit `prompts/<framework>/agentN.md`,
  then run `inject_prompts.py`. The round-trip is verified byte-exact for
  prompt content.
- **Edit prompts only under `prompts/`.** Review with Zaidul happens in
  **live working sessions** (per May 14 Connect), not async comments on
  the prompt docs.
- **Auth token rotation.** The hardcoded `ya29.…` in cell 7 is being
  replaced with Sai's own short-lived token; service-account auth is the
  longer-term fix. Whatever token is in the live notebook for the
  scheduler to run, **never commit it**.
- **Test on 100–200 cases first** (Zaidul's guidance) before validating on
  the full 3,000-case batch.
- **Don't touch the schedulers** until we've confirmed who owns each — the
  data-load scheduler may live outside this project.

## Stakeholders

- **Sai Sreekar Kanaparthy** (`kanapasai@`) — primary contributor (this repo)
- **Zaidul Mukhtar** (xWF) — QA owner, framework definitions, validation
- **Pooja Talwar** (xWF) — project lead, deadline owner
- **Vikram Singh** — MIS dashboard owner, input-load scheduler
- **Elavala Srinivasa Reddy** (`elreddy@`) — last notebook contributor (2026-01-29)
- **ukirdeankush@** — current scheduler executor identity

## Where to read more

- `docs/stage-tracker.md` — **running stage-by-stage log** (Stage 0 baseline →
  Stage 1 bundle → Stage 2 Workflow-hygiene grounding): what changed each stage, the
  improvement, and the all-6 numbers. The canonical "where the gains came from" record.
- `docs/session-2026-06-08-driver-usergap.md` — **latest KT note**: Phase-2 driver
  investigation (NULL result) — error profile shows **User Gap under-prediction** is the
  driver budget (gold's majority L1 in 3/4 frameworks); a targeted prompt lever moved L1
  recall 27→33% but NOT matcher accuracy (17.9→16.0%) → reverted; drivers stay 22.4%;
  next paths = code re-attribution or a Zaidul rubric call
- `docs/session-2026-06-05-6driver.md` — KT note: 6-driver build —
  Quality + Workflow detection scorer (`multilabel_score.py`), loaders, runner
  wiring (P/R/F1), regen widening, `gold_audit --multilabel`, `calibrate_multilabel`;
  frozen-live baseline (Quality F1 26% / Workflow F1 12.8%, bot over-emits); May
  re-verify; calibration awaits hand-read
- `docs/session-2026-06-05-fixv2-ab.md` — KT note: aggregator fix-v2
  (attribution gate) + clean 5×120 A/B win (OVERALL 15.4→22.4%), harness 3.1-pro
  default + `--resume-file`, prod 3.1-pro switch staged-not-pushed, max-concurrency
  notes, Cloud Shell run management
- `docs/session-2026-06-05.md` — KT note: gold audit + March-cutover
  window fix, re-baseline ~12.9%, matcher calibration (TTR/DSAT), fix-v1 revert,
  matcher ADC auth, 3.5-flash vs 3.1-pro A/B, speed bumps
- `docs/gold-audit-2026-06-05.md` — gold-set quality audit (coverage, defects,
  taxonomy cutover, join health) + the `evaluator/gold_audit.py` output
- `docs/session-2026-06-04.md` — prior KT note: regen harness, N-run/CI
  measurement, non-determinism fix, Gemini 3.x, quota blocker
- `docs/connect-2026-05-29.md` — catch-up: QA dump adopted, label-match,
  canonical driver diff
- `docs/connect-2026-05-14.md` — May 14 Connect: decisions, framework changes
- `docs/handover.md` — Apr 29, 2026 KT call summary + original action items
- `docs/architecture.md` — full data flow and pipeline internals
- `docs/frameworks.md` — the 6 audit frameworks & L1/L2/L3 hierarchy
- `docs/hierarchy-viz.md` — Mermaid trees of all 191 L3 nodes, per framework (regenerate with `scripts/render_hierarchy.py`)
- `docs/prompts-strategy.md` — accuracy-improvement playbook
- `docs/execution-plan.md` — phase-by-phase checklist Sai owns at the keyboard (no meetings, just work)
- `evaluator/README.md` — LLM-as-judge inner-loop evaluator (CLI, layout, workflow)
- `docs/open-questions.md` — active questions grouped by owner
- `docs/resolved-questions.md` — archive of questions answered on May 14
- `docs/resources.md` — every link, ID, and stakeholder in one place

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
