"""Audit the QA-2026 gold case set — read-only, no labels written.

Answers "is the gold good, and how good?" before we trust any accuracy number
measured against it. Reuses the same loaders as the evaluator so the audit sees
exactly the rows the matcher would.

For each driver framework (TTR / Reopen / Escalation / DSAT) it reports:
  1. Coverage by `closed_date` month (all of 2026) — does the gold extend past
     the Feb/Mar window the evaluator is currently locked to?
  2. Label-quality defects — duplicate case numbers, blank L1 / L2&L3, reviewer
     coverage, placeholder (non-real) case numbers, and L1 values that are NOT
     in the rubric (`HIERARCHY_CONFIG`).
  3. New-taxonomy presence by month — how many rows carry the updated drivers
     (`Product/Tools Gap` L1, `Quarter Freeze / YoY` anywhere) per month. Shows
     which months are safe to widen the window across.
  4. Join health — what fraction of gold cases actually have (a) a live bot
     prediction and (b) a regen input row. A low join rate silently shrinks the
     effective sample.

Run:  GOOGLE_OAUTH_TOKEN="$(gcloud auth print-access-token)" python3 -m evaluator.gold_audit
"""

from __future__ import annotations

import argparse
import re
from collections import Counter

import pandas as pd
from gspread_pandas import Spread

from . import config as cfg
from . import gold_dump, hierarchy
from .runner import _build_credentials

DRIVER_FRAMEWORKS = ("TTR", "Reopen", "Escalation", "DSAT")
# New-taxonomy markers (normalised, lower-case) we look for in the gold labels.
PRODUCT_TOOLS_L1 = "product/tool gap"  # gold_dump.normalize_l1 folds the variants here
QUARTER_FREEZE_RE = re.compile(r"quarter\s*freeze|yoy|year[\s-]*over[\s-]*year", re.I)


def _valid_l1s(framework: str) -> set[str]:
    """Normalised L1 labels that exist in HIERARCHY_CONFIG for this framework."""
    subtree = hierarchy.load_hierarchy(framework)
    return {gold_dump.normalize_l1(l1) for l1 in subtree}


def _month(series: pd.Series) -> pd.Series:
    """closed_date string -> 'YYYY-MM' period string ('unknown' if unparseable)."""
    dt = pd.to_datetime(series.astype(str).str.strip(), errors="coerce")
    return dt.dt.to_period("M").astype(str).replace("NaT", "unknown")


def _print_framework(name: str, df: pd.DataFrame) -> None:
    """df is the raw driver-tab subset for one framework (pre-filtering)."""
    c = cfg.QA2026_LABEL_COLS
    case = df[c["case_number"]].astype(str).str.strip()
    l1 = df[c["gold_l1"]].astype(str).str.strip()
    l2l3 = df.get(c["gold_l2l3"], pd.Series([""] * len(df))).astype(str).str.strip()
    reviewer = df.get(c["reviewer"], pd.Series([""] * len(df))).astype(str).str.strip()
    month = _month(df[c["closed_date"]]) if c["closed_date"] in df.columns else pd.Series(["unknown"] * len(df))

    real = gold_dump._is_real_case(case)
    has_l1 = l1 != ""
    keep = real & has_l1  # the rows load_labels_2026 would actually keep
    valid_l1 = _valid_l1s(name)
    l1_norm = l1.map(gold_dump.normalize_l1)
    off_taxonomy = keep & ~l1_norm.isin(valid_l1)

    print(f"\n{'=' * 78}\n{name}  —  {len(df)} raw rows, {int(keep.sum())} usable "
          f"(real case # + non-blank L1)\n{'=' * 78}")

    # 1. Coverage by month (usable rows only)
    print("  Coverage by closed_date month (usable rows):")
    cov = Counter(month[keep])
    for m in sorted(cov):
        print(f"    {m:>10} : {cov[m]:>4}")

    # 2. Label-quality defects
    n_dup = int(case[keep].duplicated().sum())
    n_blank_l1 = int((real & ~has_l1).sum())
    n_blank_l2l3 = int((keep & (l2l3 == "")).sum())
    n_placeholder = int((~real).sum())
    n_no_reviewer = int((keep & (reviewer == "")).sum())
    print("  Label-quality defects:")
    print(f"    duplicate case numbers (kept)   : {n_dup}")
    print(f"    blank L1 (dropped)              : {n_blank_l1}")
    print(f"    blank L2&L3 (kept)              : {n_blank_l2l3}")
    print(f"    placeholder / non-real case #   : {n_placeholder}")
    print(f"    no quality_reviewer             : {n_no_reviewer}")
    print(f"    L1 not in HIERARCHY_CONFIG      : {int(off_taxonomy.sum())}")
    if off_taxonomy.any():
        bad = Counter(l1[off_taxonomy])
        for label, n in bad.most_common(8):
            print(f"        {n:>3}×  {label!r}")

    # 3. New-taxonomy presence by month
    combined = (l1 + " " + l2l3)
    is_pt = keep & (l1_norm == PRODUCT_TOOLS_L1)
    is_qf = keep & combined.str.contains(QUARTER_FREEZE_RE)
    print(f"  New-taxonomy presence (usable rows): "
          f"Product/Tools Gap L1 = {int(is_pt.sum())}, "
          f"Quarter-Freeze/YoY (any level) = {int(is_qf.sum())}")
    by_month = pd.DataFrame({"month": month, "pt": is_pt, "qf": is_qf})[keep]
    if int(is_pt.sum()) or int(is_qf.sum()):
        for m in sorted(by_month["month"].unique()):
            sub = by_month[by_month["month"] == m]
            if sub["pt"].any() or sub["qf"].any():
                print(f"    {m:>10} : Product/Tools={int(sub['pt'].sum())}  "
                      f"QuarterFreeze={int(sub['qf'].sum())}")


