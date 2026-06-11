# Session / KT note — 2026-06-05 (fix-v2 + 5×120 A/B + 3.1-pro staging)

Continuation of `docs/session-2026-06-05.md`. Theme: **the aggregator was the
bug, and the model is the lever.** Built aggregator fix-v2, measured it cleanly
at N=5×120 on Gemini 3.1-pro, standardized the harness on 3.1-pro, and staged
(but did **not** push) the prod model switch. Demo gate unchanged: 80% by
2026-06-15. **Nothing pushed to prod** — accuracy is still low (~22% overall);
Sai will get it reviewed before any push.

## 1. Aggregator fix-v2 (`prompts/hierarchy/agent4.md`)
fix-v1 (a sub-agent intent gate) failed because the shared agent4 aggregator
overrode it. fix-v2 lives **in agent4**: a **Root-Cause Attribution Gate** added
*before* the old priority hierarchy. It classifies each finding as USER-SIDE /
EXTERNAL-SIDE (process/product) / AGENT-SIDE (People Gap), and forces the Primary
driver to come from a user/external cause when one is present, **unless** there's
clear independent agent failure (seller supplied everything, no freeze/bug/
approval, yet the agent still erred). The old Category ranking is demoted to a
tie-breaker *within* the winning class. The Reopen "Thank you email" override is
kept. Shared file → also reaches TTR (A/B confirms no regression). Injected via
`scripts/inject_prompts.py`; round-trip verified.

## 2. The result — fix-v2 is a statistically clean win
N=5×120, both branches Gemini **3.1-pro** (global), same 149 audited cases,
temp 0, matcher = regional 2.5-pro. Mean ± 95% CI:

| Framework | CTRL31 (no fix) | V2_31 (fix-v2) | Δ | CI separated |
|---|---|---|---|---|
| TTR | 24.6% ±6.4 | 29.0% ±2.5 | +4.4 | overlap (no regression) |
| Reopen | 8.5% ±1.3 | 15.9% ±2.6 | +7.4 | ✅ |
| Escalation | 7.4% ±3.6 | 21.1% ±4.6 | +13.7 | ✅ |
| DSAT | 0.0% ±0.0 | 11.4% ±7.9 | +11.4 | ✅ |
| **OVERALL** | **15.4% ±2.5** | **22.4% ±2.0** | **+7.0pp** | ✅ |

Exactly the predicted pattern: the three over-blame frameworks (Reopen/Esc/DSAT)
jumped with non-overlapping CIs; TTR (not broken) held. Checkpoints:
`evaluator/runs/ab_CTRL31_2026-06-05T08-26-21Z.json`,
`ab_V2_31_2026-06-05T10-25-56Z.json`. **Caveat:** A/B runs `--no-cache` (KB docs
403 to personal/`@google.com` accounts), so absolutes sit below frozen-prod-with-
cache — the **delta** is the signal; the quotable absolute baseline stays ~12.9%.

## 3. Harness changes (`evaluator/ab_measure.py`, `regen.py`)
- **3.1-pro is now the default bot model** (`--model` default), auto-routing to
  the global endpoint. Matcher stays regional **2.5-pro** (calibrated). To get a
  2.5 baseline, pass `--model gemini-2.5-pro --force-global`.
- **`ab_measure` now reports OVERALL** (case-weighted Σcorrect/Σaudited) and
  per-framework audited `n`, alongside per-fw mean ± CI.
- **Per-run checkpointing + `--resume-file`**: each run is written to the JSON as
  it completes; relaunch with `--resume-file <ckpt>` to continue from the last
  completed run. Built for Cloud Shell (see §6).

