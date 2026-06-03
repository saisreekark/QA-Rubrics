"""Turn a runner CSV into the May-14-locked accuracy metric.

```
python3 -m evaluator.aggregate evaluator/runs/<timestamp>.csv
```

Prints case-level accuracy (primary-framework verdict), per-framework
breakdown, and Borderline / NotApplicable counts. If a gold file is present,
also prints judge↔human agreement.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import pandas as pd

from . import config as cfg

PRIMARY_FRAMEWORK_PRIORITY = ["Reopen", "TTR", "Escalation", "DSAT", "Quality", "Workflow"]


def _pick_primary(per_case: pd.DataFrame, override: str | None) -> pd.Series:
    fired = per_case[per_case["overall_verdict"] != "NotApplicable"]
    if fired.empty:
        return per_case.iloc[0]
    if override is not None:
        match = fired[fired["framework"] == override]
        if not match.empty:
            return match.iloc[0]
    for fw in PRIMARY_FRAMEWORK_PRIORITY:
        match = fired[fired["framework"] == fw]
        if not match.empty:
            return match.iloc[0]
    return fired.iloc[0]


def aggregate(csv_path: Path, primary_override: str | None = None) -> dict:
    df = pd.read_csv(csv_path, dtype=str)
    if df.empty:
        raise RuntimeError(f"{csv_path} has no rows.")

    per_case_primary = (
        df.groupby("case_number", group_keys=False)
        .apply(lambda g: _pick_primary(g, primary_override), include_groups=False)
        .reset_index(drop=True)
    )

    audited = per_case_primary[per_case_primary["overall_verdict"] != "NotApplicable"]
    correct = (audited["overall_verdict"] == "Correct").sum()
    total = len(audited)
    case_accuracy = (correct / total) if total else 0.0

    per_framework = []
    for fw, sub in df.groupby("framework"):
        fired = sub[sub["overall_verdict"] != "NotApplicable"]
        fw_correct = (fired["overall_verdict"] == "Correct").sum()
        fw_total = len(fired)
        per_framework.append(
            {
                "framework": fw,
                "audited": int(fw_total),
                "correct": int(fw_correct),
                "accuracy": (fw_correct / fw_total) if fw_total else 0.0,
                "borderline": int((sub["overall_verdict"] == "Borderline").sum()),
                "not_applicable": int((sub["overall_verdict"] == "NotApplicable").sum()),
            }
        )

    verdict_counts = Counter(df["overall_verdict"])
    summary = {
        "input_csv": str(csv_path),
        "case_accuracy": case_accuracy,
        "cases_correct": int(correct),
        "cases_audited": int(total),
        "verdict_counts": dict(verdict_counts),
        "per_framework": per_framework,
    }

    if cfg.GOLD_PATH.exists() and cfg.GOLD_PATH.stat().st_size > 0:
        try:
            gold = pd.read_csv(cfg.GOLD_PATH, dtype=str)
            if not gold.empty:
                merged = df.merge(
                    gold,
                    on=["case_number", "framework"],
                    how="inner",
                    suffixes=("", "_gold"),
                )
                if not merged.empty:
                    agree = (merged["overall_verdict"] == merged["gold_verdict"]).sum()
                    summary["gold_overlap"] = int(len(merged))
                    summary["gold_agreement"] = float(agree / len(merged))
        except Exception as exc:  # noqa: BLE001
            summary["gold_error"] = str(exc)

    sidecar = csv_path.with_name(csv_path.stem + ".summary.json")
    sidecar.write_text(json.dumps(summary, indent=2))
    return summary


def _print(summary: dict) -> None:
    print(f"Case-level accuracy: {summary['case_accuracy']:.2%} "
          f"({summary['cases_correct']}/{summary['cases_audited']})")
    print("Verdict counts:", summary["verdict_counts"])
    print("Per framework:")
    for row in summary["per_framework"]:
        print(
            f"  {row['framework']:<11} "
            f"acc={row['accuracy']:.2%} "
            f"({row['correct']}/{row['audited']}) "
            f"borderline={row['borderline']} "
            f"n/a={row['not_applicable']}"
        )
    if "gold_agreement" in summary:
        print(
            f"Judge↔human agreement on gold overlap "
            f"({summary['gold_overlap']} rows): {summary['gold_agreement']:.2%}"
        )


def main() -> None:
    p = argparse.ArgumentParser(description="Aggregate a Rubrics evaluator CSV.")
    p.add_argument("csv", type=Path)
    p.add_argument(
        "--primary",
        choices=cfg.FRAMEWORKS,
        default=None,
        help="Force this framework as the per-case primary when computing accuracy.",
    )
    args = p.parse_args()
    _print(aggregate(args.csv, args.primary))


if __name__ == "__main__":
    main()
