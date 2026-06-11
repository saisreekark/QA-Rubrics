# Audit frameworks

Six frameworks run on every case. Each emits its own RCA column in
`RCA_Analysis_Output_1`. The L1/L2/L3 hierarchy below is the authoritative
copy from `HIERARCHY_CONFIG` in cell 4 of the notebook (snapshot from
`notebook/content.ipynb`, last updated 2026-01-20).

> ✅ **Driver diff ENCODED locally (2026-05-29) — `HIERARCHY_CONFIG`
> (cell 4) + `prompts/`.** The 3 confirmed edits are in: Reopen
> `Product/Tools Gap` L1 (it already existed in TTR/DSAT/Escalation),
> `Quarter Freeze / YoY Planning & Implementation` L3 across all four
> driver frameworks, and the `Complex Processes` rename in Reopen.
> Verified via the hierarchy parser. ⚠ **Local mirror only — not pushed
> to the prod notebook (`push_notebook.sh` deferred) and not yet
> Zaidul-reviewed.** Canonical source = the Voice-of-Seller sheet
> `1VXtXkbY9PkX2_7RODj2kco3SYSMzYpXyOMt1CPZfZ9Q`. **Still pending:** KSI
> auto-close + Quality consolidation. **Scope = the 4 driver frameworks
> only; NOT Quality/Workflow.** Accuracy delta needs a regen run
> (Phase 2.7) — `--match-labels` scores frozen predictions. Exact diff:
> memory `project_framework_diff_confirmed.md`.

## Multi-agent setup

Each framework runs N agents sequentially (output of one feeds the next).
The final agent of each framework usually has `use_cache: True`.

| Framework | Agents | Cache on last? |
|---|---|---|
| Reopen | Triage_Metadata_Auditor → Soft_Skills_Auditor → Process_Knowledge_Auditor | ✓ |
| TTR | Timeline_Auditor → Process_RootCause_Auditor | ✓ |
| Escalation | Escalation → Performance → Policy_RAG | ✓ |
| DSAT | DSAT_Audit → Performance → Policy_Process_Expert | ✓ |
| Quality | Assurance_1, Assurance_2, advanced_Support_1, advanced_Support_2, Compliance_1 | ✓ (Compliance_1) |
| Workflow | Assurance → Compliance → review | ✓ |

Quality runs **5 agents** vs 2–3 for others. Per Zaidul on May 14, the
five correspond to **Accuracy / Completeness / Relevance / Communication /
Responsiveness** and are open to **consolidation** (possibly into a single
agent) provided the output enumerates each metric with explicit pass/fail
and "no error" for non-failing metrics. Sai to propose a target shape in
the live session.

## Hierarchy reference

### 1. Reopen

| L1 | L2 | L3 |
|---|---|---|
| **Product/Tools Gap** *(NEW — canonical, not yet encoded)* | Product Limitation | Feature is not available / doesn't exist; Latency issue (need time to reflect changes) |
| **Product/Tools Gap** *(NEW)* | Product Bugs | Bug/technical issues with GCBP; Bug/technical issues with internal tools |
| Invalid Reopen | Invalid Reopen | Thank you email or Request closure |
| People Gap | Accuracy | Identified a wrong root cause; Provided an inaccurate solution |
| People Gap | Communication Skills | Asked for info repeatedly; Poor articulation; Did not structure response; Did not exude ownership; Did not respond with empathy |
| People Gap | Completeness | Did not answer all questions; Did not seek confirmation; Did not correct user's misunderstanding |
| People Gap | Relevance | Created confusion; Did not tailor solution |
| People Gap | Responsiveness | Did not respond in 24h; Missed follow-up |
| Process Gap | Workflow Complexities | Approvals/Exceptions Required; Complex Processes; Bulk Requests; **Quarter Freeze / YoY Planning & Implementation** *(NEW)* |
| Process Gap | XFn Support Efficacy | Delayed/dissatisfactory response from dependent teams; Delayed/inaccurate routing; Delayed/inaccurate consult response; Routing complexity |
| User Gap | Missing Information | Incomplete info; WOCA |
| User Gap | Mistakenly opened | Duplicate; Blank Reopens |
| User Gap | New Query | Additional or different Query |
| User Gap | Policies | User disagrees with policies/processes |
| User Gap | Timeline | Closure after deadline |

