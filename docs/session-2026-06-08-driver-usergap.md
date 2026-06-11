# Session 2026-06-08 — driver error profile + User-Gap lever (NULL result)

KT note. After Stage 2 (Workflow hygiene grounding, task 4.7, +6.9pp F1), we asked
whether the **drivers** could move in the same phase. They did **not** — but the
investigation produced the single most useful driver diagnosis we have. This note records
it so the next person doesn't re-run the same null experiment.

## The diagnosis — User Gap is the driver error budget

Gold primary-L1 composition (QA-2026, Mar–Apr), model-independent:

| Framework | User Gap | Process Gap | Product/Tools | People Gap |
|---|---|---|---|---|
| TTR | **41.2%** | 30.1% | 22.9% | 4.8% |
| Reopen | **61.8%** | 10.9% | (0.3%) | 8.3% (+ Invalid Reopen 17.9%) |
| Escalation | **67.8%** | 19.0% | 7.1% | 5.7% |
| DSAT | 39.6% | **43.4%** | 1.9% | 15.1% |

**User Gap is the plurality/majority gold L1 in 3 of 4 driver frameworks** — yet the bot
almost never emits it as primary. Bot confusion on gold-User-Gap cases (3.1-pro regen):

| Framework | gold=User Gap | bot got User Gap | bot said instead |
|---|---|---|---|
| TTR | 57% of cases | **5%** (1/20) | Process 45%, People 40% |
| Reopen | 63–75% | **27%** (16/60) | **Process 55%**, People 13% |

The bot defaults to **Process Gap / People Gap** (agent/process blame) when gold says the
**user** originated it. This is the dominant driver miss and it is **cross-framework**.

### Why — the pipeline structure
For Reopen the three sub-agents are: agent1 (Triage), **agent2 = "Soft-Skill Failure" →
People Gap**, **agent3 = "Process Root Cause" → Process Gap**. Two of three auditors are
hardwired to agent/process blame; only agent1 can surface User Gap. And `reopen/agent1`
had **no User-Gap rule** — the dominant gold driver *"Additional or different Query"* (user
reopened with a new question) = **49% of all Reopen gold** had no path to be emitted; rule 2
literally said *"IGNORE IF the message asks a question or provides new info."*

## The lever we tried — and it did NOT work

Two prompt edits (reverted after measuring; Stage 1/2 untouched):
1. **`reopen/agent1`** — added a PRIORITY-2 "Additional or different Query" (New Query) rule.
2. **`hierarchy/agent4`** — added gate clause 2b: when BOTH a USER-SIDE and EXTERNAL-SIDE
   finding are present, prefer the **user-side** (it names what *originated* the reopen).

Same-cases OLD-vs-NEW regen (3.1-pro, temp 0, n≈95 joined, Reopen):

| Config | User-Gap recall (L1) | **Reopen accuracy (matcher)** |
|---|---|---|
| OLD (Stage-1) | 27% (16/60) | **17.9%** (17/95) |
| + agent1 New Query | 23% (14/60) | — |
| + agent1 **and** agent4 2b | 33% (20/60) | **16.0%** (15/94) |

**Verdict: NULL.** The deterministic User-Gap recall nudged +6pp, but it did **not** convert
to matcher accuracy (17.9→16.0, within single-run noise). Even when explicitly instructed,
the bot emitted "Additional or different Query" only ~13/150 (gold wants ~49%) — **the model
resists reclassifying these reopens as User Gap**; it reads them as Process/Responsiveness.

## What this means (two honest implications)

1. **Drivers don't yield to prompt nudges.** This re-confirms the 2026-06-04 directional
   finding ("prompt diff ≈0; the model was the lever"). Stage 1's 3.1-pro swap + fix-v2 was
   the driver lever (12.9→22.4%); there is no easy prompt follow-up. Further driver gains
   likely need a **stronger mechanism** (e.g. deterministic re-attribution in code, like the
   hygiene fix) or a **different model**, not sub-agent wording.
2. **The label is correct (ZAIDUL CONFIRMED 2026-06-08) → the fix is CODE, not prompt.** We
   asked directly: when a closed case is reopened because the seller raises a *new/different*
   query, is the primary driver **User Gap (New Query)** or the agent's miss? **Zaidul: it IS
   User Gap (New Query) — the gold is right, the model is wrong.** So this is **not** a label
   ambiguity to relabel, and **not** something prompts can fix (the model resists). The
   confirmed path is a **deterministic User-Gap re-attribution in code** — same pattern as the
   task-4.7 hygiene grounding: detect the new-query-reopen condition deterministically (a
   reopen trigger that introduces a new/different request beyond the original resolved issue)
   and emit `User Gap | New Query | Additional or different Query` directly, bypassing the
   model's reluctance. **This is the next real driver lever** (Zaidul-backed, not a hypothesis);
   build it, then measure with `ab_measure` N-run CIs.

## Re-attribution build — MEASURED, marginal, REVERTED (2026-06-08)

After Zaidul confirmed the label, we built the deterministic re-attribution (the task-4.7
pattern): re-added the `reopen/agent1` New-Query *surfacing* rule + a **hard cell-9 code
override** (`reattribute_new_query`) that promotes a surfaced "Additional or different Query"
finding to **Primary**, bypassing agent4's demotion. Clean same-session `ab_measure`
(3.1-pro, 3×120 Reopen):

| Config | runs | mean ± 95% CI |
|---|---|---|
| OLD (Stage-1) | 20.8 / 20.8 / 18.3 | **20.0% ± 3.6** |
| NEW (re-attribution + agent1 rule) | 20.0 / 22.5 / 25.0 | **22.5% ± 6.2** |

**Δ = +2.5pp, CIs overlap → fails the +5pp gate → REVERTED.** The hard override *did* beat the
prompt-only null (which was ~0), confirming agent4 demotion is *part* of the blocker — but the
gain is capped by the **surfacing wall**: agent1 emits New Query on too few cases (~13/150), so
force-promoting it only nudges the number. **The real fix is a dedicated, unconflicted detector**
(a focused "is this reopen a new user query?" classifier or a deterministic data signal), not a
bigger override on the cluttered triage agent. That is the Phase-3 driver lever.

## Status
- Driver prompt + override edits **reverted** (`reopen/agent1.md`, `hierarchy/agent4.md`, cell-9
  back to Stage-1; re-injected). Stage 1 + Stage 2 (Workflow hygiene) + the TTR `>=7` gate fix
  untouched/kept.
- **Zaidul confirmed 2026-06-08:** reopen-with-new-query **IS** User Gap (New Query). The
  prompt + hard-override both measured (~0 and +2.5pp/overlap) → **Phase-3 = a dedicated New-Query
  detector.** Tracked in `docs/execution-plan.md` Phase 5.1, `docs/open-questions.md` (RESOLVED
  #2), memory `project_driver_usergap_ceiling`.
- Artifacts: `evaluator/runs/reopen_{OLD,NEW,NEW2}.csv`, verdict CSVs
  `runs/2026-06-08T11-1*.csv`. Error-profile method is reusable for TTR/Escalation/DSAT.