def _join_health(creds, driver: pd.DataFrame) -> None:
    """Per-framework: % of usable gold cases that have a live bot pred / regen input."""
    c = cfg.QA2026_LABEL_COLS
    print(f"\n{'=' * 78}\nJOIN HEALTH (usable gold cases that have a bot pred / regen input)\n{'=' * 78}")

    # Live output tab: a case "has a prediction" if its framework column is non-blank.
    live = Spread(cfg.LIVE_OUTPUT_SPREADSHEET_ID, creds=creds).sheet_to_df(
        sheet=cfg.LIVE_OUTPUT_TAB, index=None)
    live["_case"] = live.get("Case_Number", pd.Series(dtype=str)).astype(str).str.strip()

    # Regen inputs come from the I/O input tab (`Cases for Summary`).
    inp = Spread(cfg.SPREADSHEET_ID, creds=creds).sheet_to_df(
        sheet=cfg.INPUT_SHEET_NAME, index=None)
    input_cases = set(inp[cfg.COL_MAPPING["case_number"]].astype(str).str.strip())

    stage_for_fw = {v: k for k, v in cfg.QA2026_STAGE_MAP.items()}
    for fw in DRIVER_FRAMEWORKS:
        sub = driver[driver[c["stage"]].astype(str).str.strip() == stage_for_fw[fw]]
        case = sub[c["case_number"]].astype(str).str.strip()
        l1 = sub[c["gold_l1"]].astype(str).str.strip()
        gold_cases = set(case[gold_dump._is_real_case(case) & (l1 != "")])
        n = len(gold_cases)
        bot_col = cfg.FRAMEWORK_TO_OUTPUT_COL[fw]
        live_has = set(live.loc[live[bot_col].astype(str).str.strip() != "", "_case"]) if bot_col in live.columns else set()
        n_live = len(gold_cases & live_has)
        n_input = len(gold_cases & input_cases)
        pct = lambda x: f"{100 * x / n:.0f}%" if n else "n/a"
        print(f"  {fw:<11}: gold={n:>4}  live-pred={n_live:>4} ({pct(n_live)})  "
              f"regen-input={n_input:>4} ({pct(n_input)})")


def _multilabel_join(creds) -> dict[str, set[str]]:
    """Case sets that have a non-blank live bot prediction, per multilabel framework."""
    live = Spread(cfg.LIVE_OUTPUT_SPREADSHEET_ID, creds=creds).sheet_to_df(
        sheet=cfg.LIVE_OUTPUT_TAB, index=None)
    live["_case"] = live.get("Case_Number", pd.Series(dtype=str)).astype(str).str.strip()
    out = {}
    for fw in cfg.MULTILABEL_FRAMEWORKS:
        col = cfg.FRAMEWORK_TO_OUTPUT_COL[fw]
        out[fw] = (set(live.loc[live[col].astype(str).str.strip() != "", "_case"])
                   if col in live.columns else set())
    return out


