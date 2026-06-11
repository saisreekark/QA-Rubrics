# Execution plan — Rubrics, June demo path

Pure-execution checklist. Meetings, presentations, and stakeholder
coordination live elsewhere (see `docs/connect-2026-05-14.md` and
`CLAUDE.md` → Stakeholders). This doc is the work *Sai owns at the
keyboard*.

Sequence: top to bottom, except where noted as "parallel track".
Tick items as they ship.

Legend: `[ ]` pending · `[x]` done · `[~]` in progress · `[!]` blocked

## ⭐⭐ STAGE 1 — combined all-6 scorecard (2026-06-07)

**"Stage 1" = the first accuracy bundle, staged locally (NOT pushed), across all
6 frameworks.** Components: (a) Gemini **3.1-pro** model swap; (b) agent-4
**fix-v2** Root-Cause Attribution Gate; (c) the **driver framework diff** (Quarter
Freeze / Product-Tools Gap); (d) **Q/W emit-discipline** (re-open metadata gate +
reframe "None", Quality softened). One tracker so the 4-driver wins are not
forgotten alongside the Q/W work.

> ⚠️ **TWO METRIC FAMILIES — there is NO single all-6 number.** Drivers =
> case-level `Correct ÷ Audited` (goal **80%**). Quality/Workflow = detection
> **P/R/F1** on the error class (because ~94% of Workflow is "no error"). They
> cannot be averaged into one figure.

**Drivers — case-level accuracy** (from the 5×120 fix-v2 A/B, `V2_31`; anchor =
2.5-pro frozen prod):

| Framework | Prod anchor (2.5) | **Stage 1** (3.1+fix-v2) | Δ vs anchor |
|---|---|---|---|
| TTR | 18.7% | **29.0%** | +10.3 |
| Reopen | 6.9% | **15.9%** | +9.0 |
| Escalation | 7.5% | **21.1%** | +13.6 |
| DSAT | 6.0% | **11.4%** | +5.4 |
| **OVERALL (pooled)** | **~12.9%** | **22.4%** | **+9.5** |

(Model-controlled, the fix-v2 component alone = **15.4%→22.4%, +7.0pp** vs the
3.1-pro-OLD control. Goal is still 80% — Stage 1 closes ~⅓ of the gap.)

**Quality / Workflow — detection** (Stage-1 Q/W spike, 2026-06-07, held-out month,
clean OLD-vs-NEW on 3.1-pro — see `docs/session-2026-06-05-6driver.md` §9):

| Framework | Metric | Baseline | **Stage 1** | Note |
|---|---|---|---|---|
| Quality | detection F1 (Apr) | 40.8% | **39.1%** | ~neutral; **L3-class 65→72% (+7)**; structure-error **under-emission** = 5.Q/W.4 (Stage 2, still Zaidul-gated) |
| Workflow | detection F1 (May) | 17.0% | **23.9%** | **STAGE 2 / task 4.7 DONE**: hygiene code-grounding, +6.9pp (P 9.3→13.6, R 100), 27 hallucination-FPs killed — see stage-tracker |

**Read:** Stage 1's measured wins are concentrated in the **4 drivers (+9.5pp
pooled)**. The Q/W prompt levers cut over-emission and improve sub-error
classification but **do not move headline F1** — both Q/W F1 bottlenecks become
**Stage 2**. **Re-scoped 2026-06-08** (spike, `session-2026-06-05-6driver.md` §10):
the hygiene bottleneck (5.Q/W.2) is **field-emptiness hallucination** (verified;
bot fabricates empty `Root_Cause` — actual empty-rate 1%) → the fix is a
**deterministic code-grounding** step (task 4.7), not a prompt or a Zaidul rubric
call — **BUILT + MEASURED 2026-06-08: Workflow F1 17.0→23.9% (+6.9pp), staged not
pushed** (`evaluator/hygiene_ground.py`, notebook cell 9 `ground_workflow_hygiene`);
the Quality bottleneck (5.Q/W.4) is **under-emission of an existing rule**
(verified; clarity rewrite 0→11%) → mostly local + a one-line Zaidul semantic
confirm. Nothing pushed; whole bundle awaits Sai's review + Zaidul sign-off.

## ⭐⭐⭐ Where we are now (2026-06-10) — reviewer-grade metric + prod-faithful real-KB run + v2/v3 tuning

**Biggest change-set in the project.** For the QA-team **500-case send** (reviewers grade
"is the RCA reasonable", not gold-match), pivoted the target to the **from-scratch
reasonableness judge** scored **gated** (`runner --judge-source regen` + `gated_reason.py`) —
a **third metric family** (not driver case-acc, not Q/W F1; never averaged).

- **Model lever exhausted** — `gemini-3.1-pro-preview` is the strongest model published to the
  project. Accuracy is now prompt/code only.
- **Real KB unblocked (Phase 1-adjacent)** — Rishita's prod creds (Dataform `:readFile`) read
  all 4 KB docs (197K, `kb_snapshot_real.txt`); `evaluator/run_prod_kb.py` runs the tuned
  pipeline locally with the real KB in **genai context caches** → 500 prod-faithful cases/27min.
- **Judge-fairness + Workflow-justification fix** → **Workflow 23.6→71.9%**.
- **Tuning (Phase 5.Q/W + drivers, on the reasonableness metric):** v2 KEPT (`agent4`
  New-Query clarification-exclusion + Quality severity rule; `quality/agent1` cosmetic-not-
  material; `ttr/agent1` Backlog-must-block; `reopen/agent1` thank-you). **v3's apparent
  regression was 3.1-pro RUN-NOISE (v2↔v3 churn 15–30% both ways) → reverted. v4 = a
  DETERMINISTIC noise-proof "Unmapped" re-resolution** (`evaluator/reresolve.py` + notebook
  `HierarchyResolver` patch): ~52 drivers the bot got right but the exact-match resolver dropped
  to Unmapped now resolve (noise-isolated proof: TTR 6→Correct/0 lost, Workflow 13→Correct/2
  lost). **v4 is FINAL.**
- **Numbers (real KB, gated, same 500):** v1→v2→v4 — TTR 60→75→**84**, Workflow 74→72→**79**,
  Reopen 32→32→**38**, Quality 71, Esc 90; **overall 63.8→68.7→71.7%, ex-Reopen 75.7%.**
- **Reopen = DATA ceiling** (re-confirmed; full-pop **46.7%**, DSAT **63.6%** — both understated
  by the 200 subsample) → real fix is **Phase 7 upstream ingest** (reopen reason). **v5
  deterministic Reopen demote BACKFIRED (NET −9) → reverted; v4 final.**
- **✅ DELIVERED TO QA (2026-06-10):** 500-case sample → Google Sheet
  `1aCU9s-haBosPY4lhfbyWsFV2Nb8hxF3a1drLAhlME6c` (dev format, **not yet shared**); 18 as-run
  prompts → QA-review doc `1ALZRqSB`. Source `evaluator/runs/QA_send_prodKB_500_v4.xlsx` +
  `QA_send_prompts_asrun.md`. Full record: `docs/session-2026-06-09-reasonableness-pivot.md`,
  `docs/stage-tracker.md` Stage 5.

## ⭐ Where we are now (2026-06-05, PM) — fix-v2 works, 3.1-pro staged

Built and **measured** the two levers; nothing pushed (Sai reviews first).

- **Aggregator fix-v2** (`prompts/hierarchy/agent4.md`): a Root-Cause Attribution
  Gate — user/external causes win Primary over agent-blame unless clear
  independent agent failure. Replaces the failed fix-v1 (sub-agent gate that
  agent4 overrode).
