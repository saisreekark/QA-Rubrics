# Session 2026-06-09 — Phase 4: KSI TTR-exclusion filter (built) + KB-read verifier

Phase 4 work, two deliverables: **(1)** build + measure the deterministic KSI / TTR-exclusion
filter (objective #3, the doc-derived qualifier closed 2026-06-09); **(2)** verify the 4-doc KB
read to unblock prod-faithful **absolute** local scoring. Both are **built + verified offline;
the live-data half is auth-gated** — this session's shell had **no gcloud credentials** (interactive
`gcloud auth login` is owner-only), so the sheet/KB reads couldn't run here.

## 1. KSI TTR-exclusion filter — BUILT, staged-not-pushed

### The rule (doc-derived, no longer Zaidul-gated)
`docs/open-questions.md` RESOLVED 2026-06-09 #2: a closed case is **NULL for TTR** when **BOTH**

- **(a) a known-systemic marker** — a `KSI -`/`KSI:` tag in `Root_Cause_Description` (seen in prod
  data), **or** a populated `Bug_Id` whose note says the systemic fix is "under development /
  evaluation" (SOP **"Outcome 3"**: system bugs / complex technical issues, resolution "days to
  months"; `docs/kb-source/SOP_Summary.txt`), **and**
- **(b) the fix is pending a future / uncommitted resolution** (Eng/system-dependent).

It extends the already-shipped **`<7 days = null`** TTR gate (`aging_days >= 7`) and the SOP's
"WOCA pauses the SLA" logic.

### What was built (task-4.7 pattern — deterministic CODE, not a prompt)
The model can't be trusted to read structured markers (cf. the hygiene hallucination, task 4.7),
so this is a deterministic pre-LLM filter:

- **`evaluator/ksi_ground.py`** — single source of truth. `is_ksi_excluded(fields)` →
  `True` iff marker (a) is present (KSI-tag route self-sufficient; Bug_Id route requires the
  pending-Eng-fix phrase). A column **absent** from the data is "unknown", never a trigger — it
  only excludes on a positive, grounded marker (so a missing `Bug_Id`/`Root_Cause_Description`
  column can never wrongly null a real TTR defect). Plus `ksi_reason()` for audit dumps.
- **`notebook/content.ipynb` cell 9** — inline mirror (`is_ksi_excluded`, regexes, helpers) gated
  `EXCLUDE_KSI_FROM_TTR = True` (rollback `False`), wired into `process_single_row`:
  ```python
  if pd.to_numeric(row.get(COL_MAPPING['aging_days'], 0), errors='coerce') >= 7 \
          and not (EXCLUDE_KSI_FROM_TTR and is_ksi_excluded(row)):
      pipeline_tasks['out_ttr'] = ...   # KSI cases no longer trigger a TTR audit
  ```
- **`evaluator/ksi_measure.py`** — read-only profiler (no LLM): prevalence among TTR-audited
  cases, marker breakdown, sample reasons, gold-L1 composition of excluded cases, and (with
  `--scored-csv`) the TTR accuracy delta after exclusion.

Regexes: marker A = `\bksi\b | \bknown[ -]?systemic[ -]?issue\b`; marker B (Outcome 3) =
`under development/evaluation/investigation`, `fix/resolution pending`, `system bug`, `known
issue`, `days to months`, `wip`, … — **validated against the real SOP "Outcome 3" lines** (5
SOP matches incl. the literal "Outcome 3 … System bugs … days to months" line).

### Measured — LIVE (full, `python3 -m evaluator.ksi_measure`, 2026-06-09)
Input `Cases for Summary` = 17,675 rows, 34 cols (`Root_Cause_Description`, `Bug_Id`,
`Case_Aging_in_Days`, `Case_Status` all present):

