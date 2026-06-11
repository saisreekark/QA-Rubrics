"""Export a curated case set into the dev QA-review send format.

Reproduces the `RCA_Analysis_Output_1` tab layout from the dev send sheet
(1G3p6oKc..., 40 columns, two header rows): case metadata + the six
`*_RCA_Output` columns + bot-side score/grade/timestamp, then BLANK
per-framework QA-reviewer blocks (QA Validations / Driver 1..3 / Comments)
for the QA team to fill in.

Also writes a `Cases for Summary` tab with the full input rows for the
curated cases so reviewers can read the case while grading.

Inputs:
  --regen-csv    tuned-bot predictions (Case_Number + *_RCA_Output cols)
  --cases-file   optional newline-separated case numbers to include (the
                 curated set). Default: every case in the regen CSV.
  --out          output .xlsx path.

Usage:
  python3 -m evaluator.export_send --regen-csv evaluator/runs/<f>.csv \
      --cases-file evaluator/runs/curated_cases.txt \
      --out evaluator/runs/QA_send_<stamp>.xlsx
"""

from __future__ import annotations

import argparse
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from google.oauth2.credentials import Credentials
from gspread_pandas import Spread
from openpyxl import Workbook

from . import config as cfg
from .gated_reason import framework_gate

# The two header rows of RCA_Analysis_Output_1, col-for-col (40 cols).
ROW0 = ["", "", "", "",
        "Reopen_RCA_Output", "TTR_RCA_Output", "Escalation_RCA_Output",
        "DSAT_RCA_Output", "Quality_RCA_Output", "Workflow_RCA_Output",
        "", "", "", "",
        "Reopen", "", "", "",
        "TTR", "", "", "",
        "Escalation", "", "", "",
        "DSAT", "", "", "",
        "Quality", "", "", "", "", "",
        "Workfow Adherence / Compliance", "", "", ""]
ROW1 = ["Case_Number", "Case_Status", "Created_date", "Issue_Category",
        "Reopen_RCA_Output", "TTR_RCA_Output", "Escalation_RCA_Output",
        "DSAT_RCA_Output", "Quality_RCA_Output", "Workflow_RCA_Output",
        "L3_Score", "Grade", "RCA_Generated_At", "QA Reviewer",
        "QA Validations", "Driver 1", "Driver 2", "Comments",
        "QA Validations", "Driver 1", "Driver 2", "Comments",
        "QA Validations", "Driver 1", "Driver 2", "Comments",
        "QA Validations", "Driver 1", "Driver 2", "Comments",
        "QA Validations", "Driver 1", "Driver 2", "Driver 3", "", "Comments",
        "QA Validations", "Driver 1", "Driver 2", "Comments"]

OUT_COLS = {  # framework -> its *_RCA_Output column (and the send-sheet col index)
    "Reopen": (cfg.FRAMEWORK_TO_OUTPUT_COL["Reopen"], 4),
    "TTR": (cfg.FRAMEWORK_TO_OUTPUT_COL["TTR"], 5),
    "Escalation": (cfg.FRAMEWORK_TO_OUTPUT_COL["Escalation"], 6),
    "DSAT": (cfg.FRAMEWORK_TO_OUTPUT_COL["DSAT"], 7),
    "Quality": (cfg.FRAMEWORK_TO_OUTPUT_COL["Quality"], 8),
    "Workflow": (cfg.FRAMEWORK_TO_OUTPUT_COL["Workflow"], 9),
}
KEY = cfg.COL_MAPPING["case_number"]


def _creds() -> Credentials:
    try:
        tok = cfg.get_oauth_token()
    except Exception:
        tok = subprocess.check_output(
            ["gcloud", "auth", "print-access-token"]).decode().strip()
    return Credentials(token=tok, token_uri="https://oauth2.googleapis.com/token",
                       quota_project_id=cfg.PROJECT_ID)


def build(regen_csv: Path, cases: set[str] | None, out: Path) -> int:
    creds = _creds()
    regen = pd.read_csv(regen_csv, dtype=str)
    regen[KEY] = regen[KEY].astype(str).str.strip()
    if cases is not None:
        regen = regen[regen[KEY].isin(cases)]
    regen = regen.drop_duplicates(subset=KEY, keep="last")
    case_set = set(regen[KEY])

    inp = Spread(cfg.SPREADSHEET_ID, creds=creds).sheet_to_df(
        sheet=cfg.INPUT_SHEET_NAME, index=None)
    inp[KEY] = inp[KEY].astype(str).str.strip()
    inp = inp[inp[KEY].isin(case_set)].drop_duplicates(subset=KEY, keep="last")
    meta = inp.set_index(KEY)

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    wb = Workbook()

    # --- RCA_Analysis_Output_1 ---
    ws = wb.active
    ws.title = "RCA_Analysis_Output_1"
    ws.append(ROW0)
    ws.append(ROW1)
    for _, r in regen.iterrows():
        cn = r[KEY]
        m = meta.loc[cn] if cn in meta.index else {}
        row = [""] * 40
        row[0] = cn
        row[1] = str(m.get("Case_Status", "")) if hasattr(m, "get") else ""
        row[2] = str(m.get("Created_date", "")) if hasattr(m, "get") else ""
        row[3] = str(m.get("Issue_Category", "")) if hasattr(m, "get") else ""
        mrow = m.to_dict() if hasattr(m, "to_dict") else {}
        for fw, (col, idx) in OUT_COLS.items():
            # Mirror production gating: blank a framework's output when its gate
            # fails for this case (Reopen/TTR/Escalation/DSAT). Quality/Workflow
            # always run. Prevents shipping over-fired (e.g. Reopen on a
            # never-reopened case) drivers the QA team would rightly flag.
            if not framework_gate(mrow, fw):
                row[idx] = ""
                continue
            val = r.get(col, "")
            row[idx] = "" if pd.isna(val) else str(val)
        row[12] = stamp  # RCA_Generated_At; L3_Score/Grade left blank (QA grades)
        ws.append(row)

    # --- Cases for Summary (input context for reviewers) ---
    ws2 = wb.create_sheet("Cases for Summary")
    ws2.append(list(inp.columns))
    for _, r in inp.iterrows():
        ws2.append(["" if pd.isna(v) else str(v) for v in r.tolist()])

    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    return len(regen)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--regen-csv", type=Path, required=True)
    p.add_argument("--cases-file", type=Path, default=None)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    cases = None
    if args.cases_file:
        cases = {ln.strip() for ln in args.cases_file.read_text().splitlines() if ln.strip()}
    n = build(args.regen_csv, cases, args.out)
    print(f"Wrote {n} cases → {args.out}")


if __name__ == "__main__":
    main()
