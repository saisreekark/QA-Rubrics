# Open questions — active only

What we still need answered. Grouped by who can answer, so Sai can walk
into a stakeholder meeting with the relevant subset.

For previously-resolved items (and the answers we got on 2026-05-14 and
2026-05-29), see [`resolved-questions.md`](resolved-questions.md).

---

## For Zaidul — RESOLVED 2026-06-08 (answers in hand)

These were the measured proposals taken to Zaidul; his answers are recorded here and
propagated into the stage-tracker, execution-plan, CLAUDE.md, KT notes, and memory.

1. **Workflow hygiene — does *every* closed case with an empty `Next_Steps` count as a
   defect? → YES.** ⇒ the task-4.7 grounding (literal rule 9, which already counts empty
   `Next_Steps`) is **validated as-is — no change.** Important consequence: the measured
   precision gap (P 13.6%, the 49 held-out "FPs") is **gold UNDER-labelling, not bot
   over-firing** — every empty-`Next_Steps` firing is a real defect Zaidul stands behind. So
   the +6.9pp Workflow F1 is **conservative**; against fully-labelled gold the true precision
   is higher. (Ref: `docs/stage-tracker.md` Stage 2; `session-2026-06-05-6driver.md` §10.)
2. **Drivers — when a closed case is reopened because the seller raises a NEW/different
   query, is the primary driver "User Gap (New Query)"? → YES, the gold is right.** ⇒ the bot
   is genuinely **wrong** to default to Process/People Gap. We then built + measured **both** a
   prompt lever (~0) **and** a hard deterministic code override (`ab_measure` 3×120 Reopen: OLD
   20.0% → NEW 22.5%, **Δ+2.5pp, CIs overlap → fails the +5pp gate → REVERTED**). The cap is the
   **surfacing wall** (the model emits New Query ~13/150 vs gold ~49%). ⇒ **Phase-3 lever = a
   dedicated New-Query detector** (focused classifier / deterministic signal), not a bigger
   override. (Ref: KT `session-2026-06-08-driver-usergap.md`; memory `project_driver_usergap_ceiling`.)
3. **New-taxonomy wording — approved.** New L1 **"Product/Tools Gap"** + L3 **"Quarter Freeze
   / YoY Planning & Implementation"** wording is confirmed. **Spell-checked clean 2026-06-08**
   (consistent across all 18 prompts + `HIERARCHY_CONFIG`; no typos). **Question CLOSED.**
4. **TTR threshold — a case resolved/aged < 7 days is NULL for TTR** (no TTR defect possible).
   ⇒ the pipeline trigger changes from `Case_Aging_in_Days > 5` to **`>= 7`** (cell 9
   `process_single_row`). **DONE + staged 2026-06-08** (part of the Phase-2 bundle, not pushed).