### 2. TTR (Time to Respond)

L1 buckets: Out of Scope, People Gap, Process Gap, User Gap (full L2/L3 in
`HIERARCHY_CONFIG`). Read directly from `notebook/content.ipynb` cell 4 — it
is too long to copy here and will change once Zaidul ships the update.

### 3. Escalation, 4. DSAT, 5. Quality, 6. Workflow

Same — see cell 4 of the notebook. Each follows the People / Process / User
Gap pattern with framework-specific L2 buckets.

## Cross-framework additions — the pinned, still-unencoded diff

Pinned 2026-05-29 by diffing the canonical Voice-of-Seller sheet against the
live `HIERARCHY_CONFIG`. Scope = **4 driver frameworks only** (not
Quality/Workflow). Full strings in memory `project_framework_diff_confirmed.md`.

1. **Reopen — add L1 `Product/Tools Gap`** *(the only genuinely-new L1 —
   TTR/DSAT/Escalation already have it)*: `Product Limitation` → *Feature is
   not Available/doesn't exist*, *Latency issue (need time to reflect
   changes)*; `Product Bugs` → *Bug/Technical issues with GCBP*,
   *Bug/Technical issues with internal tools*.
2. **Reopen — `Process Gap → Workflow Complexities`:** rename the drifted L3
   `Complex Processes e.g. Quarter close guidelines` → `Complex Processes`,
   **and** add `Quarter Freeze / YoY Planning & Implementation`. (Canonical
   has no "Quarter close guidelines" string.)
3. **TTR / DSAT / Escalation — add L3** `Quarter Freeze / YoY Planning &
   Implementation` under `Process Gap → Workflow Complexities`. Their
   `Product/Tools Gap` already matches canonical — no change.

**Leave as-is (confirmed):** the `Latency` placement split (TTR/Escalation
file it under `Product Complexity`; Reopen/DSAT under `Product Limitation`)
and TTR's distinct `Product Bugs` L3 wording — follow canonical per-framework.

## Reopen processing rule — KSI auto-close (still open)

**KSI (Known-Issue) cases with a future resolution date** should be
auto-closed so they don't bleed into TTR/SLA metrics. Trigger is known:
`Issue_Type == "KSI"`. **Four pieces still undefined for Zaidul:**
(a) which date column = "future resolution date" (`Next_Steps_Due_Date`?) and
future-relative-to-what; (b) what "auto-close" produces in the audit output
(suppress the driver / a specific label / a flag — the audit can't actually
close a closed case); (c) scope — `evaluator/prompts/judge.md` encodes it as
**Reopen-only**, but the stated goal cites **TTR/SLA**; (d) code
(`prepare_reopen_input`, cell 8) vs prompt. See `docs/open-questions.md` #1.

## Scoring

`SCORING_DICT` (cell 2 of the notebook) maps each L3 to a penalty weight:

| L3 (sample) | Weight |
|---|---|
| Did not seek confirmation if all questions were resolved | 10 |
| Did not use language correctly | 15 |
| Did not structure response | 20 |
| Did not respond in a timely manner | 25 |
| Missed expectations for follow up | 30 |
| Did not respond with empathy | 15 |
| Did not answer all questions | 20 |
| Did not tailor a solution | 25 |
| Did not exude ownership | 30 |
| Asked for information repeatedly | 10 |
| Identified a wrong root cause | 20 |
| Provided an inaccurate solution | 25 |
| Did not correct user's misunderstanding | 15 |
| Created confusion by providing unnecessary information | 10 |

- **Today only `Quality_RCA_Output` is scored** (Workflow scoring was
  intentionally removed in a code comment).
- **Threshold confirmed on May 14**: `Grade = Pass if score ≥ 90 else Fail`,
  evaluated at case level.