- **Prevalence:** of the **2,592** cases currently TTR-audited (Closed & `aging>=7`), the filter
  excludes **116 (4.5%)**. Both routes contribute: **KSI-tag = 101, Bug_Id+pending (Outcome 3) =
  15** — the Bug_Id route adds 15 genuine exclusions beyond the tag (e.g. case `69228947`
  aging=60, `Bug_Id 493709844`; `69079591` aging=18, `Bug_Id 492454919`).
- **Gold agreement — the validation (QA-2026 TTR gold, Mar–Apr, 860 cases joined):** **46** are
  KSI-excluded. Their human primary-L1: **35 Product/Tool Gap, 8 Process Gap, 3 User Gap →
  46/46 external/upstream, ZERO People Gap.** People Gap is the agent-responsiveness driver TTR
  exists to catch; the reviewer **never** assigns it to a KSI case. ⇒ the filter excludes exactly
  the cases gold confirms are **not** agent TTR defects — **100% gold-validated correct.**
- (Earlier offline KSI-tag prevalence on the 17.6k `wf_fields.csv` dump = 153/17,667 = 0.87% of
  *all* cases, all genuine — superseded by the live aging≥7-scoped 4.5% above. Tag forms
  `[KSI]`/`KSI:`/`KSI -`/`(KSI)` all caught by `\bksi\b`.)

**Accuracy delta (Correct÷Audited) — MEASURED 2026-06-09** (fresh Mar–Apr TTR label-match,
`evaluator/runs/ksi_ttr_labelmatch.csv`, 858 verdicts, regional 2.5-pro matcher):
**TTR 17.6% (151/858) → 16.4% (133/812), Δ −1.2pp.** Of the 46 KSI cases removed, the matcher had
scored **18 Correct / 28 Incorrect** — the bot matched gold on **39%** of KSI cases, *above* its
17.6% baseline, so removing them slightly **lowers** the headline number. **This corrects an
earlier guess that it would be ≥0.**

**Interpretation (important — the KSI filter is metric-VALIDITY, not an accuracy lever):** the
−1.2pp is on the **RCA driver-match** metric, not the thing the rule targets. Zaidul's "NULL for
TTR" is about **SLA / breach accounting** (a KSI case shouldn't count as an SLA breach because its
age is an Eng dependency) — a downstream metric we don't score here. On the RCA driver-accuracy
metric the filter is slightly negative because the bot *coincidentally* identifies the external
driver (Product/Tool Gap) on 39% of KSI cases. **A real labeling nuance surfaced:** the QA-2026 TTR
gold **still audits KSI cases** (it assigns them external-cause drivers — 35 Product/Tool, 8
Process, 3 User), rather than marking them NULL/excluded. So fully removing them from the TTR run is
a **stricter** interpretation than the current gold. ⇒ **Flag for Zaidul:** should a KSI case be
(a) excluded from TTR entirely (our filter), or (b) audited but attributed to an external,
non-agent driver (what the gold does today)? Both keep it off the agent's SLA-breach count; they
differ on whether it stays in the RCA denominator. The filter is justified on the business rule as
stated; this is a labeling-consistency confirm, not a blocker.

## 2. KB-read verification — `evaluator/kb_probe.py` (auth-gated)

**Why:** the inner loop runs `--no-cache` because the 4 KB docs 403 locally, so local absolutes
are **KB-lite / delta-only**. The 2026-06-09 finding ([[reference_kb_source_docs]]) is that 2 of
the docs read via the Drive **export** API once the `x-goog-user-project: gtm-cloud-helpdesk`
quota-project header is attached — i.e. the earlier 403 may have been a **missing quota project,
not a hard Drive ACL**. If all 4 read, prod-faithful absolutes are unblocked with **no SA ACL
grant**.

**Built `evaluator/kb_probe.py`:** tests each KB doc via **both** read paths with quota-project
creds — **path A** = the pipeline's native readers (Docs API `documents().get` / Sheets API,
exactly what `SharedKnowledgeBase` uses in prod); **path B** = the Drive `files().export`
(text/plain) endpoint. Reports per-doc per-path char counts / 403s. With `--write`, if every doc
read on at least one path it assembles the snapshot → `regen --kb-snapshot` gives prod-faithful
absolutes.

