r"""Paste-ready Colab Enterprise driver: run the tuned pipeline on 500 cases with REAL KB.

WHY: the local sandbox network drops intermittently and kills the long regen. Colab
Enterprise (Pantheon, project gtm-cloud-helpdesk) has a stable network AND its runtime
SA can read the 4 real KB docs (SOP/T&C/Plan/DND) — fully prod-faithful, no snapshot.

HOW TO USE
  1. Open notebook/content.ipynb in Colab Enterprise (gtm-cloud-helpdesk) — or the live
     Dataform notebook. Run ALL cells above (defines process_single_row, SharedKnowledgeBase,
     FRAMEWORK_CONFIGS, JOB_CONFIG, DOC_MAPPING, SHEET_MAPPING, COL_MAPPING, IO_CONFIG, and
     the gemini-3.1 global path). This includes the tuned Stage-1/2/3 prompts + the Reopen
     Completeness rule + cell-9 grounding (KSI / TTR>=7 / hygiene-suppress).
  2. Paste the CELL below into a new cell and run it (use top-level `await`, Colab supports it).
  3. Back locally:  gsutil cp gs://analytics_genai/curate_prod_500.csv evaluator/runs/
     then: ground_hygiene_csv (Workflow justification fix) -> merge -> runner --judge-source
     regen -> gated_reason -> export_send.

NOTE: the Workflow justification-precision fix is applied locally as a deterministic
post-step (evaluator/ground_hygiene_csv.py), so it does NOT need to be in the notebook.
"""

COLAB_CELL = r'''
# === Tuned pipeline, 500 prod-faithful cases (run AFTER all content.ipynb cells) ===
import asyncio, json, datetime, subprocess
import pandas as pd
from google.auth import default as _adc
from gspread_pandas import Spread

creds, _ = _adc(scopes=["https://www.googleapis.com/auth/drive",
                        "https://www.googleapis.com/auth/cloud-platform"])

# 1) 500 recent Closed cases (Mar–Apr 2026) from the input tab
io = IO_CONFIG
key = COL_MAPPING["case_number"]
inp = Spread(io["spreadsheet_id"], creds=creds).sheet_to_df(sheet=io["input_sheet_name"], index=None)
inp[key] = inp[key].astype(str).str.strip()
closed = inp[inp[COL_MAPPING["case_status"]].astype(str).str.strip().str.lower() == "closed"]
cd = COL_MAPPING.get("created_date", "Created_date")
mask = closed[cd].astype(str).str.startswith(("2026-03", "2026-04"))
closed = closed[mask] if mask.any() else closed
rows = (closed.drop_duplicates(subset=key)
        .sample(n=min(500, len(closed)), random_state=42).to_dict("records"))
print("cases to run:", len(rows))

# 2) REAL KB caches (Colab runtime SA can read the 4 docs)
kb = SharedKnowledgeBase(DOC_MAPPING, SHEET_MAPPING, creds)
kb.create_agent_caches(FRAMEWORK_CONFIGS, JOB_CONFIG["agent_model"])

# 3) run the tuned pipeline (cell-9 gates + grounding) per case
sem = asyncio.Semaphore(16)
results = await asyncio.gather(*(process_single_row(r, sem, kb) for r in rows))  # top-level await

# 4) assemble the 6 framework outputs -> CSV -> GCS
outcol = {"out_reopen": "Reopen_RCA_Output", "out_ttr": "TTR_RCA_Output",
          "out_escalation": "Escalation_RCA_Output", "out_dsat": "DSAT_RCA_Output",
          "out_quality": "Quality_RCA_Output", "out_workflow": "Workflow_RCA_Output"}
recs = []
for r, res in zip(rows, results):
    rec = {"Case_Number": str(r[key])}
    for k, col in outcol.items():
        v = res.get(k)
        rec[col] = "" if v is None else (v if isinstance(v, str) else json.dumps(v))
    recs.append(rec)
pd.DataFrame(recs).to_csv("/tmp/curate_prod_500.csv", index=False)
subprocess.run(["gsutil", "cp", "/tmp/curate_prod_500.csv",
                "gs://analytics_genai/curate_prod_500.csv"], check=True)
print("WROTE gs://analytics_genai/curate_prod_500.csv  (gsutil cp it down locally)")
'''

if __name__ == "__main__":
    print(COLAB_CELL)
