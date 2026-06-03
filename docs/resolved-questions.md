# Resolved questions (archive)

Archive of questions raised during the Apr 29 KT call and May 12 mapping
that were answered on the **2026-05-14 Connect**. Kept so future sessions
can see the *why* behind current beliefs, not just the conclusions.

Active items live in [`open-questions.md`](open-questions.md). Connect-call
detail lives in [`connect-2026-05-14.md`](connect-2026-05-14.md).

## Resolved on 2026-05-14

| # | Question | Answer |
|---|---|---|
| 1 | New L3 driver under Process Gap? | Yes — **"Quarter freeze / planning"** added across **all** RCA workflows. Plus **Reopen** gets a new L1 **"Product Gap"** and a **KSI auto-close** processing rule. Encoding into prompts is Sai's main action item. |
| 2 | Quality 5 agents intentional? | Yes today — the five are **Accuracy / Completeness / Relevance / Communication / Responsiveness**. Zaidul is **open to consolidating** into fewer (even a single) agent provided the output enumerates each metric with explicit pass/fail and "no error" for the rest. |
| 3 | `use_cache: True` — what is being cached? | **Vertex Context Caching** of the static SOP / rule corpus. Goal: cut tokens, speed up runtime, prevent hallucinations. It is the substitute for a frozen regression set. |
| 4 | Pass/Fail threshold semantics | **`score ≥ 90 ⇒ Pass`, `< 90 ⇒ Fail`**, scored at **case level**. Today only `Quality_RCA_Output` contributes to the score, by design. |
| 5 | Frozen 200-case regression set? | Not the validation mechanism today — Context Caching plays that role in production. A labelled gold set for **prompt A/B testing** is still worth maintaining (see active question in `open-questions.md`). |
| 8 | Tricks → BigQuery trigger | Migration is **active**, not gated on compliance. Pooja sending SQL Miner + Colab paths (similar to past Voice-of-Seller work). |
| 10 | Dashboard contract | **Dashboarding parked** — re-engages downstream when accuracy work concludes. Preserve `OUTPUT_COLS_TO_SAVE` so the contract holds. |
| 11 | Hardcoded OAuth token | Confirmed temporary (Rishita's workaround). **Sai to generate his own short-lived token** immediately to avoid expiry. Service-account migration is the longer-term fix. |
| 12 | Accuracy metric definition | **Case-level: Correct Cases ÷ Total Audited.** Primary driver match is the main check; secondary driver is the tiebreaker / supporting signal. |
| 13 | No version control on the notebook | **Sai to set up git** for `prompts/` (probably `notebook/` + `docs/` too). Hosting venue TBD — tracked as an active question. |

## Resolved on 2026-05-29 (catch-up — `connect-2026-05-29.md`)

| # | Question | Answer |
|---|---|---|
| 14 | Full enumerated driver diff | Read from the Voice-of-Seller sheet. Canonical, and it **corrects the May-14 / catch-up summaries**: the new L1 is a **single combined "Product/Tools Gap"** (not separate Product Gap + Tool Gap), present across **TTR/Reopen/DSAT/Escalation** (not Reopen-only); the new L3 is **"Quarter Freeze / YoY Planning & Implementation"** (not "YI Planning") under Process Gap → Workflow Complexities. L2s under Product/Tools Gap: Product Limitation, Product Bugs. Recorded in `docs/frameworks.md`; encoding into `HIERARCHY_CONFIG`/`prompts/` is still pending (Phase 4). |
| 15 | Gold / regression-set source | The **QA dump sheet** `1tbrQ…` (previously mis-documented as "legacy") holds thousands of human-reviewer L1/L2/L3 labels + bot predictions. Evaluator now **label-matches** against it (`evaluator/runner.py --match-labels`). Replaces the manual ~30-row curation. |
| 16 | Exact demo date | **2026-06-15** is the firm deadline (was "3rd week of June, confirm exact"). |
| 17 | BigQuery migration | Confirmed **work item to implement** (Tricks → BigQuery), no longer gated on a question / on Pooja's SQL Miner + Colab links. Sequenced as execution, not an open question. |
| 18 | Git hosting venue | **Not needed** — Sai is the only person working on the repo, so version-control hosting is dropped (no git-init, no venue decision). |
