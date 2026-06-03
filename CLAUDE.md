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

1. **Lift case-level accuracy from ~50 % → ~80 %** —
   `Correct ÷ Total Audited`, primary driver weighted over secondary,
   pass threshold `score ≥ 90`.
2. **Encode the confirmed framework updates** in `prompts/` +
   `HIERARCHY_CONFIG` — new combined L1 **"Product/Tools Gap"** (L2s:
   Product Limitation, Product Bugs) and new L3 **"Quarter Freeze / YoY
   Planning & Implementation"** under Process Gap, both across
   TTR / Reopen / DSAT / Escalation. Canonical wording is in hand (read
   from the Voice-of-Seller sheet; see `docs/frameworks.md` and
   `docs/connect-2026-05-29.md`). Not yet encoded.
3. **Implement the KSI auto-close rule** so known-issue cases with future
   resolution dates stop polluting TTR / SLA metrics.
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
8. **Build the regen harness** (`docs/execution-plan.md` 2.7) — the
   label-match evaluator scores *frozen* dump predictions, so testing a
   prompt/driver change needs regenerated predictions. Inputs already
   live in the dump's `Raw Dump` tab. Validate with current prompts
   (should reproduce ~12.9%), then it measures the Phase-4 delta. Un-gated
   — can start now. Memory `project_regen_path.md`.
9. **Calibrate the judge** (2.6) before quoting 12.93% as an absolute —
   it's an unvalidated LLM matcher; hand-check ~30–50 verdicts.

## Current goal (as of 2026-05-15 — post May 14 Connect, see `docs/connect-2026-05-14.md`)

- **Push prompt accuracy → 80%** before client demo. **Anchor baseline
  (2026-05-29) is now the QA-2026 gold set** (recent cases, updated
  taxonomy): **driver-level 12.99%** (TTR 20.8 / Reopen 6.6 / Escalation
  7.8 / DSAT 7.9) and **error-detection 68.5%** under the "no People Gap =
  no error" rule. Reopen is the floor (un-encoded Product/Tools Gap).
  (The earlier 12.93% was vs the *old* dump/old taxonomy — superseded.)
- **Demo**: **2026-06-15** (firm deadline).
- **Full release**: July 2026.
- **Accuracy is measured per-case** (`Correct ÷ Total Audited`), with the
  *primary* driver weighted more than secondaries.
- **Pass threshold**: **score ≥ 90 = Pass**, **< 90 = Fail**.
- **Dashboarding is parked** — sole priority is prompt accuracy.
- **Tricks → BigQuery migration** moved from "parked" to **actively scoping**
  (Pooja sending SQL Miner / Colab paths).
- Pipeline architecture is otherwise frozen — no scheduler / model swaps.

## Where the code lives

| Surface | Location |
|---|---|
| Live notebook | Pantheon Colab → Dataform repo `1b4ad4ee-53ba-4541-9492-1dc89d100607` (us-central1, project `gtm-cloud-helpdesk`), file `content.ipynb` |
| Local mirror | `notebook/content.ipynb` |
| Prompts (18, split out) | `prompts/<framework>/agentN.md` |
| Scheduler | `rubrics-automation-run` (id `1105207098007879680`), daily 12:00 IST |
| Output bucket | `gs://analytics_genai` |
| I/O sheet | [`1Lmo5la…J94juM`](https://docs.google.com/spreadsheets/d/1Lmo5laSelj8Yp-ANjuZ_cQVnVM3W9XB6mNRt_J94juM) → input tab `Cases for Summary`, output tab `RCA_Analysis_Output_1` |

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
| [QA-2026 gold case set](https://docs.google.com/spreadsheets/d/1_MvXAMTIUcHS9ne9vJHnA_l9wviNW87mcmgNYnGkXlg) | **ADOPTED gold (2026-05-29).** Manual QA labels for recent (Jan–Apr 2026) cases in the *updated* taxonomy. Driver tab `DSAT/Reopen/Escalation/TTR` split by `Stage`; filter Feb/Mar 2026. Evaluator default (`--gold-source qa2026`); bot side joins from the live output tab. |
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
python3 -m evaluator.runner --match-labels --sample 2000              # label-match vs ADOPTED QA-2026 gold (Feb/Mar 2026, default --gold-source qa2026)
python3 -m evaluator.runner --match-labels --gold-source dump --sample 200   # legacy big dump
python3 -m evaluator.aggregate evaluator/runs/<latest>.csv

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

- `docs/connect-2026-05-14.md` — **latest** Connect call: decisions, new
  framework changes Sai must encode, action items
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
