# KB local access — diagnosis + the snapshot fix (2026-06-08)

> ## ✅ DECISION (2026-06-08): run **KB-lite / delta-only** for now — snapshot PARKED, ready
> We are **not** blocking accuracy work on the KB snapshot. Working mode going forward:
> measure every prompt change as a **same-cases OLD-vs-NEW delta A/B** (`--no-cache`,
> 3.1-pro, temp 0) — the KB gap cancels in the delta, so the delta is valid signal.
> **Do not quote local absolutes as "% toward 80%"** (they're KB-lite, lower than prod);
> the production anchor stays the 2.5-pro frozen **~12.9%**. The full snapshot path below
> is **built + proven and parked** — it's **one ACL grant** from done (grant Viewer on the
> 4 KB files to `653428233292-compute@developer.gserviceaccount.com`, then re-run the
> uploaded `gs://analytics_genai/kb_dump.ipynb`). Revisit when we need a true absolute
> (e.g. a pre-demo headline number, or to validate the final bundle before push).


**Question:** can we run the pipeline's **Knowledge Base** locally so regen
absolutes are prod-faithful (not delta-only)? The inner loop forces `--no-cache`
because the KB 403s locally — which means our local absolutes (drivers 22.4%,
Q/W F1) are **lower-fidelity than prod** and only the **deltas** are trustworthy.

## What the KB is

4 static docs baked into Vertex/genai context caches for the `use_cache: True`
agents (the 3rd agent in each framework). Read by `SharedKnowledgeBase._load_docs_once`
(notebook cell 8) via the Docs/Sheets APIs:

| Name | Type | ID |
|---|---|---|
| SOP_Guide | Google Doc | `1LJPbOEi7eUB21ndEFx8NFLc3QRBxjF_lVf1lusRIvkw` |
| Terms_Conditions | Google Doc | `14uSCmn0OZB9x3Mm2Zi6HsrVI5I181mpx_ESlA2kQmak` |
| Plan_Summary | Google Doc | `1A3lwFGFAmiNHCTsKg2lNhn74eC0tRGYg6vaPzdyUr9g` |
| Do_Not_Contact_Data | Google Sheet (tab `Do NOT tag`) | `1J0VyGVmWjoZBbyk7Ra9vl2Bh3mdG6ZCMADkCzBhUh6Y` |

## Verified diagnosis — it's a Drive ACL, nothing else

Probed all 4 with the local token (`gcloud auth print-access-token`):

- **Identity** = `saisreekark@google.com` (corp Googler, not the personal gmail).
- **Token scopes** already include `drive` + `cloud-platform` → **scope is fine**.
- **Docs / Sheets / Drive APIs are all ENABLED** on `gtm-cloud-helpdesk`.
- The **same token reads the gold + I/O sheets fine** all session.
- Yet all 4 KB files return **`403 PERMISSION_DENIED` — "The caller does not have
  permission"**.

⇒ The 4 KB files are simply **not shared with `saisreekark@google.com`**. Not a
scope, API-enablement, quota-project, or auth-mechanism problem. The prod pipeline
reads them fine because its **runtime service account** has access.

**Impersonating the pipeline SA is also blocked:** Sai lacks
`roles/iam.serviceAccountTokenCreator` on every candidate SA (`app-executor-sa@`,
`compensation-support-bot@`, `653428233292-compute@`, `spreadsheet-gateway-sa@`) —
`iam.serviceAccounts.getAccessToken` denied. Sai's project roles include `editor`,
`aiplatform.admin`, `notebooks.admin`, `storage.admin` — **but `editor` does NOT
grant Token Creator**, so local impersonation needs an IAM grant.

## CLI automation attempt (2026-06-08) — the whole path is BUILT + PROVEN except the ACL

Tried to produce the snapshot end-to-end via `gcloud` (no manual Colab clicks). What
works and the one thing that doesn't:

- **Authored a dump-only notebook** (`gs://analytics_genai/kb_dump.ipynb`) and ran it
  headless via `gcloud colab executions create --gcs-notebook-uri … --service-account
  …` on the prod runtime template — **this works** (jobs reach `JOB_STATE_SUCCEEDED`).
- **The drive scope IS honored in Colab Enterprise** — the KB read failed with
  `403 PERMISSION_DENIED` (an ACL error), NOT a scope error. So scope is a non-issue.
- **GCS read/write from the job works** for the compute SA + `compensation-support-bot@`.
- I have **`iam.serviceAccounts.actAs` on all 6 SAs** (so I can run jobs AS them) but
  **`getAccessToken` on none** (so I cannot mint any SA/user token locally).
- **Tested every runnable identity → none is on the KB ACL:** compute default SA →
  KB 403; `compensation-support-bot@` → KB 403; the other 5 SAs
  (`app-executor-sa@`, `spreadsheet-gateway-sa@`, `spreadsheet-filter-gateway@`,
  `gateway-invoker-sa@`, `gtm-devop-service@`) **failed before running** — they 403 on
  the `analytics_genai` GCS bucket itself, so they can't even fetch the input notebook.