5. **Quality consolidation shape — "whatever gives the best accuracy/results."** ⇒ resolved to
   a **measurement decision (Sai's call)**: pick the 1-agent-vs-3-agent structure that scores
   best on the detection metric; not a Zaidul-gated design choice anymore.

## For Zaidul — RESOLVED 2026-06-09 (doc-derived; Zaidul delegated to the policy docs)

**Zaidul's final answer to all remaining questions was "refer to the docs"** — he shared the
**SOP Summary** + **Terms & Conditions Summary** ([[reference_kb_source_docs]];
`docs/kb-source/`) and delegated the calls to us. So these are now **closed with doc-grounded
decisions** (no further Zaidul input expected), propagated project-wide.

1. **Quality "did not structure response" (rule-3) — CLOSED (definition adopted; lever parked).**
   The QA rubric line isn't in the policy docs, but the SOP grounds a clear structure norm:
   agents use **canned responses / templates** and a **step-by-step resolution structure**
   (acknowledge → diagnose → resolve → next steps). **Decision:** adopt the broad operational
   reading — the rule fires when the reply isn't organized enough for the seller to follow the
   resolution + next steps (wall-of-text, no clear structure, no canned-response/template use).
   **But we do NOT ship the aggressive 5.Q/W.4 rewrite** — it raised emission 0→11% and L3-class
   +3.8 yet its held-out firings were FPs (F1 flat-to-down), so it adds no measured F1. **Quality
   stays at its Stage-2 form (F1 39.1%).** Revisit only if the gold is re-labelled to credit the
   new firings.
2. **KSI qualifier — CLOSED (formalized from SOP + data).** **Decision:** a case is **NULL for
   TTR** (KSI exclusion) when **both** (a) it carries a **known-systemic-issue marker** —
   operationally a **`KSI -` / `KSI:` tag in `Root_Cause_Description`** (confirmed present in prod
   data) **or** a linked `Bug_Id` whose resolution note says the systemic fix is "under
   development / evaluation" (SOP **"Outcome 3"**: system bugs / complex technical issues,
   resolution "days to months") — **and** (b) the fix is pending a **future / uncommitted
   resolution** (Eng/system-dependent). This extends the already-shipped **`<7 days = null`** gate
   and the SOP's **"WOCA pauses the SLA"** logic. **Implementation: BUILT 2026-06-09** — a gated
   deterministic cell-9 pre-LLM filter (task-4.7 pattern), `evaluator/ksi_ground.py` +
   `is_ksi_excluded` inline mirror (`EXCLUDE_KSI_FROM_TTR=True`) wired to skip the TTR run; staged,
   not pushed. **Measured LIVE 2026-06-09:** fires on **116/2,592 (4.5%)** of TTR-audited cases
   (KSI-tag 101 / Bug_Id+pending 15); **gold-validated** — 46/46 excluded TTR-gold cases are
   external-cause (35 Product/Tool + 8 Process + 3 User Gap, **0 People Gap**). Fresh TTR
   label-match: **17.6%→16.4% (Δ −1.2pp)** — it's a **metric-validity (SLA/breach) rule, not an
   RCA-accuracy lever**. (The `<7 days` half was already shipped.) **New nuance for Zaidul:** the
   QA-2026 TTR gold *still audits* KSI cases (external drivers) rather than NULLing them → confirm
   exclude-entirely (our filter) vs attribute-to-external-driver. See
   `docs/session-2026-06-09-ksi-kb.md`.
3. **Gold-semantics ratifications — CLOSED (adopt the coded safe defaults).** Zaidul delegated, so
   the defaults already in `multilabel_score.py`/`gold_dump.py` are ratified: `Error Status` =
   coarse flag (ignored as a label); **May** Workflow gold = valid (reported separately);
   Critical = reported as a breakdown, **not** severity-weighted; `Unmapped` L1 excluded from the
   precision denominator; compliance sub-dimension dropped. **Use as-is for the Pooja numbers.**
4. **The two May-14 TBC artifacts** (`1LZ6z…` RCA labelling sheet, `1W4Gtzg…` doc) — **CLOSED as
   won't-pursue.** Not blocking anything; reopen only if a concrete need arises.

## For Vikram

6. **Full scheduler map.** The output generator (`rubrics-automation-run`)
   runs; the **input-extraction** and **code-run** schedulers still need
   to be built or verified. Where do the missing ones live and who owns
   them?
7. **Volume sizing.** Is "~3000 cases" daily / weekly / rolling? Drives
   the token budget on Vertex Context Caching.

## Engineering hygiene — Sai owns

Internal cleanup, not stakeholder questions.

- **Rotate the OAuth token** in notebook cell 7 to Sai's own short-lived
  token now; plan service-account auth as the durable fix.
- **KB local access (measurement fidelity) — ONE ACL grant unblocks a fully-built
  automated path.** The 4 KB docs 403 (`PERMISSION_DENIED`) for `saisreekark@google.com`
  AND for every runnable SA (compute, `compensation-support-bot@`) — the KB is shared
  only with the cell-7 user. The automated snapshot pipeline is **built + proven** (Colab
  execution as the compute SA, GCS I/O, drive scope all work — `docs/kb-local-access-2026-06-08.md`);
  the ONLY blocker is the Drive ACL. **Action (needs a KB-file owner):** grant **Viewer
  on the 4 KB files to `653428233292-compute@developer.gserviceaccount.com`** (or to
  `saisreekark@google.com`), then re-run the uploaded `gs://analytics_genai/kb_dump.ipynb`
  (one `gcloud colab executions create`). Caveat: the **Do_Not_Contact** sheet is PII —
  if sharing is policy-blocked, snapshot the 3 SOP/T&C/Plan docs only.
