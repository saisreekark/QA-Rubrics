# Architecture

## End-to-end data flow

```
Vector (case mgmt)
   │ scheduler #1 (owned by Vikram — outside this project)
   ▼
PLX tables
   │ scheduler #2 (owned by Vikram — outside this project)
   ▼
Google Sheet "Tricks"  ─── input tab: "Cases for Summary"
   │
   │  rubrics-automation-run  (Vertex Colab schedule, daily 12:00 IST)
   │  runs notebook/content.ipynb
   ▼
Google Sheet "Tricks"  ─── output tab: "RCA_Analysis_Output_1"
   │
   ▼
MIS dashboard (owned by Vikram)
```

## Schedulers

Per Rishita on the May 14 Connect, the **output generator** is the only one
running today. The **input-extraction** and **code-run** schedulers still
need to be built or verified — ownership TBD.

| Role | Name | Owned by | Frequency | Notes |
|---|---|---|---|---|
| Output generator | `rubrics-automation-run` | This pod | `0 12 * * * Asia/Calcutta` | Vertex AI Colab schedule id `1105207098007879680`. 63 successful runs as of 2026-05-12. Runs the notebook end-to-end and writes the output sheet. |
| Input extraction (Vector → PLX → Sheets) | TBD | Vikram (assumed) | — | Not visible in `gtm-cloud-helpdesk`. Per Rishita, this needs to be built or verified. Ask Vikram for the project / DAG. |
| Code run | TBD | TBD | — | Per Rishita, needs to be built or verified. Map ownership in the next sync. |

See `docs/open-questions.md` #10 — full scheduler map is still an open item.

## GCP resources we own

| Resource | Value |
|---|---|
| Project | `gtm-cloud-helpdesk` (number `653428233292`) |
| Location | `us-central1` |
| Dataform repo (single-file notebook host) | `projects/gtm-cloud-helpdesk/locations/us-central1/repositories/1b4ad4ee-53ba-4541-9492-1dc89d100607` |
| Dataform repo display name | `Rubrics_finalpipeline_rh (Jan 29, 2026, 10:52:21 AM)` |
| Notebook file | `content.ipynb` (14 cells, ~278 KB) |
| Notebook runtime template | `projects/653428233292/locations/us-central1/notebookRuntimeTemplates/1413241877599092736` |
| Output bucket | `gs://analytics_genai` |
| Scheduler executor | `ukirdeankush@google.com` |

## Pipeline internals (`notebook/content.ipynb`)

Cells are numbered for `@title` headers in the notebook.

| Cell | Purpose | Key symbols |
|---|---|---|
| 0 | Markdown header (project description) | — |
| 1 | Imports, pip installs | `vertexai`, `google.cloud.aiplatform`, `gspread_pandas`, `tenacity`, `nest_asyncio` |
| 2 | Configuration | `JOB_CONFIG`, `IO_CONFIG`, `DOC_MAPPING`, `SHEET_MAPPING`, `COL_MAPPING`, `OUTPUT_COLS_TO_SAVE`, `SCORING_DICT` |
| 3 | Cloud Logging setup | `logger`, `JOB_ID` |
| 4 | Hierarchy (6 frameworks × L1/L2/L3) | `HIERARCHY_CONFIG` |
| 5 | Prompts | 18 `*_PROMPT` constants (one per agent) + `HIERARCHY_AGENT_4_PROMPT` |
| 6 | Agent config | `FRAMEWORK_CONFIGS` — maps each framework → list of agents (name, prompt, temperature, use_cache) |
| 7 | Auth | `creds = Credentials(token=...)` ← **hardcoded short-lived OAuth token** (see `docs/open-questions.md` → Engineering hygiene — Sai owns) |
| 8 | Helpers | `parse_closure_timestamps`, `parse_transcript_messages`, `prepare_reopen_input`, `ModelRegistry`, `SharedKnowledgeBase`, `DeltaManager.identify_delta` |
| 9 | Retry wrapper | `@retry(...)` around `generate_content` for `ResourceExhausted`, `ServiceUnavailable`, `InternalServerError`, parsing errors. 4 attempts, exponential backoff. |
| 10 | Main execution | `run_full_job` — load sheet → delta → restore valid history → chunk loop (50) → async per-row → L3 scoring → save chunk → repeat. |
| 11 | Entry point | `await run_full_job()` |
| 12–13 | Empty | — |

## Per-case processing

For each new/changed case in the delta:

1. Build the per-framework input (transcript + metadata).
2. For each framework, run each agent in sequence (most are 2–3 agents;
   Quality has 5). The final agent of each framework has `use_cache: True` —
   confirmed on May 14 to be **Vertex Context Caching**, preloading the
   static SOP / rule corpus to cut tokens, speed up runtime, and reduce
   hallucinations. Treat the cached content (SOP_Guide, Terms_Conditions,
   Plan_Summary) as a stable input; don't bust the cache casually.
3. Parse each agent's JSON output (keys `driver_1`…`driver_5`).
4. Compute `L3_Score` by summing `SCORING_DICT[L3_name]` across drivers
   (currently only **Quality** outputs are scored; **Workflow** scoring was
   intentionally removed in a code comment).
5. Set `Grade = 'Fail' if score < 90 else 'Pass'`.
6. Write the chunk back to the output sheet via `gspread_pandas.Spread`.

## Concurrency & rate limits

- `asyncio.Semaphore(50)` caps in-flight Gemini calls.
- `save_chunk_size = 50` — output sheet is appended in 50-row blocks.
- Retry: exponential backoff (`multiplier=2, min=2, max=30`), 4 attempts.

## Active: Tricks → BigQuery migration

Moved from "parked" to **active scoping** on May 14 — no longer waiting on
a compliance trigger. Pooja is sending **SQL Miner + Colab** path links
(similar pattern to past Voice-of-Seller work).

The target swaps `gspread_pandas.Spread` reads/writes in cell 10 for
BigQuery `SELECT` / `INSERT`. Keep `OUTPUT_COLS_TO_SAVE` exactly identical
so the (parked) dashboard contract stays stable once Vikram unparks it.

Sequencing: scope the BigQuery path **in parallel** with prompt accuracy
work, not before. Accuracy still gates the June demo.
