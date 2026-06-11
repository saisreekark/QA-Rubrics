"""Measure the deterministic KSI / TTR-exclusion filter (Phase 4.3).

Profiles ``evaluator.ksi_ground.is_ksi_excluded`` on the real input data and against
the QA-2026 TTR gold — read-only, no pipeline run, no LLM. Answers three questions:

  1. PREVALENCE — among cases that currently trigger a TTR audit (Closed AND
     ``Case_Aging_in_Days >= 7``), how many would the filter exclude, and via which
     marker (KSI tag vs Bug_Id + pending-Eng-fix)?
  2. GOLD AGREEMENT — among the excluded cases that appear in the TTR gold, what is
     the human reviewer's primary-L1 composition? A KSI exclusion is *right* when the
     gold L1 is an external/upstream cause (Product/Tools, Process, User Gap), and
     *suspect* when the gold calls it an agent responsiveness defect (People Gap).
  3. EFFECT — the size of the TTR-audited denominator before/after the filter, and
     (with ``--scored-csv``) the recomputed TTR accuracy once excluded cases are
     dropped from an existing label-match run.

    export GOOGLE_OAUTH_TOKEN="$(gcloud auth print-access-token)"
    python3 -m evaluator.ksi_measure
    python3 -m evaluator.ksi_measure --scored-csv evaluator/runs/<labelmatch>.csv
"""

from __future__ import annotations

import argparse
from collections import Counter

import pandas as pd
from google.oauth2.credentials import Credentials
from gspread_pandas import Spread

from . import config as cfg
from .ksi_ground import F_BUG_ID, _KSI_TAG_RE, _PENDING_BUG_RE, is_ksi_excluded, ksi_reason


def _creds() -> Credentials:
    return Credentials(
        token=cfg.get_oauth_token(),
        token_uri="https://oauth2.googleapis.com/token",
        quota_project_id=cfg.PROJECT_ID,
    )


def _marker(row: dict) -> str:
    text = f"{row.get('Root_Cause_Description', '') or ''}\n{row.get('Root_Cause', '') or ''}"
    if _KSI_TAG_RE.search(text):
        return "ksi_tag"
    bug = str(row.get(F_BUG_ID) or "").strip()
    if bug and _PENDING_BUG_RE.search(text):
        return "bug_pending"
    return ""


