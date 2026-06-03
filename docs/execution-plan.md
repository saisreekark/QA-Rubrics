# Execution plan — Rubrics, June demo path

Pure-execution checklist. Meetings, presentations, and stakeholder
coordination live elsewhere (see `docs/connect-2026-05-14.md` and
`CLAUDE.md` → Stakeholders). This doc is the work *Sai owns at the
keyboard*.

Sequence: top to bottom, except where noted as "parallel track".
Tick items as they ship.

Legend: `[ ]` pending · `[x]` done · `[~]` in progress · `[!]` blocked

## Status snapshot

| Phase | Status | Next concrete action |
|---|---|---|
| 0 Dev env          | ✅ done       | — |
| 1 OAuth rotate     | ⏳ next       | 1.1 mint token for cell 7 |
| 2 Evaluator        | 🟡 partial    | 2.7 build regen harness · 2.6 judge calibration |
| 3 QA mining        | ⬜ pending    | gated on 2.x |
| 4 May-14 encode    | ⬜ pending    | gated on Zaidul session |
| 5 Iterate to 80 %  | ⬜ pending    | gated on 2 + 4 |
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

- [ ] **2.7 Regen harness — test prompt/driver changes via label-match.**
      `--match-labels` scores the *frozen* predictions in the dump's
      `RCA_Analysis_Output` tab, so editing prompts does **not** change
      what it measures. To test a prompt/driver change, regenerate
      predictions first. Inputs already exist — the dump's **`Raw Dump`**
      tab (13,988 rows) is the exact population that produced the frozen
      predictions (overlap matches bot⋂label counts: TTR 4389 / Reopen
      2595 / Escalation 1441 / DSAT 324; transcript populated; all
      `COL_MAPPING` cols present).
      - **2.7.1** Build `scripts/run_regen.py`: sample 30–50 labeled
        cases/framework from `Raw Dump`, run the pipeline, write to a new
        dump tab (`RCA_regen_test`). **Run from an isolated copy / local
        Cloud Shell only — never push regen `IO_CONFIG`/`COL_MAPPING`
        edits to the Dataform notebook** (the daily scheduler runs it).
      - **2.7.2** Fix the column-name mismatch: `Raw Dump` has
        `"Case_History "` (underscore); `COL_MAPPING['case_history']`
        expects `"Case History "` (space). Override for regen or TTR/Reopen
        timeline reasoning silently degrades. (`Vector_Body` absent but
        safe — only read inside a JSON transcript.)
      - **2.7.3** Repoint evaluator `DUMP_BOT_SHEET="RCA_regen_test"`, run
        `--match-labels`, compare to 12.93%.
      - **2.7.4 Control run:** validate the harness with *current* prompts
        first — it should reproduce ~12.9% on the same cases, proving it
        faithfully mirrors the production bot. Only then is a post-Phase-4
        delta attributable. Ref: memory `project_regen_path.md`.

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

- [ ] **4.1 Reopen** — add L1 "Product Gap" + its L2/L3 children to
      `prompts/reopen/*.md` and to `HIERARCHY_CONFIG` in
      `notebook/content.ipynb` cell 4.
- [ ] **4.2 All RCAs** — add L3 "Quarter freeze / planning" under
      "Process Gap" in Reopen / TTR / Escalation / DSAT.
- [ ] **4.3 KSI auto-close rule** — Known-Issue Suspensions with future
      resolution dates auto-close. Encode in TTR + Reopen prompts so
      these cases stop polluting metrics.
      Ref: `evaluator/prompts/judge.md` already mirrors this rule;
      `docs/open-questions.md` #2 (code vs prompt placement for Zaidul);
      `docs/architecture.md` → Per-case processing (where
      `prepare_reopen_input` lives).
- [ ] **4.4 Enumerated additions across TTR / Reopen / DSAT / Escalation**
      from the live session (pending — `docs/connect-2026-05-14.md`).
      Ref: `docs/open-questions.md` #1.
- [ ] **4.5 Quality consolidation shape** (5-agent → fewer) — accepted by
      Zaidul May 14 provided the output still enumerates each metric.
      Ref: `docs/open-questions.md` #3.
- [ ] **4.6 `python3 scripts/inject_prompts.py`** after each batch of
      edits to fold prompts/ back into the notebook.
      Ref: `CLAUDE.md` → Common commands & Conventions.

---

## Phase 5 — Iterate to 80 % (the main one)

CLAUDE.md objective #1. The loop runs until accuracy clears 80 % per
framework on the 200-case sample.

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