## 4. Max concurrency (empirical)
No code cap (env vars `REGEN_CONCURRENCY` / `MATCH_CONCURRENCY`). Project QPM
limits are not readable from these accounts (org-managed). Observed: conc 12 and
24 both ran with **n stable at 149** every run; at 24 a *few* `429
RESOURCE_EXHAUSTED` appeared but were absorbed by the pipeline's 4× retries
(0 cases dropped). **3.1-pro-preview is a preview model → its global QPM is the
tighter constraint, not generous.** Practical: bot ≤~24–32, matcher ≤24; find the
real knee by watching audited `n` / 429s, then back off ~20%. Also saw transient
`Temporary failure in name resolution` (Cloud Shell DNS blips) that once crashed
a run mid-way — resume recovered it losslessly.

## 5. Prod 3.1-pro switch — STAGED, NOT PUSHED
`notebook/content.ipynb` switched to 3.1-pro via an **additive, gated** block
appended to cell 8 (the `ModelRegistry` / `SharedKnowledgeBase` cell):
- Runs **only when** `agent_model.startswith("gemini-3")`; for 2.5-pro the
  regional `vertexai` path is byte-for-byte unchanged → **rollback = set
  `agent_model` back to 2.5-pro** (config-only).
- Installs a google-genai global client (lazy), rebinds `ModelRegistry.get_model`
  to a `.generate_content_async(prompt).text` adapter, and rebinds
  `SharedKnowledgeBase.create_agent_caches` to **google-genai caching**
  (`caches.create` + `cached_content`), with an **inline-KB fallback** if caching
  fails (job degrades, doesn't crash).
- **Added `google-genai` to the notebook pip-install** (cell 1) — without it the
  runtime would crash on `from google import genai`. (Caught during testing.)

Validated locally: notebook is valid JSON; `load_pipeline` execs; regen smoke
emits valid driver JSON through the **prod** global path; genai caching mechanics
(create + generate-with-cache + delete) confirmed on global 3.1-pro with a dummy
doc. **Untestable locally** (need the runtime SA): real-KB read (403 to us) and
the runtime SA's `cachedContents` permission — both low-risk (the regional cache
already works in prod today; inline fallback covers a caching failure). A manual
Colab execution tests the **Dataform** version, so it only helps *after* a push —
hence deferred to Sai's reviewed push.

## 6. Cloud Shell run management
Cloud Shell reclaims the VM on ~20-min idle (kills processes) but **`$HOME`
persists** (repo + checkpoints survive). So: launch with `setsid` (survives tab
close), checkpoint per run, and **`--resume-file` on reconnect** = lossless. On
reconnect, just relaunch the remaining runs. Used this twice today (CTRL31 after a
terminal restart; V2_31 after a DNS crash at run 5).

## 7. 6-driver (Quality + Workflow) — scoped, deferred
The gold sheet has `Quality` (142 rows) + `Workflow & Compliance` (2,683) tabs;
bot output cols exist too. Scoring them is a build (different schema +
multi-label/error-detection metric + calibration), orthogonal to fix-v2. Full
spec: `docs/quality-workflow-gold-scoping-2026-06-05.md`; memory
`project_quality_workflow_gold`. Next priority after this round.

## 8. State of the tree (nothing pushed)
- `prompts/hierarchy/agent4.md` — fix-v2. `prompts/{reopen,dsat,escalation,ttr}` —
  driver diffs (from prior session). `notebook/content.ipynb` — 3.1-pro + fix-v2
  + global path + genai pip (local mirror ahead of Dataform; **review before
  push**). `evaluator/ab_measure.py` + `regen.py` — 3.1-pro default, OVERALL,
  resume. New checkpoints + `docs/quality-workflow-gold-scoping-2026-06-05.md`.

## 9. Errors hit → solutions (this session)

