"""Merge a full 6-framework regen CSV with a Workflow-justification-fixed CSV.

Replaces the Workflow_RCA_Output column of <full> with the fixed values from
<wffix> (produced by ground_hygiene_csv). Output keeps all 6 framework columns
so export_send / runner --judge-source regen consume it unchanged.
"""
import sys
import pandas as pd
from evaluator import config as cfg

full_path, wffix_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
KEY = cfg.COL_MAPPING["case_number"]
WF = cfg.FRAMEWORK_TO_OUTPUT_COL["Workflow"]

full = pd.read_csv(full_path, dtype=str)
wf = pd.read_csv(wffix_path, dtype=str)[[KEY, WF]].rename(columns={WF: "_wffix"})
full[KEY] = full[KEY].astype(str).str.strip()
wf[KEY] = wf[KEY].astype(str).str.strip()
m = full.merge(wf, on=KEY, how="left")
# use fixed Workflow where available, else keep original
m[WF] = m["_wffix"].where(m["_wffix"].notna(), m[WF])
m = m.drop(columns=["_wffix"])
m.to_csv(out_path, index=False)
print(f"merged {len(m)} rows, cols={list(m.columns)} -> {out_path}")
