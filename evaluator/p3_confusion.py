"""Phase-3 helper: bot-primary-L1 vs gold-L1 confusion for a Reopen regen CSV.

Quick, matcher-free profiling (exact-ish L1/L3 comparison) to see where the
reachable error mass sits. NOT the accuracy metric (that's the LLM matcher via
runner --match-labels); this is a diagnostic of what the bot emits vs gold.

    python3 -m evaluator.p3_confusion evaluator/runs/p3_reopen_OLD.csv 2026-04
"""
from __future__ import annotations

import json
import sys
from collections import Counter

import pandas as pd
from gspread_pandas import Spread

from . import config as cfg, gold_dump
from .regen import _build_credentials
import vertexai


def _primary(cell: str):
    try:
        d = json.loads(cell)
    except Exception:
        return ("(parse-err)", "(parse-err)")
    if not isinstance(d, dict) or "driver_1" not in d:
        return ("(none)", "(none)")
    p = d["driver_1"]
    return (str(p.get("L1", "")).strip(), str(p.get("L3", "")).strip())


def main():
    csv_path = sys.argv[1]
    months = tuple(sys.argv[2:]) or ("2026-04",)
    creds = _build_credentials()
    vertexai.init(project=cfg.PROJECT_ID, location=cfg.LOCATION, credentials=creds)
    gs = Spread(cfg.QA2026_SPREADSHEET_ID, creds=creds)
    gold = gold_dump.load_labels_2026(gs, "Reopen", months=months)
    gmap = {r.case_number: r for r in gold.itertuples()}

    df = pd.read_csv(csv_path, dtype=str).fillna("")
    out_col = cfg.FRAMEWORK_TO_OUTPUT_COL["Reopen"]
    rows = [r for r in df.to_dict("records") if str(r["Case_Number"]) in gmap]

    gold_l1 = Counter()
    bot_l1 = Counter()
    conf = Counter()  # (gold_l1, bot_l1)
    nq_gold = nq_bot = 0
    for r in rows:
        g = gmap[str(r["Case_Number"])]
        gl1 = str(getattr(g, "gold_l1", "")).strip().lower()
        gl23 = str(getattr(g, "gold_l2l3", "")).strip().lower()
        bl1, bl3 = _primary(r[out_col])
        bl1l = bl1.lower()
        gold_l1[gl1] += 1
        bot_l1[bl1l] += 1
        conf[(gl1, bl1l)] += 1
        if "new query" in gl23 or "additional or different" in gl23:
            nq_gold += 1
            if bl3.lower() == "additional or different query":
                nq_bot += 1

    n = len(rows)
    print(f"n={n} (joined to gold, months={months})\n")
    print("GOLD primary-L1 distribution:")
    for k, v in gold_l1.most_common():
        print(f"  {v:3d} ({v/n:4.0%})  {k}")
    print("\nBOT primary-L1 distribution:")
    for k, v in bot_l1.most_common():
        print(f"  {v:3d} ({v/n:4.0%})  {k}")
    print(f"\nNew-Query: gold={nq_gold} ({nq_gold/n:.0%}), bot-emitted-as-primary={nq_bot} "
          f"(recall {nq_bot/nq_gold:.0%})" if nq_gold else "")
    print("\nTop gold->bot L1 confusions:")
    for (gl, bl), v in conf.most_common(12):
        mark = "  ✓" if gl == bl else ""
        print(f"  {v:3d}  gold={gl:18s} -> bot={bl}{mark}")


if __name__ == "__main__":
    main()
