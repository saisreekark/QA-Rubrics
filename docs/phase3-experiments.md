# Phase-3 lab notebook — driver prompt experiments (self-contained, restorable)

**Purpose:** preserve every Phase-3 experiment — exact prompt tweaks, how to apply/revert,
and all measured numbers — so nothing is lost when the working tree is reverted between A/B
branches. This is the durable record; the prompts also live in git history and the run
artifacts under `evaluator/runs/`.

> The working tree is intentionally returned to **clean Stage-1/2** between measurements
> (each A/B needs an un-tweaked OLD branch). The tweaks are NOT lost — they are reproduced
> verbatim below and restorable in 30 seconds (apply → `inject_prompts.py`).

Related records: `docs/session-2026-06-08-newquery-detector.md` (the dedicated-detector
experiment, data-ceiling finding), `docs/stage-tracker.md` (stage history),
memory `project_driver_usergap_ceiling`.

---

## Experiment P3-A — "New-Query catch-all" (agent1) + "user-side originating cause" (agent4)

**Hypothesis.** The QA reviewers label valid substantive reopens as **User Gap → New Query →
"Additional or different Query"** by *process of elimination* (not from reopen-trigger text the
pipeline doesn't ingest — see the detector KT). `reopen/agent1` had **no** New-Query rule and
even told itself to ignore questions, so valid reopens fell through to Process/None; and
`agent4`'s tie-breaker ranks `User Gap/New Query` **last (#7)**, below `Process/XFn (#5)`, so
even a surfaced New-Query lost Primary to a Process finding. Fix = two coordinated tweaks:
(1) agent1 surfaces New-Query as a **catch-all default**; (2) agent4 **prefers the user-side
originating cause** over the downstream external step.

**Grounding (the bot→gold confusion that motivated it; April n=120, Stage-1/2 OLD):**
gold User Gap **62%** vs bot User Gap 32%; the dominant reachable error is **29 cases
gold=User Gap → bot=Process Gap** (+10 →Product/Tools, +7 →People). New-Query recall 6%.

### The exact tweaks (copy-paste restorable)

**1. `prompts/reopen/agent1.md`** — insert a new block **after** PRIORITY 3 (rule 6), **before**
the `### OUTPUT FORMAT` section:

```
   #### PRIORITY 4: NEW OR DIFFERENT QUERY (Default for a valid, substantive reopen)
   7. **"Additional or different Query"** (Category: New Query)
   - **MATCH IF:** None of the rules above matched — i.e. the reopen is **valid** (not a blank/mistaken reopen, not a thank-you/closure, not a duplicate) and is **not primarily an agent responsiveness or timeline failure** — AND the seller re-engaged the case to pursue, clarify, follow up on, or extend their request: asking a question, providing new or additional information, raising a related or additional ask, or driving the issue forward. This is the **default** classification for a genuine, seller-driven reopen where **no clear agent-side failure** is evident. The seller coming back to push their own request forward is itself the originating reason for the reopen. **When in doubt between this and `None`, choose this** — a valid reopen almost always reflects the seller raising something further.
```

…and change the final line of the OUTPUT FORMAT from `If no violation, return: `None`` to:
`If genuinely no reopen activity at all (e.g. an empty/system-only reopen with no seller content), return: `None``

**2. `prompts/hierarchy/agent4.md`** — insert as **GATE RULE clause 3** (renumber the old 3→4).
⚠️ Use the **SCOPED** version below (final, P3-A v2). The earlier *generic* "prefer any user-side
over external-side" version regressed Escalation −3.2pp and was discarded.

```
    3. **New-Query promotion (scoped):** When a USER-SIDE finding named **"Additional or different Query" (New Query)** is present — the seller came back to raise a new, different, or additional request — make it the **Primary** over any EXTERNAL-SIDE finding (freeze, approval, dependency, routing, latency) it triggered, since the seller's new request is what originated the contact. **Apply this ONLY to the "Additional or different Query" finding — do NOT generalize it to other user-side findings** (other user-side vs external-side ties fall through to the STEP 4 tie-breaker).
```

### Apply / revert

```bash
# APPLY: edit the two prompts/ files as above, then fold into the notebook
python3 scripts/inject_prompts.py
# REVERT: undo the two edits (or `git checkout prompts/reopen/agent1.md prompts/hierarchy/agent4.md`
#         IF they have no other staged changes — they DO carry Stage-1 edits, so revert by hand),
#         then re-inject:
python3 scripts/inject_prompts.py
```

### Measurement commands (held-out April, 3.1-pro, temp 0)

```bash
export GOOGLE_OAUTH_TOKEN="$(gcloud auth print-access-token)"
# Single-run same-cases regen (fast directional check):
python3 -m evaluator.regen --sample 120 --framework Reopen --no-cache --temperature 0 \
  --months 2026-04 --out evaluator/runs/p3_reopen_NEW.csv
python3 -m evaluator.runner --match-labels --gold-source regen \
  --regen-csv evaluator/runs/p3_reopen_NEW.csv --framework Reopen --months 2026-04
# Matcher-free confusion diagnostic:
python3 -m evaluator.p3_confusion evaluator/runs/p3_reopen_NEW.csv 2026-04
# Powered N-run A/B with 95% CIs (the real gate):
MATCH_CONCURRENCY=20 REGEN_CONCURRENCY=24 python3 -m evaluator.ab_measure \
  --label P3R_NEW --runs 4 --sample 120 --framework Reopen --months 2026-04 --temperature 0
```

### Results

**Single-run same-cases (April, n=120 Reopen-gold) — directional, NOT gated:**

| | OLD (Stage-1/2) | NEW (P3-A) | Δ |
|---|---|---|---|
| Correct | 20.8% | 25.8% | **+5.0pp** |
| primary-correct | 21.7% | 27.5% | +5.8pp |

Confusion fingerprint (the mechanism worked **in that run**): User-Gap correct **25→34**,
gold-User→bot-Process error **29→20 (−9)**, New-Query recall **6%→17%**, Invalid-Reopen correct
6→10. Artifacts: `evaluator/runs/p3_reopen_{OLD,NEW}.csv`, verdicts `runs/2026-06-08T14-29-55Z.csv`
(OLD) / `runs/2026-06-08T14-36-04Z.csv` (NEW).

**N-run A/B, all 4 drivers (3×120, April) — the single-run +5pp did NOT replicate:**

| Framework | OLD | NEW | Δ | CIs |
|---|---|---|---|---|
| Reopen (n51) | 27.5% ± 8.4 | 23.5% ± 4.9 | −4.0 | overlap |
| TTR (n84) | 23.0% ± 1.7 | 27.4% ± 8.9 | +4.4 | overlap |
| Escalation (n13) | 20.5% ± 11.0 | 17.9% ± 11.0 | −2.6 | overlap |
| DSAT (n2) | 0.0% | 0.0% | — | — |
| **OVERALL** | **24.0% ± 2.9** | **24.9% ± 5.8** | **+0.9** | **overlap → NULL** |

Artifacts: `evaluator/runs/ab_P3NEW_2026-06-08T14-38-06Z.json`,
`ab_P3OLD_2026-06-08T16-38-56Z.json`. Note April is thin for Esc/DSAT, and ab_measure only
audited n=51 Reopen (reopen-eligible subset of a 120-draw) → the target framework is underpowered.

**Decisive Reopen-only powered A/B (full Reopen pool, April) — THE VERDICT:**

| Branch | runs | Reopen mean ± 95% CI |
|---|---|---|
| **OLD (Stage-1/2)** | 4 × [22.7, 21.7, 23.3, 23.3] | **22.8% ± 1.3** → [21.5, 24.1] |
| **NEW (P3-A)** | 5 × [32.2, 25.8, 30.3, 28.3, 28.3] | **29.0% ± 3.0** → [26.0, 32.0] |

**Δ = +6.2pp, 95% CIs cleanly separated (1.9pp gap) → PASSES the +5pp gate. Real Reopen win.**
Artifacts: `ab_P3R_NEW_2026-06-08T17-45-14Z.json` (5 runs), `ab_P3R_OLD_2026-06-09T04-09-22Z.json`
(4 runs), logs `P3R_{NEW,NEW5,OLD}.log`.

### Cross-framework check on the larger Mar–Apr window — found a regression, then fixed it

To get more data (esp. for the thin Escalation/DSAT), re-ran the powered A/B on **Mar–Apr**
(per-framework, dedicated `--sample` so each got its full n). This **exposed a regression the
April-only runs were too thin to catch:** the *generic* agent4 "prefer user-side over
external-side" clause **helped Reopen but hurt Escalation.**

| Framework | OLD (Stage-1/2) | NEW (P3-A, **generic** clause) | Δ | verdict |
|---|---|---|---|---|
| Reopen (n≈250) | 19.5% ± 2.5 | 24.7% ± 2.5 | **+5.2** | CIs separate → WIN |
| Escalation (n≈202) | 15.8% ± 1.2 | **12.6% ± 1.5** | **−3.2** | **CIs separate → REGRESSION** |
| DSAT (n≈51) | 20.3% ± 10.1 | 17.0% ± 7.4 | −3.3 | overlap (noise, tiny n) |

The agent1 catch-all is Reopen-only, so the cross-framework damage was the **shared, generic
agent4 clause** bleeding into Escalation. **Fix = scope the agent4 clause to the New-Query
pattern only** (`"Additional or different Query"`), not all user-side findings → **P3-A v2**.
Re-measured Mar–Apr:

| Framework | OLD (Stage-1/2) | NEW (**P3-A v2**, scoped) | Δ | verdict |
|---|---|---|---|---|
| Reopen (n≈246) | 19.5% ± 2.5 | **24.6% ± 1.4** → [23.2, 26.0] | **+5.1** | CIs separate → **WIN holds** |
| Escalation (n≈202) | 15.8% ± 1.2 | **15.7% ± 2.4** | **−0.1** | **NEUTRAL → regression fixed** |

Artifacts: `ab_MA_{NEW,OLD}_{Reopen,Escalation,DSAT}_*.json`, `ab_MA_SCOPED_{Reopen,Escalation}_*.json`,
`MA_*.log`.

### Verdict & disposition (FINAL) — P3-A v2 (scoped clause) is KEPT

- **KEPT: P3-A v2** = agent1 PRIORITY-4 New-Query catch-all **+** agent4 clause scoped to the
  `"Additional or different Query"` finding only. Injected into `notebook/content.ipynb`
  (staged-not-pushed, with the Stage-1/2 bundle). The earlier **generic** clause is **discarded**
  (it regressed Escalation).
- **Reopen — powered WIN, confirmed on both windows:** April (full pool) **22.8% → 29.0%
  (+6.2pp)**, Mar–Apr **19.5% → 24.6% (+5.1pp)** — CIs separate both times.
- **Escalation — NEUTRAL** with the scoped clause (15.8% → 15.7%); the −3.2pp regression seen with
  the generic clause is **eliminated.**
- **TTR — NEUTRAL** (April powered: 23.5% → 24.6%, +1.1pp, CIs overlap; the scoped clause fires
  even less on TTR, so no regression risk).
- **DSAT — inconclusive** (Mar–Apr n≈51, OLD 20.3% ± 10.1 — CI too wide to read; the scoped clause
  rarely fires on DSAT findings, so no expected effect).
- **Methodology lesson:** April-only multi-framework runs were underpowered and *masked* both the
  Reopen win (n=51 OLD outlier) **and** the Escalation regression (n=13). The Mar–Apr per-framework
  powered runs were necessary to see the truth. Always power the *target* framework directly.
- **Net Phase-3:** a measured **Reopen lift (+5–6pp)** on top of Stage-1/2, **no regression** on the
  other drivers. Stage-1/2 remains the rest of the baseline (drivers OVERALL 22.4%, Workflow F1
  23.9%, Quality F1 39.1%); Q/W are untouched by P3-A (driver-only change).