def main() -> None:
    ap = argparse.ArgumentParser(description="Measure the KSI/TTR-exclusion filter.")
    ap.add_argument("--scored-csv", default=None,
                    help="A prior label-match CSV (TTR rows) to recompute accuracy after exclusion.")
    ap.add_argument("--dump", type=int, default=12, help="How many excluded-case reasons to print.")
    args = ap.parse_args()

    creds = _creds()
    spread = Spread(cfg.SPREADSHEET_ID, creds=creds)
    df = spread.sheet_to_df(sheet=cfg.INPUT_SHEET_NAME, index=None)
    df.columns = [c.strip() for c in df.columns]
    print(f"Input '{cfg.INPUT_SHEET_NAME}': {len(df)} rows, {len(df.columns)} cols")

    for need in ("Root_Cause_Description", "Bug_Id", "Case_Aging_in_Days", "Case_Status"):
        print(f"  column {need!r}: {'present' if need in df.columns else 'ABSENT'}")

    aging = pd.to_numeric(df.get("Case_Aging_in_Days", 0), errors="coerce").fillna(0)
    closed = df.get("Case_Status", pd.Series([""] * len(df))).astype(str).str.strip().str.lower() == "closed"
    ttr_audited = closed & (aging >= 7)
    rows = df.to_dict("records")
    ksi_flag = pd.Series([is_ksi_excluded(r) for r in rows], index=df.index)

    n_aud = int(ttr_audited.sum())
    n_excl = int((ttr_audited & ksi_flag).sum())
    print("\n=== 1. PREVALENCE (full input) ===")
    print(f"  TTR-audited today (Closed & aging>=7): {n_aud}")
    pct = 100 * n_excl / n_aud if n_aud else 0
    print(f"  → KSI-excluded by the filter:          {n_excl}  ({pct:.1f}% of audited)")
    markers = Counter(_marker(rows[i]) for i in range(len(rows)) if ksi_flag.iloc[i] and ttr_audited.iloc[i])
    print(f"  marker breakdown: ksi_tag={markers.get('ksi_tag', 0)}  bug_pending={markers.get('bug_pending', 0)}")
    # whole-input flag rate (sanity: how often the marker appears at all)
    print(f"  (KSI marker present anywhere in input: {int(ksi_flag.sum())} / {len(df)} rows)")

    print(f"\n  sample excluded cases (up to {args.dump}):")
    shown = 0
    for i in range(len(rows)):
        if ksi_flag.iloc[i] and ttr_audited.iloc[i]:
            cn = str(rows[i].get("Case_Number", "?")).strip()
            print(f"    {cn:>12}  aging={int(aging.iloc[i])}  [{ksi_reason(rows[i])}]"
                  f"  RCD={str(rows[i].get('Root_Cause_Description',''))[:70]!r}")
            shown += 1
            if shown >= args.dump:
                break

    # === 2. GOLD AGREEMENT ===
    from .gold_dump import load_labels_2026
    gold_spread = Spread(cfg.QA2026_SPREADSHEET_ID, creds=creds)
    gold = load_labels_2026(gold_spread, "TTR", months=cfg.QA2026_MONTHS)
    df["_cn"] = df.get("Case_Number", "").astype(str).str.strip()
    flagmap = dict(zip(df["_cn"], ksi_flag))
    gold["ksi"] = gold["case_number"].map(flagmap).fillna(False)
    g_excl = gold[gold["ksi"]]
    print("\n=== 2. GOLD AGREEMENT (QA-2026 TTR, Mar–Apr) ===")
    print(f"  TTR gold cases joined to input: {len(gold)}")
    print(f"  → KSI-excluded among gold:      {len(g_excl)}")
    if len(g_excl):
        print("  gold primary-L1 of excluded cases (external/upstream = correct exclusion):")
        for l1, n in Counter(g_excl["gold_l1_norm"]).most_common():
            print(f"    {n:>3}  {l1}")

    # === 3. EFFECT on a prior label-match run ===
    if args.scored_csv:
        # The runner label-match CSV uses `overall_verdict` (Correct / Incorrect /
        # Borderline / NotApplicable); accuracy = Correct ÷ audited, audited = not
        # NotApplicable (mirrors evaluator/aggregate.py exactly).
        sc = pd.read_csv(args.scored_csv, dtype=str)
        cn_col = next((c for c in ("case_number", "Case_Number") if c in sc.columns), None)
        print("\n=== 3. EFFECT on label-match run (TTR Correct÷Audited) ===")
        if not (cn_col and "overall_verdict" in sc.columns):
            print(f"  expected case_number + overall_verdict; cols={list(sc.columns)}")
        else:
            if "framework" in sc.columns:
                sc = sc[sc["framework"].astype(str).str.strip().str.lower() == "ttr"]
            sc["_cn"] = sc[cn_col].astype(str).str.strip()
            v = sc["overall_verdict"].astype(str).str.strip()
            sc = sc[v != "NotApplicable"].copy()           # audited only
            sc["_ok"] = sc["overall_verdict"].astype(str).str.strip() == "Correct"
            sc["_ksi"] = sc["_cn"].map(flagmap).fillna(False)
            before = sc["_ok"].mean() * 100 if len(sc) else 0
            kept = sc[~sc["_ksi"]]
            after = kept["_ok"].mean() * 100 if len(kept) else 0
            removed = sc[sc["_ksi"]]
            print(f"  TTR before exclusion: {sc['_ok'].sum()}/{len(sc)} = {before:.1f}%")
            print(f"  TTR after  exclusion: {kept['_ok'].sum()}/{len(kept)} = {after:.1f}%"
                  f"  (Δ {after - before:+.1f}pp)")
            print(f"  removed {len(removed)} KSI cases from the audited set: "
                  f"{int(removed['_ok'].sum())} were scored Correct, "
                  f"{int((~removed['_ok']).sum())} Incorrect")


if __name__ == "__main__":
    main()
