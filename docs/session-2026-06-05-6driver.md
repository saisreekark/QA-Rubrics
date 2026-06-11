# Session / KT note — 2026-06-05 (6-driver: Quality + Workflow scoring)

Continuation of `docs/session-2026-06-05-fixv2-ab.md`. Theme: **the evaluator now
scores all 6 frameworks.** Built the loaders + a deterministic detection scorer +
wiring + calibration for **Quality** and **Workflow** — the two frameworks the
driver path couldn't touch (dynamic driver list, bypasses the agent4 aggregator,
multi-label / error-detection gold instead of a single Primary verdict). Spec
executed: `docs/quality-workflow-gold-scoping-2026-06-05.md`. Evaluator-only,
read-only on sheets, **nothing pushed to prod.**

## 1. What shipped (evaluator/)
- `config.py` — Quality/Workflow tabs, column maps, the 5-dimension→bot-L2 map,
  `MULTILABEL_FRAMEWORKS`, month-abbr parse (`"Mar'26"`→`2026-03`), windows
  (`QA2026_QUALITY_MONTHS`=Mar–Apr, `QA2026_WORKFLOW_MONTHS`=Mar–May).
- `gold_dump.py` — `load_quality_labels_2026` / `load_workflow_labels_2026`
  (paren-aware comma split so `(grammar, spelling, syntax)` stays intact; Workflow
  joins on `Case_ID`; compliance sub-dimension dropped) + `join_multilabel_2026`
  (live) and `join_regen_multilabel_2026` (regen CSV).
- `multilabel_score.py` — **new.** `parse_drivers`, `phrase_match` (the single
  hook to swap in an LLM judge), `score_quality_case` / `score_workflow_case`,
  `aggregate_quality` / `aggregate_workflow` (P/R/F1), report formatters.
- `runner.py` — `--framework Quality|Workflow --match-labels` routes to the
  scorer; prints a P/R/F1 report **separate** from driver accuracy; writes
  `runs/multilabel_<fw>_<stamp>.{json,csv}`. Added `--months` override.
- `regen.py` — `--framework` widened to `ALL_FRAMEWORKS` (worker already generic);
  `_gold_case_set` picks the right loader/window per framework.
- `ab_measure.py` — left **driver-only** on purpose (OVERALL pooling is a
  driver-accuracy instrument; help text points to the regen+runner path).
- `gold_audit.py --multilabel` — coverage by month, error-class counts, join
  health, **May re-verify**.
- `calibrate_multilabel.py` — **new.** Per-case hand-read dump of the scorer's
  TP/FP/FN + L3/error-type `phrase_match` calls (the part a human must confirm).

## 2. Metric design (why it's not the driver verdict)
- **Quality** — 5 dimensions graded independently. Gold *column name* = bot **L2**
  (the dimension); gold *cell value* = bot **L3** (specific error; comma-split for
  multiples). Per-dimension **detection** (gold-in-error AND bot-emitted-that-L2)
  → P/R/F1, plus **L3 classification** accuracy on the TPs. Critical-only variant.
- **Workflow** — one live dimension (workflow adherence). ~94% "no error", so raw
  accuracy is meaningless → **P/R/F1 on the error class** + error-type
  classification on the TPs. `bot_error` = any driver with L2 ==
  "Workflow Adherence Error"; "Unmapped" drivers tracked separately (diagnostic).

## 3. First numbers — frozen-live (prod 2.5-pro), the quotable baseline
**Quality** (85 cases, Mar–Apr): OVERALL detection **P 19.3% / R 39.8% / F1 26.0%**;
L3-classification **20.0%** (of 35 TPs). Per-dimension the story is the bot
**over-emitting** (low precision) and one hard gap: **Accuracy 0/24 detected** —
the bot essentially never flags accuracy errors on these gold cases. Critical-only
is similar (OVERALL F1 21.0%).

**Workflow** (1,595 cases, Mar–May): **P 6.9% / R 99.1% / F1 12.8%** — the bot
flags **1,590 of 1,595** cases as a workflow-adherence error vs **110** real gold
errors. Classic class-imbalance + massive over-firing. **error-type
classification 60.6%** on the TPs (when it does flag a real error, it gets the
type right ~60% of the time). Dominant bot L3s "Missing vector case hygiene
fields" (2,537) and "Incorrectly handled the re-open ticket" (2,372 — not even a
gold error type) drive the false positives.