def audit_multilabel(creds) -> None:
    """Quality + Workflow gold: coverage by month, error-class counts, join health.

    Settles the open window question (esp. whether Workflow's May'26 rows are
    usable) before any P/R/F1 number is quoted against these tabs.
    """
    spread = Spread(cfg.QA2026_SPREADSHEET_ID, creds=creds)
    live_has = _multilabel_join(creds)

    # --- Quality ---
    q = gold_dump.load_quality_labels_2026(spread, months=None)  # all months
    print(f"\n{'=' * 78}\nQUALITY — {len(q)} usable rows (real case #)\n{'=' * 78}")
    print("  Coverage by Month:")
    for m in sorted(Counter(q["month"]), key=lambda x: (x == "", x)):
        print(f"    {m or '(unparsed)':>12} : {sum(q['month'] == m):>4}")
    dim_err = Counter()
    for d in q["dims_in_error"]:
        for dim in d:
            dim_err[dim] += 1
    print(f"  Cases with >=1 dimension error: {int((q['dims_in_error'].map(len) > 0).sum())}")
    print(f"  Per-dimension error counts: {dict(dim_err)}")
    print(f"  Critical: {dict(Counter(q['critical']))}")
    jn = len(set(q['case_number']) & live_has['Quality'])
    print(f"  Join health: {jn}/{len(q)} usable cases have a live bot prediction "
          f"({100 * jn / len(q):.0f}%)" if len(q) else "  Join health: n/a")

    # --- Workflow ---
    w = gold_dump.load_workflow_labels_2026(spread, months=None)
    print(f"\n{'=' * 78}\nWORKFLOW — {len(w)} usable rows (real Case_ID)\n{'=' * 78}")
    print("  Coverage by Month (and error-class count per month):")
    for m in sorted(Counter(w["month"]), key=lambda x: (x == "", x)):
        sub = w[w["month"] == m]
        print(f"    {m or '(unparsed)':>12} : {len(sub):>4} rows, "
              f"{int(sub['wf_error'].sum()):>3} workflow-adherence errors")
    etc = Counter()
    for t in w["error_types"]:
        for e in t:
            etc[e] += 1
    print(f"  Total workflow-adherence error cases: {int(w['wf_error'].sum())}")
    print(f"  Error types: {dict(etc.most_common(12))}")
    print(f"  Error Status field (NOT used as a label — open Q for Zaidul): "
          f"{dict(Counter(w['error_status']))}")
    jn = len(set(w['case_number']) & live_has['Workflow'])
    print(f"  Join health (Case_ID -> bot Case_Number): {jn}/{len(w)} "
          f"({100 * jn / len(w):.0f}%)" if len(w) else "  Join health: n/a")
    may = w[w["month"] == "2026-05"]
    print(f"\n  MAY RE-VERIFY: May'26 has {len(may)} rows, "
          f"{int(may['wf_error'].sum())} errors, "
          f"{len(set(may['case_number']) & live_has['Workflow'])} with a bot pred. "
          f"Include May only if these join and the workflow taxonomy is stable "
          f"across the March cutover (confirm with Zaidul).")
    print("\nDone. (read-only — nothing written back to any sheet)")


def main() -> None:
    ap = argparse.ArgumentParser(description="Audit the QA-2026 gold set (read-only).")
    ap.add_argument("--multilabel", action="store_true",
                    help="Audit the Quality + Workflow tabs instead of the driver tab "
                    "(coverage by month, error-class counts, join health, May re-verify).")
    args = ap.parse_args()

    creds = _build_credentials()
    if args.multilabel:
        audit_multilabel(creds)
        return

    spread = Spread(cfg.QA2026_SPREADSHEET_ID, creds=creds)
    driver = spread.sheet_to_df(sheet=cfg.QA2026_DRIVER_TAB, index=None)
    c = cfg.QA2026_LABEL_COLS

    print(f"QA-2026 driver tab {cfg.QA2026_DRIVER_TAB!r}: {len(driver)} rows, "
          f"columns: {list(driver.columns)}")
    stage_counts = Counter(driver[c["stage"]].astype(str).str.strip())
    print(f"Stage values: {dict(stage_counts)}")
    known_stages = set(cfg.QA2026_STAGE_MAP)
    unknown = {s: n for s, n in stage_counts.items() if s not in known_stages}
    if unknown:
        print(f"  ⚠ Stage values with NO framework mapping: {unknown}")

    stage_for_fw = {v: k for k, v in cfg.QA2026_STAGE_MAP.items()}
    for fw in DRIVER_FRAMEWORKS:
        sub = driver[driver[c["stage"]].astype(str).str.strip() == stage_for_fw[fw]]
        _print_framework(fw, sub)

    _join_health(creds, driver)
    print("\nDone. (read-only — nothing written back to any sheet)")


if __name__ == "__main__":
    main()