- **N=5×120 A/B on Gemini 3.1-pro, clean CI separation:** OVERALL **15.4%→22.4%**
  (+7.0pp); Reopen 8.5→15.9, Escalation 7.4→21.1, DSAT 0→11.4, TTR 24.6→29.0
  (no regression). The 3 over-blame frameworks all moved with non-overlapping CIs.
  Checkpoints `evaluator/runs/ab_{CTRL31,V2_31}_*.json`. (`--no-cache` absolutes
  sit below frozen-prod; the **delta** is the signal — anchor stays ~12.9%.)
- **Harness:** bot defaults to **3.1-pro** (matcher stays regional 2.5-pro);
  `ab_measure` reports OVERALL pooled accuracy + audited n; **`--resume-file`**
  makes runs Cloud-Shell-idle-safe (`$HOME`/checkpoints persist VM reclamation).
- **Prod notebook → 3.1-pro: STAGED, NOT PUSHED.** Additive gated global-genai
  path in cell 8 (rollback = set `agent_model` back to 2.5; `google-genai` added
  to pip; genai KB caching + inline fallback). Validated locally; real-KB caching
  only testable on the runtime post-push. **Accuracy still far below 80** → review
  before push. See `docs/session-2026-06-05-fixv2-ab.md`.
- **Next:** review→push the staged change, then **6-driver (Quality+Workflow)
  scoring** (`docs/quality-workflow-gold-scoping-2026-06-05.md`).

## ⭐ Where we are now (2026-06-05) — gold audited + window widened

Trust the ruler before chasing the number. Audited the QA-2026 gold
(`evaluator/gold_audit.py`, `docs/gold-audit-2026-06-05.md`) and acted on it:

- **Gold is clean** (2,691 usable rows Jan–Apr, 0 dups/blanks/placeholders, join
  health 97–100%) **but the updated taxonomy is only in use from March** (Sai) —
  Jan/Feb are old-taxonomy and must be excluded. **Quarter Freeze = 0 before
  March** is the cutover proof. **Set `cfg.QA2026_MONTHS` → March-onward**
  (`2026-03`,`2026-04`) = **1,778 valid gold cases**; April is latest labelled.
  Memory `project_taxonomy_cutover_march`.
- **Re-baseline on March–April** (`rebaseline_marapr_2026-06-05…csv`, frozen
  production preds) — **new anchor ~12.9%: TTR 18.65 / Reopen 6.94 / Escalation
  7.46 / DSAT 6.00** (1,415 audited). Supersedes Feb/Mar 12.99%; dropping
  pre-cutover Jan/Feb recovered Escalation/DSAT vs the polluted Jan–Apr run.
- **Two findings that reset expectations:** Quarter Freeze only appears from
  March (Mar+Apr = 164 cases; adding April ~2× the Mar-only signal). **Reopen
  Product/Tools Gap is 2 cases in the entire set** — that Phase-4.1 L1 is
  structurally right but won't move Reopen; the Reopen floor is the
  User-Gap/New-Query under-prediction, not missing drivers.
- **Reopen fix v1 reverted** (failed sub-agent gate) — prompts back to baseline +
  driver diff only, re-injected into the local notebook. Clean control for v2.
- **Matcher calibration generalised** to `evaluator/calibrate_matcher.py`
  (`--framework`); running for TTR/DSAT/Escalation (Reopen already PASS).
- **Label-quality nits for Zaidul:** `quality_reviewer` blank on ~36–44% of
  TTR/Reopen rows; a few comma-joined multi-L1 gold labels.

## ⭐ Where we are now (2026-06-04, end of day)

The inner-loop measurement stack is **built, validated, and now produced its
first clean numbers.** The "quota blocker" was mis-diagnosed and is resolved.
Two headline results: **a 3.1-pro model swap is a big accuracy lever; the
Phase-4 prompt diff is ≈0; Reopen's bug is now pinpointed.**

- **Quota was never a hard block.** All Gemini quotas are *per-minute*
  (self-heal); the nans were **bot+matcher self-saturating the same regional
  bucket**. Fixed with `ab_measure --force-global` (bot → global pool, matcher
  stays regional) + env `REGEN_CONCURRENCY`. Also fixed a **global-endpoint auth
  bug** (static token 401s under concurrency → ADC auto-refresh; 0 failures
  after). See Phase 2.11.
- **First directional A/B** (N=3×30, temp 0, no-cache, global bot): TTR
  **OLD-2.5 11.8% == NEW-2.5 11.8% → prompt effect ≈0**; **NEW-3.1-pro 33.3% →
  model effect +21.5pp** (same-endpoint, clean). 3.1-pro is non-deterministic
  even at temp 0 → N-run CIs still needed. See Phase 2.9.
- **Matcher calibration (Reopen, 45 cases) PASSES** (~90% judge↔human). Reopen
  "0%" was noise (true ~18% regional / ~11% global). **Root cause found:** the
  bot under-predicts **User Gap / New Query** (gold 62% of Reopen, bot gets
  0/28) and over-predicts People Gap; Quarter Freeze over-fires. See Phase 2.6.
- **Reopen prompt-fix v1 (sub-agent intent gate) FAILED** (11.1%→13.6%, noise;
  0/28 recovered) — the **aggregator (agent4) overrides** the sub-agent finding,
  so the fix must be aggregator-level. See Phase 5.1.
- **Measurement caveat:** regional ≠ global 2.5-pro (same prompts: 17.8% vs
  11.1%) — **hold the endpoint constant in every A/B.**

**Next concrete actions:** (1) diagnose the Reopen aggregator override (~10
cases, per-sub-agent output); (2) Reopen fix **v2 at `agent4`** (user-side
causes win over agent-blame); (3) take the **+21.5pp model-effect** result to
Zaidul/Pooja; (4) scale to N=5×120 on a stable network; (5) calibrate the
matcher for TTR/DSAT/Escalation; (6) decide agent-4 temp=0 for production.

## Status snapshot