**Read:** for both, the headline finding is **bot over-precision-loss** — it emits
too many drivers. Quality/Workflow bypass agent4, so **fix-v2 can't help them**;
the lever here is the Quality/Workflow sub-agent prompts (tighten when to emit a
driver), which is a separate, future prompt-tuning task.

## 3b. Model lever — regen on 3.1-pro (apples-to-apples with the driver run)
Same metric, regenerated through the **global 3.1-pro** path (temp 0, no-cache),
matcher unchanged. Q/W bypass agent4 so this is purely the model effect on the
dynamic-driver agents.

**Quality** (full 85 pop, Mar–Apr) — clear lift, and it **fixes the dead Accuracy
dimension**:

| Quality | P | R | F1 | L3-class |
|---|---|---|---|---|
| frozen-live 2.5-pro | 19.3% | 39.8% | 26.0% | 22.9% |
| **regen 3.1-pro** | **28.2%** | **45.5%** | **34.8%** | **60.0%** |

(L3-class shown *after* the §5 client/user synonym fix; was 20.0% / 57.5% before.)
Per-dimension on 3.1-pro: Accuracy **10/24** detected (was 0/24!) P43.5/R41.7;
Responsiveness F1 54.5; Communication Skills F1 37.0. **L3 classification 22.9→60.0%**
(2.5→3.1) is the big one — 3.1-pro picks the right specific error far more often,
mirroring the driver model lever (+21.5pp TTR). Critical-only OVERALL F1 35.8%,
L3-class 66.7%.

**Workflow** (350-case sample, 21 gold errors, 3.1-pro):

| Workflow | P | R | F1 | error-type-class |
|---|---|---|---|---|
| frozen-live 2.5-pro (1,595, 110 err) | 6.9% | 99.1% | 12.8% | 60.6% |
| regen 3.1-pro (350, 21 err) | 6.1% | 100% | 11.4% | **85.7%** |

**The over-firing is unchanged by the model** — 3.1-pro still flags 346/350 cases
(precision ~6%). That confirms precision is a **prompt/criteria** problem, not a
model problem: the Workflow sub-agent emits "Missing vector case hygiene fields" /
"Incorrectly handled the re-open ticket" on nearly everyone. The model *does* lift
**error-type classification** (60.6→85.7%, though only 21 TPs — thin, wide CI),
same shape as Quality's L3 jump. (Samples/denominators differ, so treat the
detection F1s as not-directly-comparable; the **over-firing** and **classification
lift** are the robust reads.)

Note: regen samples the union pool, so Quality (small pop) is regenerated with
`--framework Quality --sample 85` (full); Workflow separately with a large sample
to cover the rare error class. The runner defaults `--sample 200`, so pass a large
`--sample` when scoring the full Workflow regen. Files: `runs/regen_Q31.csv`,
`runs/regen_W31.csv`.

