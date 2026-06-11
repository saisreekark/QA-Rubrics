"""Post-filter a Workflow regen CSV with deterministic hygiene grounding (task 4.7).

Reads a regen CSV (``Case_Number``, ``Workflow_RCA_Output``), joins the actual case
hygiene fields, applies ``hygiene_ground.ground_workflow_output`` to suppress
hallucinated ``Missing vector case hygiene fields`` firings, and writes a grounded CSV
of identical shape so ``runner --gold-source regen`` scores it unchanged. The grounding
is deterministic, so OLD-vs-grounded is a clean same-cases A/B with no model re-run.

Field source (in priority order):
  --fields-csv <f>   read the hygiene fields from a cached CSV (offline, no token)
  (else)             read live from the input sheet (needs GOOGLE_OAUTH_TOKEN)
Use --dump-fields <f> to pull the fields once with a token and reuse them offline.

Examples
--------
    export GOOGLE_OAUTH_TOKEN="$(gcloud auth print-access-token)"
    python3 -m evaluator.ground_hygiene_csv --regen-csv runs/regenOLD_W.csv \
        --dump-fields runs/wf_fields.csv --out runs/regenGND_W.csv
    # offline re-run from the cached fields:
    python3 -m evaluator.ground_hygiene_csv --regen-csv runs/regenOLD_W.csv \
        --fields-csv runs/wf_fields.csv --out runs/regenGND_W.csv
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import pandas as pd

from . import config as cfg
from . import hygiene_ground as hg

# Columns we pull from the input sheet to ground the hygiene rule.
_FIELD_COLS = [
    hg.F_CASE_STATUS, hg.F_ROOT_CAUSE, hg.F_ROOT_CAUSE_DESC, hg.F_NEXT_STEPS,
    hg.F_ISSUE_TYPE, "Issue_Category", *hg.F_COMP_EXTRA,
]
_CASE_COL = cfg.COL_MAPPING["case_number"]
_OUT_COL = cfg.FRAMEWORK_TO_OUTPUT_COL["Workflow"]


def _load_fields_from_sheet() -> pd.DataFrame:
    """Read Case_Number + the hygiene fields from the live input sheet."""
    import vertexai  # noqa: F401  (kept symmetric with runner; not strictly needed)
    from google.oauth2.credentials import Credentials
    from gspread_pandas import Spread

    creds = Credentials(
        token=cfg.get_oauth_token(),
        token_uri="https://oauth2.googleapis.com/token",
        quota_project_id=cfg.PROJECT_ID,
    )
    df = Spread(cfg.SPREADSHEET_ID, creds=creds).sheet_to_df(
        sheet=cfg.INPUT_SHEET_NAME, index=None)
    present = [c for c in _FIELD_COLS if c in df.columns]
    keep = [_CASE_COL, *present]
    out = df[keep].copy()
    out[_CASE_COL] = out[_CASE_COL].astype(str).str.strip()
    return out.drop_duplicates(subset=_CASE_COL, keep="last")


def _fields_map(fields_df: pd.DataFrame) -> dict[str, dict]:
    return {
        str(r[_CASE_COL]).strip(): {k: r.get(k) for k in fields_df.columns if k != _CASE_COL}
        for _, r in fields_df.iterrows()
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Deterministic Workflow hygiene grounding")
    p.add_argument("--regen-csv", type=Path, required=True, help="Input Workflow regen CSV.")
    p.add_argument("--out", type=Path, required=True, help="Grounded output CSV (same shape).")
    p.add_argument("--fields-csv", type=Path, default=None,
                   help="Cached hygiene fields CSV (offline; else read the live sheet).")
    p.add_argument("--dump-fields", type=Path, default=None,
                   help="Also write the pulled hygiene fields here for offline reuse.")
    p.add_argument("--exclude-next-steps", action="store_true",
                   help="Root_Cause/RCD-only variant (analysis): do NOT count empty "
                        "Next_Steps as a violation. Default = literal rule-9 (the "
                        "gold-aligned, F1-improving grounding).")
    args = p.parse_args()
    include_next_steps = not args.exclude_next_steps

    if args.fields_csv:
        fields_df = pd.read_csv(args.fields_csv, dtype=str)
        fields_df[_CASE_COL] = fields_df[_CASE_COL].astype(str).str.strip()
    else:
        fields_df = _load_fields_from_sheet()
    if args.dump_fields:
        fields_df.to_csv(args.dump_fields, index=False)
        print(f"dumped {len(fields_df)} field rows → {args.dump_fields}")

    fmap = _fields_map(fields_df)
    regen = pd.read_csv(args.regen_csv, dtype=str)

    n_hygiene = n_suppressed = n_no_fields = 0
    rows_out = []
    for _, r in regen.iterrows():
        case = str(r[_CASE_COL]).strip()
        bot = r.get(_OUT_COL)
        bot = "" if bot is None or (isinstance(bot, float) and pd.isna(bot)) else str(bot)
        had_hygiene = hg.HYGIENE_L3.lower() in bot.lower()
        n_hygiene += int(had_hygiene)
        fields = fmap.get(case)
        if fields is None:
            n_no_fields += int(had_hygiene)
            new = bot  # no grounding possible → leave as-is
        else:
            new, suppressed = hg.ground_workflow_output(
                bot, fields, include_next_steps=include_next_steps)
            n_suppressed += int(suppressed)
        rows_out.append({_CASE_COL: case, _OUT_COL: new})

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[_CASE_COL, _OUT_COL])
        w.writeheader()
        w.writerows(rows_out)

    kept = n_hygiene - n_suppressed
    print(f"cases={len(regen)}  hygiene firings={n_hygiene}  "
          f"suppressed={n_suppressed}  kept={kept}  no-fields={n_no_fields}")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
