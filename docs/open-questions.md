# Open questions — active only

What we still need answered. Grouped by who can answer, so Sai can walk
into a stakeholder meeting with the relevant subset.

For previously-resolved items (and the answers we got on 2026-05-14 and
2026-05-29), see [`resolved-questions.md`](resolved-questions.md).

---

## For Zaidul (live working session)

1. **KSI auto-close — code or prompt?** Should the rule live in
   `prepare_reopen_input` (notebook cell 8 — pre-LLM filter) or inside
   the Reopen agent prompts (LLM-driven)?
2. **Quality consolidation target shape.** Single agent with five
   enumerated metric fields, or two agents (people-metrics vs
   process-metrics)? Zaidul has the call.
3. **Confirm the QA dump is the agreed ground truth.** The dump sheet
   (`1tbrQ…`) is now the evaluator's label-match gold source — confirm
   this corpus is the canonical reference Zaidul's team stands behind.
4. **Quality / Workflow label-match shape.** Quality labels are
   per-metric scores (`Accuracy`/`completeness`/`relevance`/
   `Communication`/`responsiveness` + `evaluation_score` + `grade`), not
   L1/L2/L3 drivers — they need a score-match, not the driver-match used
   for TTR/Reopen/DSAT/Escalation. Workflow bot output is also sparse in
   the dump (~200 cases). How should these two be scored?
5. **Purpose of the two TBC artifacts** shared on May 14 (`1LZ6z…` RCA
   labelling sheet, `1W4Gtzg…` doc). Worth opening?

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