```bash
export GOOGLE_OAUTH_TOKEN="$(gcloud auth print-access-token)"
python3 -m evaluator.kb_probe --write
```

### Measured — LIVE (2026-06-09), and the diagnosis was WRONG before
**The "KB 403 = Drive ACL" belief was partly a SCOPE bug.** The local `gcloud auth login` in
Cloud Shell mints a token **without the `drive` scope** (only `cloud-platform`/`compute`/…), so
the Docs/Sheets API returned `ACCESS_TOKEN_SCOPE_INSUFFICIENT` — which the 2026-06-08 probe read
as an ACL `PERMISSION_DENIED`. Re-auth with **`gcloud auth login --enable-gdrive-access`** adds
the scope. Result with the drive-scoped token (`kb_probe`, native + Drive-export paths):

| KB doc | ID | result | blocker |
|---|---|---|---|
| **SOP_Guide** | `1LJPbO…` | ✅ **85,120 chars** | was **scope-only** (now reads) |
| **Plan_Summary** | `1A3lwF…` | ✅ **5,963 chars** | was **scope-only** (now reads) |
| Terms_Conditions | `14uSCmn…` | ❌ 403 `The caller does not have permission` | **genuine ACL** |
| Do_Not_Contact_Data | `1J0VyG…` (sheet) | ❌ 403 `…does not have permission` | **genuine ACL** (PII) |

So **2/4 KB docs were never an ACL problem — just a missing scope** (the two biggest/most
substantive driver docs, SOP 85K + Plan 6K). The other **2 are real ACL blocks**: the separate
`Terms_Conditions` doc (`14uSCmn…`, distinct from Plan_Summary whose body is titled "Terms &
Conditions Summary") and the PII `Do_Not_Contact` sheet (expected to be policy-restricted).

**Consequence:** `kb_probe --write` did **not** write a snapshot (it requires all 4 for a
prod-faithful one). To unblock true absolutes we need an ACL grant on the remaining 2 — share
`Terms_Conditions` (`14uSCmn…`) + `Do_Not_Contact_Data` (`1J0VyG…`) with `saisreekark@google.com`
(DND may be PII-blocked → snapshot the 3 non-PII docs and flag the DND gap, closer to prod than
no-KB). This **supersedes** the [[reference_kb_local_access]] "share with the compute SA"
recommendation for the local-token path: the local token now reads 2/4 with scope alone; only 2
files need sharing, not all 4.

## Status / next
- **KSI filter — BUILT + MEASURED + VALIDATED, staged-not-pushed.** Fires on 4.5% of TTR-audited
  cases; 46/46 excluded gold cases are external-cause (0 People Gap) → exclusion is gold-correct.
  Cell 9 + `prompts/`-independent (it's code, no `inject_prompts`). Stage 1/2/3 untouched; drivers
  22.4% / Workflow F1 23.9% / Quality F1 39.1% unchanged (KSI changes *which* cases are TTR-audited,
  not the prompt accuracy on the rest).
- **KB read — 2/4 unblocked by scope; 2/4 need an ACL grant.** Local drive-scoped token now reads
  SOP_Guide + Plan_Summary; `Terms_Conditions` + `Do_Not_Contact` need sharing with
  `saisreekark@google.com` for a full prod-faithful snapshot. Absolutes stay delta-only until then.
- **Auth gotcha (record this):** in Cloud Shell use **`gcloud auth login --enable-gdrive-access`** —
  the plain `gcloud auth login` token lacks the `drive` scope and 403s every Docs/Sheets read.
- **Next:** (a) request the 2 ACL grants to finish the snapshot; (b) compute the exact TTR accuracy
  delta on the next window-matched TTR label-match via `ksi_measure --scored-csv`; (c) push the
  Stage-1/2/3 + KSI bundle after Sai's review.
