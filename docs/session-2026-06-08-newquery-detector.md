# Session 2026-06-08 — Phase-3 New-Query detector (NULL result: a DATA ceiling, not a prompt/model one)

KT note. Phase 2 ended with one carried lever: a **dedicated, unconflicted New-Query
detector** for Reopen — the hypothesised real path off the 22.4% driver plateau. We built
it, measured it, and it does **not** work. But the measurement located the true cause of
the Reopen plateau, which is more valuable than the detector would have been. This note
records the build (fully recoverable) and the finding so the next person doesn't re-run it.

## Why we built it (the Phase-2 hypothesis)

User Gap is the driver error budget: gold's majority Reopen L1 is **User Gap → New Query →
"Additional or different Query" (~47–49% of Reopen gold)**, but the bot emits it ~9%. Phase 2
showed the cheap fixes fail (prompt edit ≈0; hard cell-9 override +2.5pp, CIs overlap). The
diagnosis blamed the **"surfacing wall"**: the `reopen/agent1` triage agent has 6 competing
priorities and rarely surfaces New Query (~13/150), and agent4 demotes it. The hypothesis:
a **focused single-purpose YES/NO classifier** ("is this reopen a new/different user query?")
whose verdict **deterministically force-emits** the driver as Primary (bypassing agent4) would
break the wall. Zaidul confirmed 2026-06-08 the label is correct (reopen-with-new-query **IS**
User Gap (New Query)), so this was framed as an engineering problem, not a relabel.

## What we built (recoverable — reverted from the notebook, preserved here)

The task-4.7 pattern (dedicated component + deterministic override), all gated, Stage 1/2
untouched:

1. **`prompts/reopen/newquery_detector.md`** → `REOPEN_NEWQUERY_DETECTOR_PROMPT` (bootstrapped
   into cell 5). A single-decision classifier: ignore agent behaviour/timing/process; answer
   **YES** iff the reopen trigger introduces a new/different/additional request beyond the
   original resolved issue; **NO** for blank/gratitude/duplicate/same-issue/info-provision.
   Explicit YES-leaning calibration and one-line `YES|… / NO|…` output.
2. **cell 9 `run_framework_pipeline`** (gated `NEWQUERY_DETECT`): for Reopen, run
   `detect_new_query(case_data, temp)` concurrently with the sub-agents; if YES,
   `apply_new_query_override(final_output, just)` force-sets Primary to
   `User Gap | New Query | Additional or different Query` (resolver-backed) and demotes the
   model's old primary to Secondary iff its L1 differs. Bypasses agent4 entirely.
3. `scripts/extract_prompts.py` made tolerant of non-`AGENT_N` prompt names (so the
   round-trip survives a `<FRAMEWORK>_<SLUG>_PROMPT`). Reverted with the rest.

Verified offline: pipeline loads, resolver returns the correct L1/L2/L3, override promotes/
demotes correctly. Verified live on 3.1-pro: detector fires end-to-end.

## The measurement — the detector inherits the SAME reluctance (held-out April, 3.1-pro, temp 0)

Rather than burn a full N-run accuracy A/B, we measured the detector's behaviour directly
against gold on n=60 held-out Reopen cases — a cheaper, more *mechanistic* test:

| Metric | Value |
|---|---|
| Detector **YES rate** | **5%** (3/60) |
| Gold New-Query rate | 47% (28/60) |
| Gold User-Gap rate (any L3) | 68% (41/60) |
| Detector vs gold New-Query | TP=2 FP=1 FN=26 → **precision 67%, recall 7%** |

When it fires, it's right (precision 67%). It almost never fires (**recall 7%**) — i.e. the
*same* ~9% surfacing rate as the cluttered triage agent. **A dedicated, unconflicted,
YES-leaning, temp-0 classifier does NOT break the surfacing wall.** A full A/B would only
confirm ≈0 driver-accuracy change (CIs overlapping), at high cost, because the dominant gold
class is unreadable — so we did not run it.

## Why — the wall is a DATA-INSTRUMENTATION ceiling, not prompts or the model

Tracing the false-negatives revealed the root cause:

1. **The reopen-phase marker doesn't exist in the input.** Every Reopen prompt (and the
   detector) instructs: *"find the last `<<< SYSTEM LOG: CASE CLOSED … >>>` marker, analyse the
   text AFTER it."* The constructed input contains **no such marker** (`'CASE CLOSED'` count = 0,
   `'>>>'` count = 0). There is nothing delimiting the original issue from the reopen.
2. **The reopen-trigger message isn't separably in the transcript.** Splitting the transcript
   at the metadata `Reopen Date` recovers a post-reopen message for only **3 of 28** gold
   New-Query cases. For 25/28 the reopen occurs **within seconds of closure** (e.g. 69967285:
   Closed 12:43:16 → Reopen 12:43:18) with the last actual seller message days earlier — there
   is **no distinct new-query message** in the data.
3. **No reopen-reason field exists.** Input columns carry `Reopen_Counter` but **no**
   `Reopen_Reason` / reopen-comment / reopen-trigger field. `Case_History` is tiny (404–1063
   chars) and the same-day content on the reopen date is the closing exchange, not a new ask.

So the human reviewer labelled "Additional or different Query" from a source the pipeline
**does not ingest** (the case-management reopen reason / a richer view). The signal needed to
classify the dominant Reopen driver is **absent from the pipeline input for ~90% of these
cases.** No prompt, no detector, no model swap, and no deterministic code split can extract a
signal that isn't there. This conclusively explains every prior null: the model's ~9% emission,
the prompt nudge ≈0, the override +2.5pp, and now the dedicated detector's 7% recall — all the
same ceiling.

## Implications / what the real lever is

- **Drivers stay at Stage-1 22.4%.** The New-Query detector is reverted; Stage 1 + Stage 2
  (Workflow hygiene grounding, TTR `>=7`) untouched.
- **The Reopen plateau is largely structural.** ~47% of Reopen gold is the New-Query class,
  which is **unreachable** until the reopen-trigger content is ingested into the pipeline input.
  This caps Reopen accuracy regardless of prompt/model work at the agent layer.
- **The real Phase-3 lever moves UPSTREAM, to data ingestion** (not prompts): add the
  **reopen reason / first post-reopen seller message** to the input the pipeline reads — a
  query/schema change on the data-load side (Vikram's input-load scheduler / the
  Tricks→BigQuery migration Pooja is scoping). Once that field lands, the detector built here
  becomes viable and can be restored from this doc verbatim.
- **Open question for Zaidul/data:** confirm which source field the QA reviewers read to assign
  "Additional or different Query," and whether it can be surfaced into `Cases for Summary`.

## Status
- Detector **reverted** from `notebook/content.ipynb` (cells 5 & 9 restored byte-for-byte to
  Stage-1/2: cell 9 = 10,956 chars, cell 5 = 85,743), `prompts/reopen/newquery_detector.md`
  removed, `scripts/extract_prompts.py` restored. Stage 2 hygiene grounding + fix-v2 + framework
  diff all intact. No `NEWQUERY` residue anywhere.
- Diagnostic scripts were one-off (`/tmp`); the numbers + the detector prompt/wiring above are
  the durable record. Method (detector-vs-gold confusion + timestamp-split recoverability) is
  reusable for TTR/Escalation/DSAT to check whether *their* dominant User-Gap L3s are likewise
  data-limited.
- Tracked in `docs/stage-tracker.md` (Phase-3 block), `docs/execution-plan.md` (Phase 5.1),
  memory [[project_driver_usergap_ceiling]].