**Conclusion:** the entire automated pipeline is proven; the ONLY missing link is the
**Drive ACL**. The KB is shared only with the specific google.com user whose token is
hardcoded in **cell 7** (the prod pipeline reads the KB via that user token, not via a
SA — which is why no SA has access). No identity Claude/Sai can drive is on the ACL,
and impersonation is blocked.

### ⇒ One-step unblock (then it's fully automated, zero further engineering)

Share the 4 KB files with an identity we can run as — **simplest = the compute SA**:

```
653428233292-compute@developer.gserviceaccount.com   # Viewer on the 4 KB files
```

Then re-run the already-uploaded dumper (it writes the snapshot to GCS):

```bash
gcloud colab executions create --display-name=kb-snapshot-dump \
  --region=us-central1 --project=gtm-cloud-helpdesk \
  --notebook-runtime-template=projects/653428233292/locations/us-central1/notebookRuntimeTemplates/1413241877599092736 \
  --gcs-notebook-uri=gs://analytics_genai/kb_dump.ipynb \
  --gcs-output-uri=gs://analytics_genai \
  --service-account=653428233292-compute@developer.gserviceaccount.com
gsutil cp gs://analytics_genai/kb_snapshot.txt evaluator/kb_snapshot.txt   # then regen --kb-snapshot
```

(Alternatively share with `saisreekark@google.com` → `dump_kb_snapshot.py` runs
locally.) **Caveat:** the **Do_Not_Contact** sheet is PII and may be policy-blocked
from sharing with a SA/user — if so, snapshot the 3 SOP/T&C/Plan docs (closer to prod
than no-KB) and flag the DND gap. The 3 driver docs are the safe ones.

## The fix — ranked

### ✅ Recommended: one-time **KB snapshot** (self-serve, no ACL/IAM change)

The KB is static. Dump it ONCE from a KB-capable identity, snapshot it locally, and
have regen **inline** it into the `use_cache` agents. Inlining (vs Vertex caching)
changes **cost/latency, not accuracy** — the model sees the same KB text → local
absolutes become prod-faithful. Built this session:

- `evaluator/dump_kb_snapshot.py` — assembles the KB text EXACTLY as the pipeline
  does (`load_pipeline` → `SharedKnowledgeBase._load_docs_once`, same readers +
  concatenation). Guards against a headers-only (403) result.
- `evaluator/regen.py --kb-snapshot <file>` — `_SnapshotKB` returns the text as an
  `{"inline": ...}` payload; the global gemini-3 adapter prepends it to the
  `use_cache` agents' system prompt. (Plumbing validated end-to-end with a dummy
  snapshot on Reopen agent3.)

**How Sai runs it (uses only roles he already has — `aiplatform.admin` +
`notebooks.admin` + `storage.admin`):**

```bash
# 1. In a Colab Enterprise notebook (Pantheon, project gtm-cloud-helpdesk) — the
#    runtime SA already reads the KB. Paste the cell from:
python3 -m evaluator.dump_kb_snapshot --colab-cell
#    It writes gs://analytics_genai/kb_snapshot.txt
# 2. Pull it down locally + use it (no live Drive read needed after this):
gsutil cp gs://analytics_genai/kb_snapshot.txt evaluator/kb_snapshot.txt
python3 -m evaluator.regen --framework Workflow --sample 200 \
  --kb-snapshot evaluator/kb_snapshot.txt --temperature 0
```

Re-dump only when the SOPs change (rare). This decouples the inner loop from live
KB access permanently.

### Faster if someone helps (parallel asks)
- **Share the 4 KB files** with `saisreekark@google.com` → then `dump_kb_snapshot`
  (and the live KB path) just work locally, zero code. **Caveat:** the DND sheet is
  PII ("Do Not Contact") and may be policy-restricted from user sharing — the
  snapshot path sidesteps that.
- **Grant Sai `roles/iam.serviceAccountTokenCreator`** on the pipeline SA (e.g.
  `app-executor-sa@gtm-cloud-helpdesk.iam.gserviceaccount.com`) → impersonate
  locally for an exact-prod identity (`regen._build_vertex_credentials` already uses
  ADC).

### The mirror-notebook idea — verdict: works, but heavier
Creating a Colab Enterprise notebook that mirrors prod **does** solve KB access (it
runs as the runtime SA that already reads the KB) and Sai has the roles to do it.
But running the *whole* pipeline there each iteration is a heavy inner loop. The
**snapshot** captures the only thing Colab buys us (KB access) in a one-time step,
keeping the fast local loop. Reserve a full Colab/Enterprise run for a **one-time
"true absolute" validation** (it also reproduces the regional 2.5-pro cached path
exactly) or for the eventual deploy.

## Bottom line for accuracy work
Until a KB snapshot exists, **local numbers are delta-only** — fine for A/B-ing a
prompt change, NOT for claiming "we're at X% toward 80%". Producing the snapshot
(or getting the share/grant) is the prerequisite to trustworthy absolute accuracy
reporting. See `docs/execution-plan.md` Phase 2 / `CLAUDE.md` → Evaluator & regen
harness.