**Lever read (both frameworks):** the model (2.5→3.1) clearly helps
**classification** (Quality L3 20→57.5%, Workflow type 60.6→85.7%) and recall, but
the **precision ceiling is the bot over-emitting drivers** — fixed only by
tightening the Q/W sub-agent emit criteria, since Q/W bypass agent4 (fix-v2 can't).

## 3c. What the bot actually emits (the over-firing, concretely)
Pulled the live bot output for the gold cases (2.5-pro). The bot is **rubber-
stamping a few default drivers onto almost every case**, not assessing per case:

**Workflow** (1,595 cases):
- **Always exactly 2 drivers** (1,588/1,595); L1 is always `People Gap` (+121 `Unmapped`).
- **85% of all cases get the IDENTICAL pair**: *"Incorrectly handled the re-open
  ticket"* + *"Missing vector case hygiene fields"* (1,348 cases).
- Frequencies: "Missing vector case hygiene fields" on **95%**, "Incorrectly
  handled the re-open ticket" on **89%** of cases — and the latter **isn't even a
  valid gold error type** (the bot invented a default). Gold has only ~110 errors (~7%).

**Quality** (85 cases):
- L1 always `People Gap` (every quality issue blamed on the agent); **2+ drivers on
  79/85** cases.
- Two go-to drivers: *"Did not seek confirmation if all questions were resolved"*
  (**79%** of cases) + *"Did not tailor a solution to user's needs"* (**54%**); the
  single most common output (29%) is just that pair.
- **Barely flags Accuracy** (7 driver-instances / 85) → misses all 24 gold Accuracy
  errors. The dominant gold error **"did not structure response" (54/142)** is barely
  emitted. **[CORRECTED 2026-06-08, §10]** — this was originally written as "NOT in the
  bot's L3 vocabulary at all / can never emit it." That is **wrong**: the rule **IS** in
  vocab (`quality/agent1.md` rule 3); the bot just **under-emits** it (0–2/85). A
  clarity rewrite of rule 3 raised emission 0→11% (still < gold ~38%) — see §10. So it
  is an **under-emission**, not a vocab gap.

⇒ Two distinct prompt problems: **(a) over-firing** (default accusations applied by
reflex → precision collapse) and **(b) under-emission + default-blame** (under-emits
"did not structure response" — it IS in vocab, just rarely chosen, see §10; rarely
considers Accuracy; every Quality case → "People Gap"). Both are sub-agent **prompt**
issues, not model issues — confirmed by 3.1-pro leaving precision at ~6%. **(Originally
written as "vocabulary gaps / can't say it" — corrected 2026-06-08 in §10.)**

## 3d. DIAGNOSTIC (2026-06-07) — root cause of the over-firing
Sai's scope call: **improve Q/W** (#14). Ran the diagnostic — read the Q/W
sub-agent prompts (`prompts/{quality,workflow}/agent{1,2,3}.md`) + the cell-9
pipeline branch + an empirical check of the bot's two dominant Workflow rules
against the actual input data.

**Architecture (the "dynamic drivers" path):** each framework has 3 sub-agents;
each independently picks a *"Single BEST MATCH"* L3 **or returns "None"**. Cell 9
adds **every** non-"None" agent output as a driver (dedup by unique L3) — **no
agent-4, no aggregation, no confidence threshold**. So final driver count = how
many sub-agents fired. **"No error" IS allowed** (the pipeline skips
None/Error/Unclear) — the architecture does **not** force a driver. ⇒ the fix is
**prompt-level, NOT structural.** This is the key unblock for #14/A2.

**Why each agent over-fires — empirical (Workflow gold, 1,597 cases):**

| Bot rule | bot fires on | rule precondition actually true in data | verdict |
|---|---|---|---|
| "Incorrectly handled the re-open ticket" (needs `Reopen_Counter>0`) | **89%** | **12%** (`Reopen_Counter>0`) | **pure hallucination** — fires ignoring its own gate on ~77% of cases |
| "Missing vector case hygiene fields" (needs Closed AND a hygiene field empty) | **95%** | **65%** (Closed=100%, but only via `Next_Steps` empty=65%; Root_Cause empty=1%) | **too-broad rule + partial hallucination** — even correct application (65%) >> gold's ~7% real errors |

**Two distinct failure modes, now separated:**
1. **Metadata-gate hallucination** (the re-open rule): the agent emits a rule whose
   own deterministic precondition is false. Clean, high-value **prompt fix** —
   force each rule's metadata gate to be checked and return None when unmet.
2. **Rule too broad** (the hygiene rule): an empty `Next_Steps` on a closed case
   technically trips the rule but the gold doesn't count that as a workflow error.
   Tightening this needs Zaidul's call on *what counts* (B1/B2) — but it's also a
   prompt/rule-definition change, not architecture.

Plus the structural over-eagerness: the prompt bolds *"BEST MATCH"* 3× and treats
*"None"* as an afterthought, with **no "did any violation clear the bar?" gate** and
**no aggregation step** to suppress weak picks — so 3 eager agents → 2–3 drivers on
~everyone.

**Cost of "improve" (answers A1's implicit cost question):** medium, prompt-only —
(a) add an explicit evidence/precondition gate + a "default to None unless clearly
met" instruction to each Q/W sub-agent; (b) tighten the 2 broadest Workflow rules;
(c) for Quality, fix the vocab gap (can't emit "did not structure response") and the
default-blame. No notebook architecture change. Measurable locally via regen + the
scorer on **held-out** gold. **Next:** draft (a)+(b) as a disciplined change, measure
F1 on a held-out split, hand Zaidul a labeled hypothesis+delta (vocab/B1 + the
hygiene-rule definition need his sign-off).

## 4. Gold audit / May re-verify (settled)
`gold_audit --multilabel`: Quality joins 142/142; Workflow 2,678/2,683 on
`Case_ID`. **May'26 Workflow: 456 rows, 48 errors, 454 with a bot pred** → joins
clean and carries the *most* errors, so including May ~doubles the error
denominator (110 Mar–May vs 62 Mar–Apr). Kept Mar–May for Workflow. **Open Q for
Zaidul:** is the workflow taxonomy stable across the March cutover (i.e. is May
legitimately comparable)? Data-wise it's fine.

## 5. Calibration — DONE (hand-read 2026-06-05), decision: deterministic, no judge
Hand-read every TP decision in both dumps (`runs/calib_multilabel_*`):

| Framework | scorer↔human agreement | call |
|---|---|---|
| **Workflow** error-type | **19/19 (100%)** | deterministic — done |
| **Quality** L3 | **12/13 (92%)** → **13/13** after one fix | deterministic — done |

Both clear the ≥70–90% bar, so **no LLM judge** (it would add cost / latency /
non-determinism to fix ~1 case in 13). Key insight: the low L3-classification
*percentage* is a **real bot weakness** — it detects the right dimension but emits
a *different specific sub-error* (e.g. gold "did not answer all questions" vs bot
"did not seek confirmation"; gold "did not structure response" — which has **no
bot-vocab equivalent at all**). The matcher correctly calls those misses. Workflow
false positives are almost all the same over-fired pair ("Incorrectly handled the
re-open ticket" + "Missing vector case hygiene fields"), confirming §3's
over-emission story.

**The one fix:** the sole Quality deterministic miss was gold *"...client's needs"*
vs bot *"...user's needs"* — the same party in GTM support. Added a targeted
party-synonym fold (`client/customer/seller/requester → user`) in
`multilabel_score._norm`; 7/7 unit checks pass (the synonym matches; genuine
misses + truncation + exact-ci all stay correct). Effect (detection P/R/F1
unchanged, as expected — synonyms only touch L3): Quality **L3-classification
57.5→60.0%** on 3.1-pro (Relevance L3-acc 50→75%), 22.9% frozen-live. Calibration
re-run confirms the client/user TP now scores a match. **Quality L3-classification
is now final/quotable.**

**Driver regression check:** ran all 4 driver frameworks through the shared
`runner --match-labels` path (20 cases each, 80 verdicts) — all produced clean
Correct/Incorrect verdicts, no breakage from the multilabel wiring. (Accuracy on
that tiny frozen-live 2.5-pro sample is anchor-consistent: TTR 20% / Reopen 10% /
Esc 0% / DSAT 5% — a path check, not an accuracy measurement.)

## 6. Open questions for Zaidul
- Workflow `Error Status` (`Yes`=2031 ≠ ~164 dim errors) — **not used as a label.**
- Workflow May'26 / taxonomy cutover — data joins; confirm comparability.
- Quality Critical-vs-Non-critical — **reported as a breakdown, not weighted.**
- Bot `"Unmapped"` L1/L2 in Workflow (201 drivers) — pipeline taxonomy-resolver
  gap; tracked as diagnostic (`n_unmapped_only`).
- Comma-joined multi-errors / truncated gold L3 — handled (paren-aware split +
  truncation-tolerant `phrase_match`).

## 6b. Metric guide — what each number means (and does NOT)
Several numbers in this note are easy to misread as "accuracy." They are not the
same thing — keep them separate:

| Number | What it is | NOT |
|---|---|---|
| **calibration 19/19, 13/13** | how well *the scorer* agrees with *a human* (validates the measuring tape) | ❌ not bot accuracy |
| **Workflow recall 99–100%** | the bot flags an error on ~everyone | ❌ that's *bad* (over-firing), not good |
| **error-type 85.7% / L3 60%** | classification accuracy **only on the ~11–21 cases where the bot already detected a real error** (conditional, tiny n) | ⚠️ not over all cases |
| **F1 (Quality ~35%, Workflow ~11%)** | the real headline for Q/W (P/R balanced on the error class) | the honest bot-quality number |

- **There is NO single "overall accuracy across all 6."** Drivers use case-level
  `Correct ÷ Audited` (goal **80%**, best so far **~22.4%** w/ 3.1-pro+fix-v2);
  Q/W use **detection P/R/F1** (because ~94% of Workflow is "no error", plain
  per-case accuracy would reward a bot that says "no error" always — it'd score 94%
  catching nothing). The two metrics can't be averaged.
- **We did NOT hit 90+ on Q/W and did NOT change their prompts this session** — the
  only changes were the model (2.5→3.1, measurement) and a *scorer-side* synonym fix.
- **Best setup today:** 3.1-pro + fix-v2 → drivers ~22.4%, Quality F1 ~35% /
  L3-class 60%, Workflow F1 ~11% / error-type 85.7%. All far from any 90.

## 6c. Open decisions / inputs needed before the next step
The next real lever is a **Q/W sub-agent prompt change** to cut the over-firing
(§3c). Before/while doing it, these are owed:

- **A1 (Sai) — SCOPE [gating]:** are Quality/Workflow meant to *improve*, or just be
  *reported* for Pooja's all-6 view? The June-15 demo gate is the **4 drivers at
  80%** (currently 22%), so the recommendation is **report-only Q/W, focus drivers**
  — but it's Sai's call. Everything below only matters if "improve".
- **A2 (Sai/Zaidul/code) — is the bot allowed to output "no error"?** Today the
  pipeline forces Q/W to always emit a driver (Workflow emits exactly 2 on 99%) —
  the root of the precision problem. Whether "always emit" is by design or just how
  it was built can be **read from the pipeline (cell 9 dynamic-driver branch)** —
  doesn't strictly need a human.
- **B1 (Zaidul) — canonical L3 vocabulary:** the bot can't say the most common gold
  error ("did not structure response"). Re-aligning the Q/W L3 vocabulary to the
  gold taxonomy needs Zaidul's Voice-of-Seller sheet. For a *local experiment* the
  gold's own strings can stand in (hypothesis, not canonical).
- **B2 (Zaidul) — the §6 open gold-semantics questions** (affect whether the
  numbers are trustworthy): `Error Status`, May/cutover, Critical weighting,
  compliance drop, `Unmapped`.
- **A3 (Sai) — push decision** on the staged 3.1-pro + fix-v2 (separate workstream).
- **Convention:** per `feedback_evaluator_workflow`, the right order is **measure a
  prompt-change delta locally first, then take the confirmed delta to Zaidul** — so
  a local "spike" (draft change → measure on held-out gold → labeled hypothesis) is
  the correct next move IF A1 = "improve". Held-out split avoids overfitting to the
  85 Quality cases.

## 7. Next steps
1. ~~Hand-read the calibration dumps + decide deterministic vs LLM judge~~ —
   **DONE 2026-06-05** (§5): deterministic for both (Workflow 19/19, Quality
   13/13 after the synonym fix); no judge; drivers regression-checked clean.
2. **Awaiting Sai's A1 (scope) decision** (§6c): report-only vs improve Q/W. Until
   then, no Q/W prompt work.
3. **If report-only:** finalize the all-6 numbers for Pooja (§3/§3b ready) and
   redirect to the 4-driver 80% push (the demo gate).
4. **If improve:** run the local spike — read Q/W sub-agent prompts + cell-9
   branch (answers A2), draft an emit-criteria change, measure F1 on **held-out**
   gold, hand Zaidul a labeled "hypothesis + delta" (B1/B2 in a live session).
5. **Report all-6 to Pooja**; **push** the staged 3.1-pro + fix-v2 (A3); **resolve
   §6 open Qs with Zaidul**.

## 8. State of the tree
Evaluator: `config.py`, `gold_dump.py`, `runner.py`, `regen.py`, `ab_measure.py`,
`gold_audit.py` edited; `multilabel_score.py` (incl. the party-synonym fold),
`calibrate_multilabel.py` new; `README.md` updated. New `runs/multilabel_*`,
`runs/calib_multilabel_*`, `runs/regen_Q31.csv`, `runs/regen_W31.csv`. **No bot
prompt or notebook changes** (the synonym fix is scorer-side only); nothing pushed.
The Q/W sub-agent prompt change (§3c / §6c) is NOT started — gated on A1.
**(Superseded by §9 — A1 = improve; the prompt change is now drafted + measured.)**

## 9. Spike result (2026-06-07) — Q/W prompt change drafted + measured
A1 resolved (**improve**). Ran the local spike per §6c convention: drafted the two
no-Zaidul levers (**5.Q/W.1** metadata gate + **5.Q/W.3** reframe "None"), measured
a **clean same-cases OLD-vs-NEW A/B on 3.1-pro** (the staged prod model), held-out
months (Quality→April, Workflow→May). Nothing pushed.

**What changed (`prompts/{quality,workflow}/agent{1,2,3}.md`):**
- Rewrote the shared `### CRITICAL INSTRUCTION FOR ACCURACY & OUTPUT` block in all
  6 sub-agents: makes "None" the default + forces a metadata-gate check, keeps the
  exact pipe-line output contract. (`workflow/agent3` had no such block → inserted one.)
- Inline `Reopen_Counter > 0` GATE on `workflow/agent1` rule 6 (the re-open rule).
- **Quality framing later softened** (see finding 2) — Quality agents drop the
  "most cases have NO violation" prior, keep the anti-default-stacking + correct-L3
  emphasis. Workflow keeps the strong version.
- **Untouched (deferred to Zaidul):** the hygiene rule (5.Q/W.2) and the Quality
  L3 vocab gap (5.Q/W.4).

**Workflow — over-emission, same 30 cases (3.1-pro, May):**

| | avg drivers/case | re-open fires | hygiene fires |
|---|---|---|---|
| OLD | 1.53 | 17% | 93% |
| NEW | **1.13** | **10%** | 93% (untouched) |

**Quality — detection, same 35 cases (3.1-pro, April held-out):**

| Quality April | P | R | F1 | L3-acc | tp/fp/fn |
|---|---|---|---|---|---|
| OLD | 32.8 | 54.1 | **40.8** | 65.0 | 20/41/17 |
| NEW1 (strong "None-default") | 36.1 | 35.1 | 35.6 | 84.6 | 13/23/24 |
| **NEW2 (softened, staged)** | 32.7 | 48.6 | **39.1** | 72.2 | 18/37/19 |

**Three findings (these change the plan):**
1. **The "89% re-open hallucination" was a 2.5-pro problem.** On 3.1-pro (staged for
   prod) it was already only **17%** — the model self-corrects the gate. The fix
   trims it to 10% and cuts total over-emission **1.53→1.13 drivers/case (~26%)**.
   Real, but smaller than the 2.5-pro §3d diagnostic implied.
2. **A blanket "most cases have no violation" prior backfired on Quality.** True for
   Workflow (~94% clean), false for Quality. NEW1 cratered recall −19pp → **F1
   −5.2pp**. Softening it (NEW2) recovered recall to ~F1-neutral (−1.7pp, noise at
   n=35) with a real **L3-classification gain (+7.2pp)**. Framing must be
   **per-framework**, not blanket.
3. **Both headline-F1 levers are gated on Zaidul** — confirming §6c. Workflow
   detection-F1 is bottlenecked on the **hygiene rule** (still fires 93%, OLD=NEW →
   binary `bot_error` ~unchanged) = **5.Q/W.2**. Quality F1 is bottlenecked on the
   **vocab gap** (can't emit the dominant gold error "did not structure response") =
   **5.Q/W.4**. The no-Zaidul levers reduce over-emission + improve sub-error
   classification, but neither moves headline F1 the +5pp the gate wants.

**Staged state (local only, not pushed):** Workflow = strong gate+reframe
(over-emission win, no F1 regression); Quality = softened (F1-neutral, +L3-class).
Runs: `runs/regen_2026-06-07T12-28-57Z.csv` (W-NEW), `…12-37-58Z` (W-OLD),
`…12-34-14Z`/`…12-49-22Z` (Q-NEW1/NEW2), `…12-42-48Z` (Q-OLD); scored
`runs/multilabel_{Quality,Workflow}_2026-06-07T*`.

**Next:** take this labeled hypothesis+delta to Zaidul to unblock **5.Q/W.2**
(hygiene-rule definition, B2) + **5.Q/W.4** (Quality L3 vocab, B1) — the two real
F1 levers. Decide whether to keep Quality NEW2 (borderline) or revert to OLD recall.
See the **Stage-1 combined scorecard** in `docs/execution-plan.md`.

## 10. Stage-2 spike + decisions (2026-06-08) — the two "Zaidul-gated" F1 levers, re-tested

A data check this session **changed the diagnosis** of both remaining F1 bottlenecks,
so Sai's call was: **spike both locally, measure F1 on held-out gold, then bring Zaidul
*measured* proposals** (not hypotheses). All runs 3.1-pro / temp 0 / `--no-cache`,
**same-cases OLD-vs-NEW** (regen `random_state=42`), held-out month at scoring
(`runner --months`). **Everything reverted to Stage-1 after measuring — nothing pushed.**
Run artifacts: `runs/regen{OLD,NEW}_{Q,W}.csv`, `runs/multilabel_{Quality,Workflow}_2026-06-08T*`.

### Decisions locked (verbatim, recorded so nothing is lost)
1. **Item 1 — Workflow hygiene rule (5.Q/W.2):** redefine locally, measure held-out F1,
   take the result to Zaidul. Confirm-with-Zaidul: *is empty `Next_Steps` on a closed
   case ever an error? which issue types make the fields mandatory?*
2. **Item 2 — Quality structure-response (5.Q/W.4):** execute (a) rewrite rule-3 logic,
   (b) add a tie-break vs grammar (rule 2) / "answer-all-questions" (Completeness),
   (c) measure — all locally; then a one-line Zaidul confirm that his label means the
   same concept.
3. **Item 3 — gold-semantics:** insulate the pipeline with **safe defaults**, keep
   Zaidul informed. `Error Status` = coarse flag (not the label); include May but
   **report it separately**; Critical **reported, not weighted**; `Unmapped` **excluded
   from the precision denominator** (diagnostic); **compliance sub-dimension dropped.**
   (These defaults are already in `multilabel_score.py` / `gold_dump.py` — see §6/§6b.)
4. **Item 4 — framework diff:** Product/Tools Gap + Quarter Freeze **adopt-as-encoded**
   (confirm wording vs Voice-of-Seller); **KSI → code** (`prepare_*_input` pre-filter,
   future task 4.3, not built here); Quality 3-agent split **treated resolved** (already
   enumerates all 5 metrics). Close in a **live show-and-tell**, not async edits.

### Spike A — Workflow hygiene rule (item 1). **PREMISE OVERTURNED — it is hallucination, not rule breadth.**
The pre-spike belief (locked item 1; §3d) was "the gate is *literally true* (empty
`Next_Steps` on 65%), so it's a **rule-definition-breadth** problem, **not**
hallucination." **The data says the opposite.** I narrowed rule 9 to drop the
standalone empty-`Next_Steps` trigger and keep only `Root_Cause`/`Root_Cause_Description`
empty (+ the Comp/Attainment field set), then measured the **same 300 cases**:

| Workflow (3.1-pro, 300 cases) | avg drivers/case | hygiene-L3 fires | re-open fires | binary adherence fire |
|---|---|---|---|---|
| OLD (Stage-1) | 1.10 | **97%** (293/300) | 2% | 98% |
| NEW (rule narrowed) | 1.01 | **87%** (263/300) | 2% | 88% |

| Workflow detection (May held-out, 86 cases, 8 gold errors) | P | R | F1 | tp/fp/fn | err-type |
|---|---|---|---|---|---|
| OLD | 9.3% | 100% | **17.0** | 8/78/0 | 87.5% |
| NEW | 8.0% | 75% | **14.5** | 6/69/2 | 83.3% |

**Why the narrowing barely moved firing (97→87%) and *hurt* recall:** the bot keeps
firing the hygiene rule by **fabricating that `Root_Cause`/`Root_Cause_Description` are
empty.** Verified against the live input for the same 300 cases:

| Field | **actual** empty-rate (input data) | bot's NEW hygiene justification claims empty |
|---|---|---|
| `Root_Cause` | **1%** | the majority of the 263 firings |
| `Root_Cause_Description` | **1%** | the majority of the 263 firings |
| `Next_Steps` | 63% | 107/263 still cite it despite the rule change |

Spot-checked cases (bot said "Root_Cause + Root_Cause_Description are empty"):
`70387546` → `Root_Cause="User Education"`; `69413718` → `"Other"`; `70430464` →
`"User Education"` — **all populated.** This is the **same failure mode as the re-open
gate** (metadata-emptiness hallucination), not a too-broad rule. ⇒ **A prompt rewrite
cannot fix it — the model ignores the real field values.** The robust fix is
**deterministic field-grounding in code**: compute the hygiene violation from the
actual `Root_Cause`/`Root_Cause_Description`/`Next_Steps` values in a
`prepare_workflow_input` / post-filter step (sibling to the KSI code rule, item 4),
bypassing the model. **DECISION: reverted the prompt edit to Stage-1** (it didn't fix
the problem and cost 2 recall TPs); the real fix is logged as a **new future code task**
(see execution-plan 5.Q/W.2 + task 4.4). To Zaidul: this is now an *engineering* fix
plus the semantics confirm (does empty `Next_Steps` on a closed case ever count?).

### Spike B — Quality "did not structure response" (item 2). **Mis-diagnosis confirmed; partial local win; F1 gated on Zaidul semantics.**
Rewrote rule 3 (`quality/agent1.md`) to be concrete + recall-friendly (wall-of-text /
no greeting→ack→resolution structure / missing required canned response) + a tie-break
(form vs grammar=rule 2 vs missing-answers=Completeness) + a structure-check analysis
instruction. **Same 85 cases / April held-out (35):**

| Quality April (3.1-pro) | OVERALL F1 | tp/fp/fn | L3-acc | rule-3 emission (full 85) |
|---|---|---|---|---|
| OLD (Stage-1) | **40.9** | 19/37/18 | 68.4% | **0/85 (0%)** |
| NEW (rule-3 rewrite) | **37.5** | 18/41/19 | **72.2%** | **9/85 (11%)** |

Per-dimension: **Accuracy F1 21.1→31.6** (L3 50→67), **Communication Skills F1
48.0→32.3** (the structure firings land as FPs: 12→19 FP, recall 86→71), Completeness
35.7→33.3, Relevance 54.5→50.0, Responsiveness 60→60. **Read:** the **mis-diagnosis is
confirmed** — the rule was *in vocab* but emitted **0/85**; a clarity rewrite raises it
to **11%** (gold prevalence ~38%) and lifts L3-classification (+3.8) and Accuracy, **but
the new structure firings are mostly FPs on held-out**, so headline F1 is
flat-to-slightly-down (−3.4pp, within n=35 noise). Converting firings to TPs needs
**Zaidul's one-line confirm that his "did not structure response" label means the same
concept** (so the bot can target the right pattern). **DECISION: reverted to Stage-1,
carried as a measured Zaidul-gated proposal** (exact rule-3 text above + in git history);
apply after Zaidul's confirm (locked item 2).

### Net (both spikes) + correction to the §9 framing
The two remaining F1 levers were tracked as "Zaidul-gated rubric questions." **This
session re-scoped them with data:**
- **5.Q/W.2 (Workflow hygiene)** is **NOT** a rule-breadth question — it is
  **field-emptiness hallucination** (verified). Fix = **deterministic code-grounding**
  (engineering, mostly local), + a small Zaidul semantics confirm. The prompt lever is
  a dead end.
- **5.Q/W.4 (Quality structure)** is **NOT** a vocab gap — it is **under-emission of an
  existing rule** (verified: 0→11% with a prompt clarity rewrite). Mostly fixable
  locally for emission + classification; the F1 gain needs a one-line Zaidul semantic
  confirm.

Both confirm the §9 meta-finding from a new angle: **the local levers move
sub-behaviors (emission 0→11%, over-emission 1.10→1.01) but do not clear the headline-F1
gate** — and for Workflow the real fix isn't even a prompt. **Stage-1 is unchanged**
(both spikes reverted; prompts/ + notebook restored, verified). Driver guardrail: all 4
drivers ran clean through the shared `runner --match-labels` path (32 verdicts, no
regression).