| Phase | Status | Next concrete action |
|---|---|---|
| 0 Dev env          | ✅ done       | — |
| 1 OAuth rotate     | ⏳ next       | 1.1 mint token for cell 7 |
| 2 Evaluator        | 🟡 partial    | gold audited, window = March-onward (taxonomy cutover; 1,778 gold); re-baseline ~12.9% (TTR 18.7/Reopen 6.9/Esc 7.5/DSAT 6.0); 2.6 Reopen+TTR matcher PASS, DSAT/Esc calibration next; 2.9 model +21.5pp; 2.11 auth/quota fixes done |
| 3 QA mining        | ⬜ pending    | gated on 2.x |
| 4 May-14 encode    | 🟡 partial    | driver diff encoded+tightened (local); 4.3 KSI → **code** (decided), 4.5 Quality **resolved**, sign-off = live show-and-tell; **4.7 hygiene code-grounding ✅ DONE+measured** (Workflow F1 17.0→23.9, staged) |
| 5 Iterate to 80 %  | ⏳ active     | **Stage 1 staged** (drivers OVERALL 12.9→22.4; Q/W spike done — 5.Q/W.1/.3/.5 ✅, over-emission cut); **Stage 2: 5.Q/W.2 hygiene ✅ DONE (task 4.7, +6.9pp Workflow F1)**; **5.Q/W.4** Quality under-emission Zaidul-gated; **5.1 driver User-Gap lever ❌ NULL 2026-06-08** (recall 27→33% but acc 17.9→16.0, reverted — prompts don't move drivers) |
| 6 Version control  | ❌ dropped    | solo contributor — no git |
| 7 BigQuery         | ⏳ active     | 7.1 inventory current Tricks queries |
| 8 Schedulers       | ⬜ scope TBD  | confirm ownership |

Status legend: `✅ done` = every sub-step `[x]` · `🟡 partial` = mixed
`[x]`/`[ ]` · `⏳ next` = actively starting · `⬜ pending` = nothing
started · `[!] blocked` = at least one sub-step is `[!]`.

Update the row alongside the sub-step checkbox below — the checkboxes
remain source of truth; this table is the index.

---

## Phase 0 — Dev environment

- [x] **0.1 Local Python env.** Install runtime deps that mirror notebook
      cell 1.
      ```
      pip install gspread_pandas tenacity nest_asyncio \
                  google-cloud-aiplatform pydantic tqdm pandas
      ```
      Note: `gspread_pandas` pins `gspread` to `5.x` — expect a downgrade
      from 6.x if it's already installed. Harmless.
      Ref: `notebook/content.ipynb` cell 1; `evaluator/README.md`.

- [x] **0.2 OAuth token export.** Short-lived token for local runs.
      ```
      gcloud auth login
      export GOOGLE_OAUTH_TOKEN="$(gcloud auth print-access-token)"
      ```
      Note: the env var lives in the current shell only and the token
      expires ~1h after mint — re-export at the start of each new shell
      until the service-account fix in 1.4 lands.
      Ref: `CLAUDE.md` → Conventions (auth rotation); `evaluator/config.py`.

- [x] **0.3 Pull the live notebook + extract prompts.**
      ```
      ./scripts/pull_notebook.sh
      python3 scripts/extract_prompts.py
      ```
      Ref: `CLAUDE.md` → Common commands.

---

## Phase 1 — Rotate the production OAuth token

CLAUDE.md objective #5. Avoid an in-flight scheduler failure.

- [ ] **1.1 Mint Sai's own short-lived token** for cell 7 of the live
      notebook (replace the existing `ya29.…`).
- [ ] **1.2 Push the notebook** with the new token via
      `./scripts/push_notebook.sh`. Never commit the token to git.
- [ ] **1.3 Confirm next daily run** (12:00 IST scheduler
      `rubrics-automation-run`, id `1105207098007879680`) succeeds with the
      new token.
      Ref: `docs/resources.md` → GCP (canonical scheduler id + cron).
- [ ] **1.4 (Stretch / durable fix)** Scope service-account auth so we
      stop rotating tokens by hand.
      Ref: `CLAUDE.md` → Conventions; `notebook/content.ipynb` cell 7.

---

## Phase 2 — Stand up the inner loop (LLM-as-judge evaluator)

CLAUDE.md objective #1 prerequisite. Already scaffolded; remaining work
is calibration and use.

- [x] **2.1 Evaluator module scaffolded.** `evaluator/` with runner,
      aggregate, judge, hierarchy, schemas, judge prompt, gold/runs dirs.
      Ref: `evaluator/README.md`.

- [x] **2.2 Smoke test (Path A).** Read-only, judge-only. Completed
      2026-05-27 with 3-case run; first invocation surfaced four bugs that
      were fixed inline:
      - `evaluator/runner.py` — added `quota_project_id=cfg.PROJECT_ID` to
        the local `Credentials` so the Drive API call has a billable
        project (Colab runtime sets this automatically; local doesn't).
      - `evaluator/judge.py` — added `_strip_null_types()` helper and
        applied it to `JudgeVerdict.model_json_schema()` before passing
        as Vertex `response_schema`. Pydantic's `Optional[...]` emits
        `anyOf: [<type>, null]`, which Vertex's schema parser rejects.
      - `evaluator/judge.py` — provenance fields (`judge_model`,
        `judged_at`) now use unconditional assignment instead of
        `setdefault`. Gemini was hallucinating values (`gpt-4`,
        2024-dated timestamps) which `setdefault` was honouring.
      - `evaluator/aggregate.py` — `include_groups=False` on the
        `groupby().apply()` to silence the pandas FutureWarning.
      ```
      python3 -m evaluator.runner --sample 5 --framework Quality
      python3 -m evaluator.aggregate evaluator/runs/<latest>.csv
      ```
      Proves wiring + auth. ~5 Gemini calls.

- [x] **2.3 Gold source = the QA dump sheet (`1tbrQ…`), label-match.**
      Superseded the manual ~30-row curation. The dump holds thousands of
      human-reviewer L1/L2/L3 labels per framework + bot predictions in
      `RCA_Analysis_Output`. The evaluator joins them and asks the matcher
      whether bot == human. Built 2026-05-29: `evaluator/gold_dump.py`,
      `evaluator/prompts/judge_match.md`, `judge.match_case_framework`,
      `runner.py --match-labels`. Ref: `docs/connect-2026-05-29.md`;
      `evaluator/README.md`.

- [x] **2.4 Loader (replaces the old mine-QA-comments helper).**
      `gold_dump.load_labels` / `join_bot_and_labels` pull + join live
      from the dump; a real-case-id filter drops the dump's placeholder
      test rows. No manual export needed.

- [x] **2.5 Baseline accuracy snapshot (label-match).** Run 2026-05-29
      (all four driver frameworks in one invocation → one CSV):
      ```
      export GOOGLE_OAUTH_TOKEN="$(gcloud auth print-access-token)"
      python3 -m evaluator.runner --match-labels --sample 200
      python3 -m evaluator.aggregate evaluator/runs/2026-05-29T05-21-56Z.csv
      ```
      **Result — case-level accuracy 12.93% (95/735).** Per framework:
      TTR 16.0% (32/200), DSAT 13.2% (22/167), Reopen 13.1% (26/198),
      Escalation 8.6% (17/198). Error budget is **systemic** (all four
      8–16%), **88% of misses are full L1 mismatches** (not L3 wording),
      and **~16% of misses cite the un-encoded May-14 drivers** (Phase 4
      recovers these). Bot over-predicts a few defaults ("Process Gap /
      Backlog due to PPR", "People Gap / Completeness"). This 12.93% is a
      strict full-primary-driver match and is **not** the same measure as
      the project's prior "~50%" narrative — anchor all future deltas to
      this number. Recorded in memory `project_baseline_labelmatch.md`;
      Quality/Workflow scored-match is a follow-on (`docs/open-questions.md` #5).

- [ ] **2.6 Judge calibration (do before quoting 12.93% as absolute).**
      The matcher is itself an unvalidated LLM judge — no match-mode
      judge↔human agreement established yet. Hand-check ~30–50 label-match
      verdicts to confirm the matcher agrees with a human; aim ≥70%
      agreement (per `evaluator/README.md`). Below that, treat the number
      as a *relative* yardstick for deltas only. Borderline policy also
      swings it ±2pp (12.93% with Borderline as wrong → 15.1% as right).

- [x] **2.7 Regen harness — BUILT 2026-05-29 (`evaluator/regen.py`).**
      `--match-labels` scores *frozen* predictions, so a prompt/driver edit
      changes nothing it measures — predictions must be regenerated. The
      harness loads the production pipeline cells (2,4,5,6,8,9) out of the
      local notebook, wires auth + KB caching, runs the 4 driver frameworks
      on the **QA-2026 gold cases** (inputs read live from `Cases for
      Summary` — covers 862/869 gold cases; Raw Dump overlaps 0), and writes
      a regen CSV. Scored via `runner.py --gold-source regen --regen-csv`
      (joins regen predictions to QA-2026 gold). Validated end-to-end: the
      newly-encoded `Quarter Freeze / YoY Planning & Implementation` driver
      is now emitted by the regenerated bot.
      ```
      python3 -m evaluator.regen --sample 60 --framework Reopen TTR --no-cache
      python3 -m evaluator.runner --match-labels --gold-source regen \
        --regen-csv evaluator/runs/regen_<stamp>.csv --framework Reopen
      python3 -m evaluator.aggregate evaluator/runs/<latest>.csv
      ```
      - **KB-permission caveat (DIAGNOSED + DECIDED 2026-06-08).** The KB docs
        403 (`PERMISSION_DENIED`) for **every identity we can drive** — the local
        `saisreekark@google.com` token AND all runnable SAs (compute default,
        `compensation-support-bot@`). It's a **Drive ACL**, not scope/API/auth
        (the same token reads gold+I/O sheets fine; the drive scope is honored in
        Colab). The KB is shared only with the cell-7 user. So local regen runs
        **without real KB context** (`--no-cache`). **DECISION (2026-06-08): work
        KB-lite / delta-only** — the prod-faithful **KB snapshot** path is built +
        proven (`evaluator/dump_kb_snapshot.py` + `regen --kb-snapshot`;
        `gs://analytics_genai/kb_dump.ipynb` uploaded) but **PARKED**, one ACL grant
        away (Viewer on the 4 files to
        `653428233292-compute@developer.gserviceaccount.com`). Revisit only for a
        true absolute. Full diagnosis: `docs/kb-local-access-2026-06-08.md`.
      - **Clean local measurement = old-vs-new A/B.** Run regen with the
        **old** prompts and the **new** prompts on the *same* cases, same
        (no-KB) settings — the KB gap is constant and **cancels in the
        delta**, isolating the prompt effect. The control (old prompts) is
        free: `./scripts/pull_notebook.sh` re-fetches the production notebook
        (never pushed, still pre-Phase-4). Procedure: back up the edited
        notebook → regen treatment → pull old → regen control on the same
        `random_state=42` sample → restore edited notebook → score both.
      - **Clean A/B (temp 0, no-KB, ~50 audited/fw, old vs new prompts):**
        Reopen 13.0%→10.9% (**−2.2pp**, flips +0/−1); TTR 14.6%→12.5%
        (**−2.1pp**, flips +1/−2). At temp 0 the flips are tiny (≈1 case),
        so the encoding is **roughly accuracy-neutral-to-slightly-negative**
        here — *not* a win as written. **Why:** the new Quarter-Freeze driver
        fires in ~16% of cases (verdicts mentioning it: 0→8 Reopen, 0→7 TTR)
        but those emissions **don't match the human gold — it over-fires**,
        occasionally displacing a previously-correct driver. Action: tighten
        the Quarter-Freeze MATCH-IF (require explicit freeze evidence, not
        any delay/planning mention) before pushing; re-measure on a larger
        sample after calibrating the matcher (2.6). (An earlier temp-0.3 run
        showed −7pp but was noise-confounded — temp 0 is the trustworthy read.)
        NB: these absolute numbers aren't the production baseline (no-KB,
        small sample); only the **old-vs-new delta** is meaningful.
      - **🚨 BLOCKER FOUND — the pipeline is non-deterministic (~84% answer
        churn at temp 0).** Tightening the Quarter-Freeze MATCH-IF *worked*
        (firing 16%→6%), but the scaled A/B (200 cases) showed Reopen
        −4.7pp / TTR −8.5pp with **11 of 11 TTR regressions unrelated to the
        edit**. Direct check: the bot's primary L3 differs run-to-run on
        **169/200 (84%) of cases** for *both* frameworks — for TTR the prompt
        was functionally identical, so this is pure run-to-run variance.
        Causes: gemini-2.5-pro isn't deterministic at temp 0, compounded over
        3–4 chained agents, **and agent 4 (the aggregator that selects the
        final driver) is hardcoded `temperature = 0.2` in cell 9** (the
        `--temperature` override doesn't reach it).
        **Consequence: single-run A/B cannot measure a few-pp prompt effect.**
      - **✅ DETERMINISM FIX (2026-06-04): churn 84% → 23%.** Made the
        aggregator temp configurable (`regen.load_pipeline(agent4_temp=...)`
        patches the cell-9 literal) and wired it to `--temperature`. With the
        aggregator also pinned to 0, two same-prompt TTR runs now agree on
        **77%** of cases (was 16%). The hardcoded `0.2` was the dominant noise
        source. Residual 23% is gemini-2.5-pro's own temp-0 variance across
        the sub-agents → still needs N-run averaging (2.9). **Production
        recommendation:** drop the agent-4 temp to 0 in the live notebook for
        a more stable RCA (decision for Zaidul/Pooja; not pushed).
      - **Never push regen/IO config to the Dataform notebook** (daily
        scheduler). Ref: memory `project_regen_path.md`.

- [x] **2.8 Adopt the QA-2026 gold set (2026-05-29).** Replaced the old dump
      as the driver-framework gold. Sheet
      `1_MvXAMTIUcHS9ne9vJHnA_l9wviNW87mcmgNYnGkXlg` — recent (Jan–Apr 2026)
      manual QA labels in the **updated taxonomy** (Product/Tools Gap +
      Quarter Freeze actually appear). Driver tab `DSAT/Reopen/Escalation/TTR`
      split by `Stage`; filter Feb/Mar 2026 → 862 cases. Bot side joins from
      the **live output tab** (these recent cases aren't in Raw Dump). Wired
      as the evaluator default:
      ```
      python3 -m evaluator.runner --match-labels --gold-source qa2026 --sample 2000
      python3 -m evaluator.aggregate evaluator/runs/<latest>.csv
      ```
      Code: `cfg.QA2026_*` + `ERROR_L1`; `gold_dump.load_labels_2026` /
      `join_bot_and_labels_2026`; `runner.py --gold-source`.
      **Baseline (run `2026-05-29T12-10-16Z`):** driver-level **12.99%**
      (TTR 20.8 / Reopen 6.6 / Escalation 7.8 / DSAT 7.9); **error-detection
      68.5%** under "no People Gap = no error" (TTR 83 / Reopen 60 /
      Escalation 61 / DSAT 24). Reopen floor = un-encoded Product/Tools Gap;
      DSAT over-predicts People Gap. **New anchor** — supersedes 12.93%.
      Ref: memory `project_gold_qa2026.md`.

- [~] **2.9 N-run measurement with confidence intervals
      (`evaluator/ab_measure.py`, BUILT 2026-06-04).** Because the pipeline is
      ~23% non-deterministic even at temp 0 (2.7), one regen run can't measure
      a few-pp change. `ab_measure` runs regen + label-match **N times on the
      same cases** and reports per-framework accuracy as **mean ± 95% CI**.
      A/B = run it on the NEW (edited) notebook, then `pull_notebook.sh` the
      OLD one and run again; the prompt effect is real only if the CIs
      separate.
      ```
      python3 -m evaluator.ab_measure --label NEW --runs 5 --sample 120 \
        --framework TTR Reopen --temperature 0 [--model gemini-3.1-pro-preview]
      ```
      - Validated at small scale (FIXSMOKE 20 cases × 3 runs: 20/25/40% — the
        wide spread is exactly why N-run CIs are needed). Single-loop fix
        applied (repeated `asyncio.run()` was nan-ing runs 2+).
      - **[!] BLOCKED on Vertex quota (2026-06-04).** The day's repeated heavy
        runs **depleted the gemini-2.5-pro per-minute quota**; full N=5×120×2
        batches now saturate it instantly → `ResourceExhausted` → 4× backoff
        → nan runs. Small batches (≤~30 cases) still work. Mitigations added:
        `REGEN_CONCURRENCY=2`, `JUDGE_CONCURRENCY=8`, 20s inter-run sleep —
        not enough once depleted. **Next:** run the full N-run A/B (prompt
        effect OLD-2.5 vs NEW-2.5; model effect NEW-2.5 vs NEW-3.1) when the
        quota recovers, or request a QPM bump for `gemini-2.5-pro` /
        `gemini-3.1-pro-preview`. Partial clean data so far: NEW-2.5 TTR
        ≈16.2% (n=2), Reopen ≈16% (n=2) — not enough runs for a CI.

- [~] **2.10 Latest-model exploration — Gemini 3.x (2026-06-04).** The Vertex
      project lists Gemini 3.x but they **404 in `us-central1`** — served only
      from the **`global`** endpoint, which the notebook's legacy `vertexai`
      SDK can't target. Confirmed callable via `google-genai` (1.68.0, already
      installed): **`gemini-3.1-pro-preview`** (latest pro) and
      `gemini-3.5-flash`; `gemini-3-pro-preview` is superseded (404). Wired a
      `--model` flag into `regen.py` / `ab_measure.py` that routes the **bot**
      through the global endpoint via google-genai (same
      `generate_content_async().text` interface; requires `--no-cache`). The
      **matcher stays on gemini-2.5-pro** so the measurement instrument is
      fixed. Validated: 3.1-pro emits valid driver JSON end-to-end. The
      accuracy comparison (2.5-pro vs 3.1-pro) is pending the quota recovery
      in 2.9.

---

## Phase 3 — Mine the QA comments for prompt-edit signal

How phase 4 actually happens — without this, prompt edits are guesses.

- [ ] **3.1 Pull every row with non-empty N+ QA comments** from the I/O
      sheet (reuses 2.4 if built).
- [ ] **3.2 Cluster "Incorrect" reasons** by failure mode. Most common
      shapes (from `docs/prompts-strategy.md` § 1): overlapping L3 pairs,
      missing priority rules, off-rubric labels.
- [ ] **3.3 Map each cluster to a fix type:**
      - prompt-clarity rewrite (in `prompts/<framework>/agentN.md`)
      - new priority rule
      - few-shot example (Lever 2 in `docs/prompts-strategy.md`)
- [ ] **3.4 Park the cluster list** in `docs/qa-comment-clusters.md`
      (new file) as the backlog for phase 4.

---

## Phase 4 — Encode May-14 framework updates

CLAUDE.md objective #2 + #3. Gated on the live session with Zaidul to
lock the exact wording — but the file-level edits are pure execution.

Ref: `docs/frameworks.md` (hierarchy reference + "not yet encoded"
banner); `docs/architecture.md` → Pipeline internals (which cells the
diff touches).

- [x] **4.1 Reopen — add L1 `Product/Tools Gap`** (2026-05-29, local only).
      Added to `HIERARCHY_CONFIG` cell 4 (Product Limitation: Feature not
      available, Latency; Product Bugs: GCBP, internal tools) and to
      `prompts/reopen/agent3.md`. Also renamed the drifted L3 `Complex
      Processes e.g. Quarter close guidelines` → `Complex Processes`.
      ⚠ **Not pushed to prod / not Zaidul-reviewed.** Headroom on the
      QA-2026 Feb/Mar gold = **0 Reopen cases** (none labelled
      Product/Tools Gap in that window) — structurally correct, but moves
      nothing on the current gold sample.
- [x] **4.2 All 4 driver RCAs — add L3 `Quarter Freeze / YoY Planning &
      Implementation`** (2026-05-29, local only) under Process Gap →
      Workflow Complexities in Reopen / TTR / Escalation / DSAT (cell 4 +
      `prompts/{reopen/agent3,ttr/agent2,dsat/agent3,escalation/agent2}.md`).
      Headroom on the QA-2026 Feb/Mar gold ≈ **64 cases (~6%)** whose human
      label references quarter-freeze/YoY — the ceiling this unlocks once
      predictions are regenerated.
- [~] **4.3 KSI TTR-exclusion filter — BUILT 2026-06-09 (deterministic CODE, gated,
      staged-not-pushed); full measure auth-gated.** The qualifier is no longer
      Zaidul-gated — it was doc-derived + CLOSED 2026-06-09 (`open-questions.md` RESOLVED
      #2). A closed case is **NULL for TTR** when **(a)** a known-systemic marker is
      present — a `KSI -`/`KSI:` tag in `Root_Cause_Description` *or* a populated `Bug_Id`
      + a pending-Eng-fix phrase (SOP "Outcome 3") — **and (b)** the fix is pending a
      future/uncommitted resolution. Built as a deterministic pre-LLM filter (task-4.7
      pattern, NOT a prompt — the model can't be trusted to read structured markers):
      `evaluator/ksi_ground.py` (single source of truth) + an inline mirror in cell 9
      (`is_ksi_excluded`, gated `EXCLUDE_KSI_FROM_TTR=True`, rollback `False`) wired into
      `process_single_row` so a KSI case never triggers a TTR audit. Extends the shipped
      `<7 days = null` gate (`aging_days >= 7`).
      **Measured LIVE 2026-06-09 (`evaluator/ksi_measure.py`):** fires on **116 / 2,592
      (4.5%)** of TTR-audited cases (Closed & aging≥7); marker split **KSI-tag 101 /
      Bug_Id+pending 15**. **Gold-validated:** of the 46 excluded cases in the QA-2026 TTR
      gold (Mar–Apr), the human primary-L1 is **35 Product/Tool Gap + 8 Process Gap + 3
      User Gap = 46/46 external/upstream, ZERO People Gap** → the filter removes exactly the
      cases gold confirms are NOT agent responsiveness defects. **Accuracy delta (fresh Mar–Apr
      TTR label-match, 858 verdicts): TTR 17.6%→16.4%, Δ −1.2pp** (removed 46: 18 Correct / 28
      Incorrect — the bot matches the external driver on 39% of KSI cases, above baseline, so the
      headline dips slightly). **The KSI filter is metric-VALIDITY (SLA/breach hygiene), NOT an
      RCA-accuracy lever.** Labeling nuance flagged: the gold still *audits* KSI cases with
      external drivers rather than NULLing them → Zaidul confirm = exclude-entirely vs
      attribute-to-external. Ref: `docs/session-2026-06-09-ksi-kb.md`; `open-questions.md` RESOLVED
      #2; `evaluator/ksi_ground.py` / `ksi_measure.py`.
- [ ] **4.4 Enumerated additions across TTR / Reopen / DSAT / Escalation**
      from the live session (pending — `docs/connect-2026-05-14.md`).
      Ref: `docs/open-questions.md` #1.
- [ ] **4.5 Quality consolidation shape** (5-agent → fewer) — **TREATED RESOLVED
      2026-06-08 (item 4).** The current **3-agent** split already enumerates all 5
      metrics — the exact condition Zaidul set on May 14. Business action = a one-line
      Zaidul confirm in the show-and-tell; no further code work planned.
      Ref: `docs/open-questions.md` #3.
- [x] **4.6 `python3 scripts/inject_prompts.py`** — ran 2026-05-29, folded
      all 18 prompts into the local notebook cell 5. Hierarchy parser
      verified emitting the new nodes. **Local mirror only — `push_notebook.sh`
      deferred to Zaidul sign-off.**
- [x] **4.7 Deterministic hygiene-field grounding (DONE + measured 2026-06-08,
      staged-not-pushed).** The Workflow "Missing vector case hygiene fields" rule
      over-fired (293/300 = 97.6%) because the model **hallucinates** empty
      `Root_Cause`/`Root_Cause_Description` (actual empty-rate 0.67%). Built a
      **deterministic post-filter** — `evaluator/hygiene_ground.ground_workflow_output`
      (measurement, via `evaluator/ground_hygiene_csv.py`) + an inline mirror
      `ground_workflow_hygiene` in `notebook/content.ipynb` cell 9, gated behind
      `GROUND_WORKFLOW_HYGIENE` (rollback = `False`). It recomputes the **literal rule 9**
      (Closed AND any of `Root_Cause`/`Root_Cause_Description`/`Next_Steps` empty, +
      Comp/Attainment extras, issue-type-gated) from the real case fields and suppresses
      the driver when nothing is genuinely empty (a missing column = unknown, never
      "empty"). **Result (same-cases, held-out May): Workflow detection F1 17.0→23.9%
      (+6.9pp)**, precision 9.3→13.6, recall held 100%, 27 pure-hallucination FPs killed.
      **The `Next_Steps` question is answered by gold** (6/8 held-out "missing hygiene"
      gold errors = populated Root_Cause + empty `Next_Steps`), so the literal rule 9 is
      the gold-aligned grounding. **Zaidul CONFIRMED 2026-06-08: every closed case with an
      empty `Next_Steps` IS a defect (yes)** → the grounding is validated as-is; the residual
      precision gap (49 held-out "FPs") is **gold UNDER-labelling, not bot over-firing**, so
      the +6.9pp F1 is conservative. **Question CLOSED.** Ref:
      `docs/stage-tracker.md` Stage 2; `session-2026-06-05-6driver.md` §10; Phase 5.Q/W.2.

### Phase 4 sign-off plan — most items RESOLVED by Zaidul 2026-06-08

The May-14 framework diff is encoded locally (4.1/4.2). Zaidul's answers (2026-06-08):
1. **New L1 `Product/Tools Gap` + L3 `Quarter Freeze / YoY Planning & Implementation`** —
   **APPROVED. ✅ CLOSED.** Wording confirmed; **spell-checked clean 2026-06-08** (consistent
   across all 18 prompts + `HIERARCHY_CONFIG`, no typos). Caveat unchanged: Reopen Product/Tools
   Gap is ~2 gold cases — structurally right, won't move the number.
2. **KSI auto-close** — engineering decision = **code** (4.3). **Zaidul gave one rule:
   a case resolved/aged `< 7 days` is NULL for TTR** (no TTR defect) ⇒ **DONE 2026-06-08
   (staged): cell-9 trigger `Case_Aging_in_Days > 5` → `>= 7`.** **Still owed:** the full KSI
   qualifier (what marks a "known issue" + which future-resolution-date test auto-closes a case
   out of TTR/SLA).
3. **Quality consolidation (5→3 agents)** — **RESOLVED to "whatever measures best" (Sai's
   call).** Zaidul defers the structure to whichever (1-agent vs 3-agent) scores best on the
   detection metric; pick by measurement, not by design debate.
4. **Workflow hygiene `Next_Steps`** — **CONFIRMED: every closed case with empty `Next_Steps`
   IS a defect.** ⇒ task-4.7 grounding validated as-is; measured precision is gold-limited.
5. **Driver reopen-new-query** — **CONFIRMED: it IS User Gap (New Query).** ⇒ build the
   deterministic code re-attribution (Phase 5.1).

### Gold-semantics defaults (decided 2026-06-08, item 3 — insulate the pipeline, keep Zaidul informed)

No code change needed — these defaults already hold in `evaluator/multilabel_score.py`
/ `gold_dump.py` (see `session-2026-06-05-6driver.md` §6). Recorded so they're not
re-litigated, with the one-line Zaidul confirmations owed:
- **`Error Status`** = a **coarse flag, NOT the label** (`Yes`=2031 ≫ ~164 real
  dimension errors). Confirm: what does `Error Status` track?
- **May'26** = **included** for Workflow (bigger error denominator) but **reported
  separately**. Confirm: is the workflow taxonomy comparable across the March cutover?
- **Critical/Non-critical** = **reported as a breakdown, NOT weighted.** Confirm intent.
- **`Unmapped` bot L1/L2** = **excluded from the precision denominator** (diagnostic
  `n_unmapped_only`). It's a pipeline taxonomy-resolver gap, not a real driver.
- **Compliance sub-dimension** = **dropped** (2 positives — effectively dead).

---

## Phase 5 — Iterate to 80 % (the main one)

CLAUDE.md objective #1. The loop runs until accuracy clears 80 % per
framework on the 200-case sample.

> **ALL 6 FRAMEWORKS ARE IN SCOPE (Sai's call 2026-06-07).** Quality and
> Workflow are now first-class accuracy-improvement targets, not report-only.
> They use a **different metric** from the 4 drivers — detection **precision /
> recall / F1** on the error class, not case-level Correct÷Audited (because
> ~94% of Workflow is "no error", so plain accuracy is meaningless). Measure
> them with `regen --framework Quality Workflow` → `runner --match-labels
> --gold-source regen` (detection scorer); the 4 drivers stay on `ab_measure`.
> Their dominant problem is **over-firing**, diagnosed in
> `docs/session-2026-06-05-6driver.md` §3d — see Phase 5.Q/W below and the
> Q/W lever in `docs/prompts-strategy.md`.

> 🚨 **PREREQUISITE (found 2026-05-29 via the regen A/B): the pipeline is
> ~84% non-deterministic at temp 0** — a single before/after run cannot
> measure a few-pp prompt change (see Phase 2.7). Before this loop is
> trustworthy: (a) drop the hardcoded `temperature = 0.2` on agent 4 (cell
> 9) and/or add self-consistency voting; (b) measure each prompt variant as
> the **mean of N≥5 runs with a confidence interval**, not one run. Treating
> single-run deltas as signal will chase noise.

For each iteration:

- [ ] **5.x.1 Pick target framework** = lowest accuracy in latest
      `aggregate` output.
- [ ] **5.x.2 Pick one fix** from phase 3 backlog or phase 4 diff.
- [ ] **5.x.3 Edit `prompts/<framework>/agentN.md`** only — never the
      notebook directly.
- [ ] **5.x.4 `python3 scripts/inject_prompts.py`**.
- [ ] **5.x.5 Re-measure.** For the four driver frameworks, measure via
      the **regen harness (2.7)** — regenerate predictions on the same
      `Raw Dump` sample, then `--match-labels` against the human labels
      (the `--sample 200` live-sheet path is judge-from-scratch and does
      *not* reflect prompt edits against the dump). Reuse the same seeded
      sample for a comparable delta vs the 12.93% baseline.
- [ ] **5.x.6 Gate:** ≥ +5 pp on target framework, no regression on
      others → take the diff to Zaidul. Otherwise revert.
- [ ] **5.x.7 On Zaidul sign-off** → `./scripts/push_notebook.sh` and
      re-run on full ~3000-case batch via the scheduler.
      Ref: `docs/prompts-strategy.md` → Iteration loop (target).

### Phase 5.1 — Driver User-Gap lever (ATTEMPTED 2026-06-08 — NULL, reverted)

First data-chosen driver iteration after Stage 1. **Outcome: no accuracy gain; reverted.**
Full KT: `docs/session-2026-06-08-driver-usergap.md`; memory `project_driver_usergap_ceiling`.

- **Diagnosis (solid, reusable):** profiled gold primary-L1 composition + bot L1 confusion.
  The dominant driver miss is **User Gap under-prediction** — gold's plurality/majority L1 in
  3 of 4 frameworks (Reopen 62%, Escalation 68%, TTR 41%, DSAT 40% w/ Process 43%), but the
  bot emits it as primary only ~5–27%, defaulting to **Process / People Gap**. Structural
  cause: 2 of 3 driver sub-agents are blame-oriented (Reopen agent2=soft-skill→People,
  agent3=process→Process); only agent1 (triage) can surface User Gap, and `reopen/agent1` had
  **no rule** for the dominant gold driver *"Additional or different Query"* (49% of Reopen
  gold) — rule 2 even said to *ignore* questions.
- **Lever (5.x.2/.3):** `reopen/agent1` New-Query rule + `hierarchy/agent4` gate clause 2b
  (prefer user-side over external-side when both present).
- **Measured (5.x.5, same-cases regen, 3.1-pro temp 0, n≈95 Reopen):** User-Gap **L1 recall
  27→33%**, but **matcher accuracy 17.9→16.0%** (single-run noise — NOT a gain). Even
  instructed, the bot emitted "Additional or different Query" only ~13/150 vs gold ~49% — the
  model **resists reclassifying**.
- **Gate (5.x.6): FAILED → reverted both edits.** Re-confirms the 2026-06-04 finding "prompt
  diff ≈0; the model was the lever." Drivers stay at Stage-1 **22.4%**.
- **Zaidul CONFIRMED 2026-06-08: a reopen-with-new-query IS "User Gap (New Query)"** (gold
  right, model wrong). We built the **deterministic re-attribution** (agent1 New-Query surfacing
  rule + a hard cell-9 code override that promotes a surfaced New-Query finding to Primary,
  bypassing agent4). **Measured (`ab_measure` 3×120 Reopen, 3.1-pro): OLD 20.0% ±3.6 → NEW
  22.5% ±6.2 = Δ +2.5pp, CIs OVERLAP → fails the +5pp gate → REVERTED.** The override beat the
  prompt-only null (so agent4 demotion is *part* of the blocker), but the gain is capped by the
  **surfacing wall** (agent1 emits New Query ~13/150). **Phase-3 lever = a dedicated New-Query
  detector** (focused classifier or deterministic data signal), not a bigger override. KT
  `docs/session-2026-06-08-driver-usergap.md`.

### Phase 5.1b — Dedicated New-Query detector (BUILT 2026-06-08 — NULL: a DATA ceiling, reverted)

The Phase-3 driver lever carried from 5.1. **Outcome: no gain; the Reopen plateau is a
data-instrumentation ceiling, not prompt/model.** Full KT + recoverable build:
`docs/session-2026-06-08-newquery-detector.md`; memory `project_driver_usergap_ceiling`.

- **Built (task-4.7 pattern, gated, reverted):** `REOPEN_NEWQUERY_DETECTOR_PROMPT` — a focused
  single-decision YES/NO classifier (ignore agent behaviour; YES iff the reopen raises a
  new/different/additional request beyond the original issue) — + cell-9 `detect_new_query` /
  `apply_new_query_override` (`NEWQUERY_DETECT`) that force-emits
  `User Gap | New Query | Additional or different Query` as Primary, bypassing agent4.
- **Measured detector-vs-gold (n=60 held-out April, 3.1-pro, temp 0)** — cheaper + more
  mechanistic than a full A/B: detector **YES rate 5%**, gold New-Query **47%**, **recall 7%**
  (precision 67%). The dedicated, unconflicted classifier inherits the **exact same ~9%
  reluctance** as the triage agent — it does NOT break the surfacing wall. A full A/B would only
  confirm ≈0 (CIs overlap) at high cost; skipped.
- **Root cause (the finding):** the wall is a **DATA ceiling.** (1) the constructed input has
  **no `<<< SYSTEM LOG: CASE CLOSED >>>` marker** the prompts rely on (`CASE CLOSED` count = 0);
  (2) splitting the transcript at metadata `Reopen Date` recovers a post-reopen seller message
  for only **3/28** gold New-Query cases — for 25/28 the reopen fires within seconds of closure
  with no distinct new-query message; (3) **no `Reopen_Reason`/reopen-comment field** exists in
  the input. So the reviewer's "Additional or different Query" signal is from a source the
  pipeline **doesn't ingest** ⇒ ~47% of Reopen gold is structurally unreachable at the agent
  layer. Explains every prior null (emission ~9%, prompt ≈0, override +2.5pp, detector 7%).
- **Gate: FAILED → reverted; Stage 1/2 untouched. Drivers stay 22.4%.**
- **Real Phase-3 lever = UPSTREAM data ingestion** (reopen reason / first post-reopen seller
  message into `Cases for Summary`; data-load side — Vikram / Tricks→BigQuery), then restore the
  detector from the KT doc. **Open for Zaidul/data:** which field do reviewers read to label
  "Additional or different Query," and can it be surfaced into the pipeline input?

### Phase 5.1c — Reopen prompt lift (P3-A v2) — ✅ PHASE 3 WIN (2026-06-09, kept + staged)

The *reachable* lever that cleared the gate after the detector null. Full record + restorable
blocks: `docs/phase3-experiments.md`; all-6 scorecard: `docs/stage-tracker.md`.

- **Change (P3-A v2):** (1) `reopen/agent1` PRIORITY-4 **"Additional or different Query" catch-all**
  — a valid substantive reopen (not blank/thank-you/duplicate, not a responsiveness/timeline
  failure) **defaults to User Gap → New Query**, encoding the reviewer's process-of-elimination
  convention *without* the un-ingested reopen text; (2) `hierarchy/agent4` clause promoting that
  **New-Query finding** over the downstream external step (fixes the tie-breaker that demoted it).
- **Powered Reopen A/B (3.1-pro, temp 0):** April (full pool) **22.8% ± 1.3 → 29.0% ± 3.0 (+6.2pp)**;
  Mar–Apr **19.5% ± 2.5 → 24.6% ± 1.4 (+5.1pp)** — CIs separated both → **PASS.**
- **Regression found + fixed (why it's "v2"):** the *generic* agent4 clause (prefer any user-side)
  **regressed Escalation −3.2pp** (Mar–Apr powered, CIs separate). **Scoping the clause to the
  New-Query finding only** restored Escalation to neutral (15.8→15.7%) while keeping the Reopen win.
  TTR neutral (+1.1); DSAT inconclusive (n≈51).
- **Methodology lesson:** April-only multi-framework `ab_measure` was underpowered (Reopen n=51 with
  an OLD outlier; Esc n=13) and **masked both the win and the regression** → always power the target
  framework directly (dedicated `--framework X --sample`, Mar–Apr).
- **Disposition:** KEPT = P3-A v2, re-applied + injected (staged-not-pushed). Q/W untouched
  (driver-only). **Phase 3 = a measured Reopen lift (+5–6pp), no regression elsewhere.**

### Phase 5.Q/W — Quality + Workflow accuracy (the over-firing fix)

Tracked as task #13. Built + measured + diagnosed 2026-06-05/07 (KT
`docs/session-2026-06-05-6driver.md` §3c/§3d). **DRAFTED + MEASURED 2026-06-07
(§9):** the two no-Zaidul levers (5.Q/W.1 + 5.Q/W.3) are done and staged — they
cut over-emission (Workflow drivers/case 1.53→1.13, re-open 17→10%) and lift
Quality L3-classification (+7pp), but **do NOT move headline F1**: both F1
bottlenecks (Workflow hygiene rule 5.Q/W.2, Quality vocab 5.Q/W.4) are **gated on
Zaidul** = Stage 2. Best F1 so far (3.1-pro): Quality **~39%**, Workflow **~12%**.
Architecture is fine ("None" *is* allowed — 3 sub-agents, each picks one L3 or
"None", cell-9 adds every non-None as a driver; no agent-4). The fix is
**prompt-only**:

- [x] **5.Q/W.1 Metadata-gate hallucination — DONE 2026-06-07 (drafted + measured).**
      Added an inline `Reopen_Counter > 0` GATE on `workflow/agent1` rule 6 + a
      "check the metadata gate first / default to None" instruction across all 6
      Q/W sub-agents. **Result (3.1-pro, clean OLD-vs-NEW):** re-open firing
      **17%→10%**, avg drivers/case **1.53→1.13**. NB the 2.5-pro "89%" was a model
      artefact — 3.1-pro already self-corrects to 17%, so the gate's headroom is
      smaller than the §3d diagnostic implied. (`session-2026-06-05-6driver.md` §9.)
- [~] **5.Q/W.2 Hygiene over-firing — RE-DIAGNOSED 2026-06-08 (spike): it's
      HALLUCINATION, not rule breadth → Stage 2 = CODE, not a prompt.** The Workflow
      detection-F1 bottleneck. The pre-spike belief was "rule too broad (empty
      `Next_Steps` trips it on 65%)". **Disproven:** I narrowed rule 9 to drop the
      `Next_Steps` trigger and keep only `Root_Cause`/`Root_Cause_Description` empty —
      the bot **still fired hygiene on 87%** (was 97%) by **fabricating** that those
      fields are empty (verified: actual empty-rate **1%**; e.g. case `70387546`
      `Root_Cause="User Education"` but bot said empty). May F1 even dipped 17.0→14.5.
      ⇒ **A prompt edit can't fix it** (model ignores real field values). **Real fix =
      deterministic code-grounding** (compute the violation from actual field data in a
      `prepare_workflow_input` / post-filter) → **task 4.7**. Prompt edit **reverted**;
      Zaidul confirm narrows to: *does empty `Next_Steps` on a closed case ever count?*
      See `session-2026-06-05-6driver.md` §10.
- [x] **5.Q/W.3 Over-eagerness / reframe "None" — DONE 2026-06-07.** Rewrote the
      shared instruction block in all 6 sub-agents (Workflow: "None is the default,
      most cases have no violation"; **Quality: softened** after the strong prior
      cratered Quality recall −19pp → F1 −5.2pp). **Quality April F1 OLD 40.8 →
      strong 35.6 → softened (staged) 39.1** (~neutral, n=35) with **L3-class
      65→72% (+7)**. Lesson: framing must be **per-framework**, not blanket.
- [~] **5.Q/W.4 Quality structure-error — RE-SCOPED 2026-06-08 (spike): NOT a vocab
      gap, it's UNDER-EMISSION of an existing rule → mostly local + a 1-line Zaidul
      confirm.** The Quality F1 bottleneck. The pre-spike belief was "the bot *can't*
      emit *did not structure response* — vocab gap". **Disproven:** the rule **is** in
      vocab (`quality/agent1.md` rule 3); the bot just emitted it **0/85**. A concrete,
      recall-friendly rewrite of rule 3 + a tie-break (form vs grammar=rule 2 vs
      missing-answers=Completeness) raised emission **0→11%** (gold ~38%), lifted
      L3-classification **+3.8** (68.4→72.2) and Accuracy F1 +10.5 — but the new
      structure firings are **FPs on held-out**, so headline F1 was flat-to-down
      (40.9→37.5, n=35 noise). ⇒ emission + classification are **local** wins; the F1
      gain needs **Zaidul's one-line confirm** that his label = the same concept (so
      firings can be targeted to true structure errors). Prompt edit **reverted to
      Stage-1, carried as a ready proposal** (rule-3 text in §10 + git history). See
      `session-2026-06-05-6driver.md` §10.
- [x] **5.Q/W.5 Measure on a HELD-OUT split — DONE 2026-06-07.** Month split
      (Quality→April, Workflow→May) via `--months`; clean same-cases OLD-vs-NEW on
      3.1-pro (KB gap cancels in the delta). Confirmed: the two no-Zaidul levers cut
      over-emission + lift sub-error classification but **do not clear the +5pp F1
      gate** — both real F1 levers are the Zaidul-gated 5.Q/W.2 + 5.Q/W.4 (Stage 2).

---

## Phase 6 — Version control ❌ DROPPED (2026-05-29)

Sai is the only person working on the repo, so git hosting was dropped —
no venue decision, no git-init. (Was CLAUDE.md objective #4.)
Ref: `docs/resolved-questions.md` #18.

---

## Phase 7 — Tricks → BigQuery migration (parallel track)

CLAUDE.md objective #6. Independent of accuracy work; runs alongside
phase 5. Confirmed work item, **not gated on anyone** (2026-05-29) — the
old "wait for Pooja's SQL Miner / Colab paths" dependency is dropped; use
them if they arrive, but don't block on them.

- [ ] **7.1 Inventory the current Tricks data reads.** Identify every
      place the pipeline pulls case data from the sheet — primarily the
      input load (`Cases for Summary`) read in
      `notebook/content.ipynb` cell 10 (`Spread.sheet_to_df`). List the
      columns consumed (cross-check `COL_MAPPING`, cell 2).
      Ref: `docs/architecture.md` → data flow.
- [ ] **7.2 Locate / define the BigQuery source.** Find the BQ table(s)
      that back the Tricks sheet (or the SQL Miner query that populates
      it) and confirm the schema covers every column from 7.1. Note the
      project / dataset / table.
- [ ] **7.3 Add a `DATA_SOURCE` flag** (`sheet` | `bq`) in cell 2 and a
      `read_cases_from_bq()` path alongside the existing sheet read, so
      the switch is reversible and testable.
- [ ] **7.4 Validate parity.** Run the same case set through both
      sources; outputs must be byte-identical (compare on
      `RCA_Analysis_Output_1` columns). Gate the cutover on this.
- [ ] **7.5 Cut over** `DATA_SOURCE=bq` once parity holds; keep the sheet
      path as fallback for one full cycle before removing it.

---

## Phase 8 — Schedulers (deferred, scope unclear)

The phrase "2/3 schedulers to be built" needs clarification before any
work starts.

- [ ] **8.1 Clarify scope.** Possible candidates:
      - new scheduler for the evaluator (nightly accuracy regression)
      - replacement scheduler for `rubrics-automation-run` (the daily
        12:00 IST RCA job)
      - input-load scheduler that fills `Cases for Summary` (this one is
        Vikram's — likely not ours to touch)

      Ref: `docs/open-questions.md` #10; `docs/architecture.md` →
      Schedulers.
- [ ] **8.2 Confirm ownership per scheduler** before touching anything.
      Ref: `CLAUDE.md` → Conventions ("Don't touch the schedulers until
      we've confirmed who owns each").
- [ ] **8.3 Then build / migrate** whichever are in scope.

---

## Cross-reference index

| Activity | CLAUDE.md objective | Doc reference |
|---|---|---|
| Phase 1 OAuth rotation | #5 | `notebook/content.ipynb` cell 7 |
| Phase 2 Evaluator | #1 (enables) | `evaluator/README.md` |
| Phase 3 QA mining | #1 (enables) | `docs/prompts-strategy.md` Lever 2 |
| Phase 4 May-14 encode | #2, #3 | `docs/connect-2026-05-14.md`, `docs/frameworks.md` |
| Phase 5 Iterate to 80 % | #1 (main) | `docs/prompts-strategy.md` |
| Phase 6 Version control | ~~#4~~ dropped | `docs/resolved-questions.md` #18 |
| Phase 7 BigQuery | #6 | `docs/resources.md` |
| Phase 8 Schedulers | (none yet — out of scope) | `CLAUDE.md` → Conventions |

## What's deliberately not in this plan

- The 2026-06-15 demo (firm deadline) — coordination, not execution.
- Dashboarding — parked per May 14.
- Model swaps — frozen per May 14.