| # | Symptom | Root cause | Fix / takeaway |
|---|---|---|---|
| 1 | Background launcher "completed" instantly; watcher fired early | Double-backgrounding (`run_in_background` **and** `nohup &`) detached the job from tracking | Launch long jobs with **`setsid nohup … & disown`**; track by **pid** / checkpoint, not the launcher |
| 2 | Terminal restart killed CTRL31 (only run 1 survived) | Cloud Shell reclaims the VM on disconnect → processes die | Cloud Shell **`$HOME` persists**; built **`ab_measure --resume-file`** (per-run checkpoint) → relaunch continues losslessly |
| 3 | `Temporary failure in name resolution` on Agent-4 calls | Transient **Cloud Shell DNS blips** (not quota/auth) | 4× pipeline retries absorbed them (n stayed 149); when a flood crashed V2 run 5, **verified DNS recovered then `--resume-file`'d** the last run at lower conc |
| 4 | `429 RESOURCE_EXHAUSTED` at conc 24 | **3.1-pro-preview** global QPM is the tight constraint (preview models get less) | Retries absorbed all (0 cases dropped, n=149). **Empirical ceiling: bot ≤~24–32, matcher ≤24**; watch audited `n` / 429s, back off ~20% |
| 5 | Couldn't see header/concurrency log lines mid-run | Python **block-buffers stdout** to a file; only `flush=True` lines (`run k/5`) appear live | Expected; rely on the checkpoint JSON + the flushed run lines for monitoring |
| 6 | Can't read KB docs locally (SOP/T&C/Plan = 403) | KB Google Docs are shared **only to the runtime SA**, not personal/`@google.com` | A/B runs `--no-cache` (delta, not absolute); validated genai **caching mechanics with a dummy doc** instead — real-KB caching only testable post-push |
| 7 | Would the prod switch crash the runtime? | Notebook pip-install was missing **`google-genai`**; `from google import genai` in the new block would `ImportError` | **Added `google-genai` to the cell-1 pip line.** Also made the global block **gated** + lazy, with an **inline-KB fallback** if caching fails (degrade, don't crash) |
| 8 | Can't end-to-end test the prod switch without pushing | A **manual Colab execution runs the Dataform version**, not local edits → chicken-and-egg | Validated everything testable locally (load_pipeline, regen smoke through the prod path, caching mechanics); the real-runtime test is deferred to **after** Sai's reviewed push |

## 10. Findings
- **fix-v2 is the right fix and it's clean** (§2): +7.0pp OVERALL with separated
  CIs; the 3 over-blame frameworks moved, TTR didn't regress.
- **3.1-pro is the bigger lever** (prior: +21.5pp TTR vs 2.5-pro) and is **non-
  deterministic at temp 0** → 3.x A/Bs need N-run CIs (2.5 doesn't).
- **Only 4 of 6 frameworks are scorable today** — gold + the agent4 path exist
  only for TTR/Reopen/Escalation/DSAT. Quality/Workflow gold **does exist** but
  needs a new loader + multi-label/error-detection metric + calibration (§7).
- **n is the trust signal**: it held at 149 across all 10 runs despite DNS/429
  noise → the denominators (and therefore the deltas) are trustworthy.

## 11. Next steps
1. **Get the staged 3.1-pro + fix-v2 reviewed** (Zaidul, per the prompt-review
   convention) → `scripts/push_notebook.sh`. Pair the push with a **manual Colab
   execution** to validate real-KB genai caching + runtime-SA `cachedContents`
   permission on the actual runtime; keep rollback ready (set `agent_model`→2.5).
2. **Build the 6-driver (Quality + Workflow) scoring** —
   `docs/quality-workflow-gold-scoping-2026-06-05.md` (loaders + detection metric
   + calibration). Next priority after the push.
3. **Keep closing the gap to 80%** — 22.4% is still far short; next levers after
   fix-v2 land: sub-agent precision on the recovered User-Gap cases, and whether
   real-KB caching (post-push) lifts absolutes.

### Open questions for Zaidul
- Workflow `Error Status` semantics (`Yes`=2031 ≠ the ~166 dimension errors).
- Include Workflow's **May'26** rows? (driver tab stops at April; is workflow
  taxonomy stable across the March cutover?)
- Quality severity weighting (Critical vs Non-critical); the near-empty compliance
  sub-dimension; comma-joined multi-L1 gold labels; blank `quality_reviewer`.
