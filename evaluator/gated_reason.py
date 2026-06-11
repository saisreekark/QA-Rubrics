"""Gated reasonableness scorer + curation helper.

The from-scratch reasonableness judge (`runner --judge-source regen`) judges every
framework on every regen row, but production only *runs* a framework when its gate
passes (mirror of cell-9 `process_single_row`):

    Reopen      -> Reopen_Counter > 0
    TTR         -> Case_Aging_in_Days >= 7  AND NOT KSI-excluded
    Escalation  -> Escalated == TRUE
    DSAT        -> Survey_Result == DSAT
    Quality     -> always
    Workflow    -> always

So a fair "as-deployed" reasonableness number must drop verdicts whose framework
gate is not satisfied for that case. This module joins the gate fields from the
input sheet, applies the gates, and reports per-framework Correct/Audited. It also
exposes the per-(case,framework) gated+judged table for curating the send.

Usage:
    python3 -m evaluator.gated_reason --verdicts evaluator/runs/<v>.csv \
        [--verdicts evaluator/runs/<other>.csv --label A B]
"""

from __future__ import annotations

import argparse
import subprocess

import pandas as pd
from google.oauth2.credentials import Credentials
from gspread_pandas import Spread

from . import config as cfg
from .ksi_ground import is_ksi_excluded

DRIVER_FWS = ["Reopen", "TTR", "Escalation", "DSAT"]
ALL_FWS = ["Reopen", "TTR", "Escalation", "DSAT", "Quality", "Workflow"]
M = cfg.COL_MAPPING


def _token() -> str:
    try:
        return cfg.get_oauth_token()
    except Exception:
        return subprocess.check_output(
            ["gcloud", "auth", "print-access-token"]).decode().strip()


def _creds() -> Credentials:
    return Credentials(token=_token(), token_uri="https://oauth2.googleapis.com/token",
                       quota_project_id=cfg.PROJECT_ID)


def framework_gate(row: dict, fw: str) -> bool:
    """Mirror of cell-9 process_single_row gating for one framework."""
    if fw == "Reopen":
        return pd.to_numeric(row.get(M["reopen_counter"], 0), errors="coerce") > 0
    if fw == "TTR":
        aged = pd.to_numeric(row.get(M["aging_days"], 0), errors="coerce") >= 7
        return bool(aged) and not is_ksi_excluded(row)
    if fw == "Escalation":
        return str(row.get(M["is_escalated"], "")).upper() == "TRUE"
    if fw == "DSAT":
        return str(row.get(M["survey_result"], "")).upper() == "DSAT"
    return True  # Quality / Workflow always run


def load_gate_map(case_numbers: set[str], creds=None) -> dict[str, dict[str, bool]]:
    """case_number -> {framework -> gate_passes}, from the live input tab."""
    creds = creds or _creds()
    key = M["case_number"]
    inp = Spread(cfg.SPREADSHEET_ID, creds=creds).sheet_to_df(
        sheet=cfg.INPUT_SHEET_NAME, index=None)
    inp[key] = inp[key].astype(str).str.strip()
    inp = inp[inp[key].isin(case_numbers)].drop_duplicates(subset=key, keep="last")
    out: dict[str, dict[str, bool]] = {}
    for _, r in inp.iterrows():
        rd = r.to_dict()
        out[str(r[key])] = {fw: framework_gate(rd, fw) for fw in ALL_FWS}
    return out


def gated_table(verdicts_csv: str, gate_map: dict | None = None) -> pd.DataFrame:
    """Return the verdict rows whose framework gate passes for their case,
    annotated with `gated_in` and `fired` flags."""
    v = pd.read_csv(verdicts_csv, dtype=str)
    v["case_number"] = v["case_number"].astype(str).str.strip()
    if gate_map is None:
        gate_map = load_gate_map(set(v["case_number"]))
    v["gated_in"] = v.apply(
        lambda r: gate_map.get(r["case_number"], {}).get(r["framework"], False), axis=1)
    v["fired"] = v["overall_verdict"] != "NotApplicable"
    return v[v["gated_in"]].copy()


def report(verdicts_csv: str, label: str, gate_map: dict | None = None) -> pd.DataFrame:
    g = gated_table(verdicts_csv, gate_map)
    print(f"\n=== {label} (GATED, as-deployed) ===")
    dc = dn = 0
    for fw in ALL_FWS:
        sub = g[g.framework == fw]
        fired = sub[sub.fired]
        c = (fired.overall_verdict == "Correct").sum()
        b = (fired.overall_verdict == "Borderline").sum()
        n = len(fired)
        acc = c / n * 100 if n else 0.0
        print(f"  {fw:<11} gated_in={len(sub):>3} fired={n:>3} "
              f"correct={c:>3} borderline={b:>2} acc={acc:5.1f}%")
        if fw in DRIVER_FWS:
            dc += c
            dn += n
    print(f"  DRIVERS pooled: {dc}/{dn} = {dc/dn*100 if dn else 0:.1f}%")
    return g


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--verdicts", action="append", required=True)
    p.add_argument("--label", action="append", default=None)
    args = p.parse_args()
    labels = args.label or [f"run{i}" for i in range(len(args.verdicts))]
    all_cases: set[str] = set()
    for vp in args.verdicts:
        all_cases |= set(pd.read_csv(vp, dtype=str)["case_number"].astype(str).str.strip())
    gate_map = load_gate_map(all_cases)
    for vp, lab in zip(args.verdicts, labels):
        report(vp, lab, gate_map)


if __name__ == "__main__":
    main()
