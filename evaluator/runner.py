"""CLI runner: load rows → fan out judges → write CSV.

Examples
--------

```
python3 -m evaluator.runner --sample 200
python3 -m evaluator.runner --gold
python3 -m evaluator.runner --sample 100 --framework Reopen
python3 -m evaluator.runner --sample 50 --model gemini-2.5-pro --temperature 0
```

Read-only on the sheet — never writes back.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import nest_asyncio
import pandas as pd
import vertexai
from google.oauth2.credentials import Credentials
from gspread_pandas import Spread
from tqdm.asyncio import tqdm

from . import config as cfg
from . import gold_dump
from . import judge as judge_mod
from . import multilabel_score as ml
from .schemas import CSV_COLUMNS, JudgeVerdict

nest_asyncio.apply()


def _build_credentials() -> Credentials:
    return Credentials(
        token=cfg.get_oauth_token(),
        token_uri="https://oauth2.googleapis.com/token",
        quota_project_id=cfg.PROJECT_ID,
    )


def _load_sheets(creds: Credentials) -> tuple[pd.DataFrame, pd.DataFrame]:
    spread = Spread(cfg.SPREADSHEET_ID, creds=creds)
    inputs = spread.sheet_to_df(sheet=cfg.INPUT_SHEET_NAME, index=None)
    outputs = spread.sheet_to_df(sheet=cfg.OUTPUT_SHEET_NAME, index=None)
    return inputs, outputs


def _parse_bot_output(cell: Any) -> Any:
    if cell is None or (isinstance(cell, float) and pd.isna(cell)):
        return None
    if isinstance(cell, str):
        s = cell.strip()
        if not s or s.lower() in {"none", "n/a", "na"}:
            return None
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            return s
    return cell


def _select_rows(inputs: pd.DataFrame, outputs: pd.DataFrame, sample: int | None) -> pd.DataFrame:
    key = cfg.COL_MAPPING["case_number"]
    if key not in outputs.columns or key not in inputs.columns:
        raise RuntimeError(f"Both sheets must contain column {key!r}")
    joined = outputs.merge(inputs, on=key, how="inner", suffixes=("", "_input"))
    if sample is not None and sample < len(joined):
        joined = joined.tail(sample)
    return joined


def _select_regen_rows(regen_csv: Path, inputs: pd.DataFrame) -> pd.DataFrame:
    """Join regen bot outputs with the live input sheet for reasonableness judging.

    The from-scratch judge needs the bot's per-framework RCA (from the regen CSV,
    keyed Case_Number with *_RCA_Output columns) AND the case transcript fields
    (from the input tab). Merge on Case_Number so `_run` can read both off one row.
    """
    key = cfg.COL_MAPPING["case_number"]
    regen = pd.read_csv(regen_csv, dtype=str)
    if key not in regen.columns:
        raise RuntimeError(f"Regen CSV {regen_csv} missing {key!r} column")
    regen[key] = regen[key].astype(str).str.strip()
    inputs = inputs.copy()
    inputs[key] = inputs[key].astype(str).str.strip()
    return regen.merge(inputs, on=key, how="inner", suffixes=("", "_input"))


def _select_gold_rows(inputs: pd.DataFrame, outputs: pd.DataFrame) -> pd.DataFrame:
    if not cfg.GOLD_PATH.exists() or cfg.GOLD_PATH.stat().st_size == 0:
        raise RuntimeError(
            f"Gold file {cfg.GOLD_PATH} is empty. Populate it with "
            "Zaidul-validated rows before running --gold."
        )
    gold = pd.read_csv(cfg.GOLD_PATH, dtype=str)
    if gold.empty:
        raise RuntimeError(f"Gold file {cfg.GOLD_PATH} has no data rows.")
    key = cfg.COL_MAPPING["case_number"]
    case_numbers = set(gold["case_number"].astype(str))
    outputs = outputs[outputs[key].astype(str).isin(case_numbers)]
    return outputs.merge(inputs, on=key, how="inner", suffixes=("", "_input"))


async def _match_one(
    sem: asyncio.Semaphore,
    row: dict[str, Any],
    framework: str,
) -> JudgeVerdict | None:
    case_number = str(row.get("case_number", ""))
    bot_output = _parse_bot_output(row.get(cfg.FRAMEWORK_TO_OUTPUT_COL[framework]))
    if bot_output is None:
        return JudgeVerdict(
            case_number=case_number,
            framework=framework,
            overall_verdict="NotApplicable",
            confidence=1.0,
            primary_driver_reason="Framework did not fire (empty bot output).",
            judge_model=cfg.JUDGE_MODEL,
            judged_at=datetime.now(timezone.utc),
        )
    async with sem:
        try:
            return await judge_mod.match_case_framework(
                framework,
                bot_output,
                gold_l1=str(row.get("gold_l1", "")),
                gold_l2l3=str(row.get("gold_l2l3", "")),
                case_number=case_number,
            )
        except Exception as exc:  # noqa: BLE001 — last-chance log, don't kill batch
            print(
                f"[warn] case={case_number} framework={framework} "
                f"match failed after retries: {exc}",
                file=sys.stderr,
            )
            return None


async def _run_match(
    framework: str, sample: int | None, creds: Credentials, source: str = "qa2026",
    regen_csv=None,
) -> list[JudgeVerdict]:
    if source == "regen":
        gold_spread = Spread(cfg.QA2026_SPREADSHEET_ID, creds=creds)
        joined = gold_dump.join_regen_and_labels_2026(
            regen_csv, gold_spread, framework, months=cfg.QA2026_MONTHS
        )
    elif source == "qa2026":
        gold_spread = Spread(cfg.QA2026_SPREADSHEET_ID, creds=creds)
        live_spread = Spread(cfg.LIVE_OUTPUT_SPREADSHEET_ID, creds=creds)
        joined = gold_dump.join_bot_and_labels_2026(
            gold_spread, live_spread, framework, months=cfg.QA2026_MONTHS
        )
    else:  # legacy big-dump source
        spread = Spread(cfg.DUMP_SPREADSHEET_ID, creds=creds)
        joined = gold_dump.join_bot_and_labels(spread, framework)
    if sample is not None and sample < len(joined):
        # Random (seeded) rather than tail — the dump is roughly chronological
        # and the tail isn't representative, so a random draw gives a fairer
        # per-framework baseline. Fixed seed keeps runs comparable.
        joined = joined.sample(n=sample, random_state=42)
    rows = joined.to_dict(orient="records")
    sem = asyncio.Semaphore(cfg.JUDGE_CONCURRENCY)
    tasks = [_match_one(sem, row, framework) for row in rows]
    results = await tqdm.gather(*tasks, desc=f"Matching {framework}")
    return [r for r in results if r is not None]


def _multilabel_months(framework: str, override) -> tuple[str, ...]:
    if override:
        return tuple(override)
    return (cfg.QA2026_QUALITY_MONTHS if framework == "Quality"
            else cfg.QA2026_WORKFLOW_MONTHS)


def _run_multilabel(
    framework: str, sample: int | None, creds: Credentials,
    source: str = "qa2026", regen_csv=None, months=None,
) -> tuple[str, dict, list[dict]]:
    """Score a multi-label framework (Quality/Workflow) -> (report, agg, per_case).

    Uses the deterministic detection/error-class scorer rather than the driver
    primary/secondary judge — see evaluator/multilabel_score.py.
    """
    win = _multilabel_months(framework, months)
    gold_spread = Spread(cfg.QA2026_SPREADSHEET_ID, creds=creds)
    if source == "regen":
        joined = gold_dump.join_regen_multilabel_2026(regen_csv, gold_spread, framework, win)
    elif source == "qa2026":
        live = Spread(cfg.LIVE_OUTPUT_SPREADSHEET_ID, creds=creds)
        joined = gold_dump.join_multilabel_2026(gold_spread, live, framework, win)
    else:
        raise SystemExit(
            f"--framework {framework} supports --gold-source qa2026 or regen (not dump)")
    if sample is not None and sample < len(joined):
        joined = joined.sample(n=sample, random_state=42)

    col = cfg.FRAMEWORK_TO_OUTPUT_COL[framework]
    label = f"({source}, {'/'.join(win)})"
    if framework == "Quality":
        results = [
            ml.score_quality_case(r["case_number"], r["dims_in_error"], r["critical"], r[col])
            for _, r in joined.iterrows()
        ]
        agg = ml.aggregate_quality(results)
        agg_crit = ml.aggregate_quality(results, critical_only=True)
        report = (ml.format_quality_report(agg, label) + "\n"
                  + ml.format_quality_report(agg_crit, label + " CRITICAL-only"))
        per_case = [
            {"case_number": r.case_number, "critical": r.critical,
             **{f"{dim}": f"g={int(d['gold'])} b={int(d['bot'])} l3={d['l3_match']}"
                for dim, d in r.per_dim.items()}}
            for r in results
        ]
        agg = {"all": agg, "critical_only": agg_crit}
    else:  # Workflow
        results = [
            ml.score_workflow_case(r["case_number"], r["wf_error"], r["error_types"], r[col])
            for _, r in joined.iterrows()
        ]
        agg = ml.aggregate_workflow(results)
        report = ml.format_workflow_report(agg, label)
        per_case = [
            {"case_number": r.case_number, "gold_error": r.gold_error,
             "bot_error": r.bot_error, "type_match": r.type_match,
             "bot_unmapped_only": r.bot_unmapped_only}
            for r in results
        ]
    return report, agg, per_case


async def _run_one(
    sem: asyncio.Semaphore,
    row: dict[str, Any],
    framework: str,
) -> JudgeVerdict | None:
    bot_output = _parse_bot_output(row.get(cfg.FRAMEWORK_TO_OUTPUT_COL[framework]))
    if bot_output is None:
        return JudgeVerdict(
            case_number=str(row.get(cfg.COL_MAPPING["case_number"], "")),
            framework=framework,
            overall_verdict="NotApplicable",
            confidence=1.0,
            primary_driver_reason="Framework did not fire (empty bot output).",
            judge_model=cfg.JUDGE_MODEL,
            judged_at=datetime.now(timezone.utc),
        )
    async with sem:
        try:
            return await judge_mod.judge_case_framework(row, framework, bot_output)
        except Exception as exc:  # noqa: BLE001 — last-chance log, don't kill batch
            print(
                f"[warn] case={row.get(cfg.COL_MAPPING['case_number'])} "
                f"framework={framework} failed after retries: {exc}",
                file=sys.stderr,
            )
            return None


async def _run(rows: list[dict[str, Any]], frameworks: list[str]) -> list[JudgeVerdict]:
    sem = asyncio.Semaphore(cfg.JUDGE_CONCURRENCY)
    tasks = [_run_one(sem, row, fw) for row in rows for fw in frameworks]
    results = await tqdm.gather(*tasks, desc="Judging")
    return [r for r in results if r is not None]


def _write_csv(verdicts: list[JudgeVerdict], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for v in verdicts:
            row = v.model_dump()
            row["judged_at"] = v.judged_at.isoformat()
            writer.writerow(row)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Rubrics LLM-as-judge evaluator")
    p.add_argument("--sample", type=int, default=None, help="Run on the N most-recent output rows.")
    p.add_argument("--gold", action="store_true", help="Run only on rows listed in gold/cases.csv.")
    p.add_argument(
        "--match-labels",
        action="store_true",
        help="Label-match mode: score bot predictions against human ground-truth "
        "labels (TTR/Reopen/Escalation/DSAT).",
    )
    p.add_argument(
        "--gold-source",
        choices=["qa2026", "dump", "regen"],
        default="qa2026",
        help="Gold label source for --match-labels. 'qa2026' (default) = the "
        "adopted updated-taxonomy sheet, Feb/Mar 2026, bot side from the live "
        "output tab. 'dump' = the legacy big QA dump. 'regen' = score a regen "
        "CSV (--regen-csv) against QA-2026 gold (measures a prompt/driver edit).",
    )
    p.add_argument(
        "--regen-csv", type=Path, default=None,
        help="Regen predictions CSV (from evaluator.regen); required for "
        "--gold-source regen.",
    )
    p.add_argument(
        "--framework",
        choices=cfg.FRAMEWORKS,
        action="append",
        help="Restrict to one framework (repeatable). Defaults to all six.",
    )
    p.add_argument(
        "--months", nargs="+", default=None,
        help="Override the gold month window for multilabel frameworks "
        "(Quality/Workflow). Default: Quality=Mar-Apr, Workflow=Mar-May.",
    )
    p.add_argument(
        "--judge-source",
        choices=["live", "regen"],
        default="live",
        help="From-scratch reasonableness judge source (non-match mode). 'live' "
        "(default) judges the production output tab; 'regen' judges a regen CSV "
        "(--regen-csv) joined with the input transcript — i.e. the tuned bot.",
    )
    p.add_argument("--model", default=cfg.JUDGE_MODEL, help="Override the judge model.")
    p.add_argument("--temperature", type=float, default=cfg.JUDGE_TEMPERATURE)
    p.add_argument("--out", type=Path, default=None, help="Override output CSV path.")
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    if args.sample is None and not args.gold:
        args.sample = 200

    cfg.JUDGE_MODEL = args.model  # type: ignore[assignment]
    cfg.JUDGE_TEMPERATURE = args.temperature  # type: ignore[assignment]

    creds = _build_credentials()
    vertexai.init(project=cfg.PROJECT_ID, location=cfg.LOCATION, credentials=creds)

    if args.match_labels:
        frameworks = list(args.framework) if args.framework else list(cfg.MATCH_FRAMEWORKS)
        supported = set(cfg.DUMP_LABEL_TABS) | set(cfg.MULTILABEL_FRAMEWORKS)
        unsupported = [f for f in frameworks if f not in supported]
        if unsupported:
            raise SystemExit(
                f"--match-labels does not support {unsupported}; "
                f"supported: {tuple(sorted(supported))}"
            )
        if args.gold_source == "regen" and not args.regen_csv:
            raise SystemExit("--gold-source regen requires --regen-csv <path>")

        driver_fws = [f for f in frameworks if f in cfg.DUMP_LABEL_TABS]
        multilabel_fws = [f for f in frameworks if f in cfg.MULTILABEL_FRAMEWORKS]
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")

        # Multi-label frameworks (Quality/Workflow) use the detection scorer and a
        # P/R/F1 report — kept SEPARATE from the driver Correct/Incorrect verdicts
        # so a detection metric is never averaged into the driver accuracy.
        for fw in multilabel_fws:
            report, agg, per_case = _run_multilabel(
                fw, args.sample, creds, args.gold_source, args.regen_csv, args.months)
            print("\n" + report)
            cfg.RUNS_DIR.mkdir(parents=True, exist_ok=True)
            base = cfg.RUNS_DIR / f"multilabel_{fw}_{stamp}"
            base.with_suffix(".json").write_text(json.dumps(agg, indent=2, default=str))
            if per_case:
                with base.with_suffix(".csv").open("w", newline="") as f:
                    w = csv.DictWriter(f, fieldnames=list(per_case[0].keys()))
                    w.writeheader()
                    w.writerows(per_case)
            print(f"wrote {base.with_suffix('.json')} (+ .csv)")

        if not driver_fws:
            return
        verdicts: list[JudgeVerdict] = []
        for fw in driver_fws:
            verdicts.extend(asyncio.run(
                _run_match(fw, args.sample, creds, args.gold_source, args.regen_csv)
            ))
    elif args.judge_source == "regen":
        if not args.regen_csv:
            raise SystemExit("--judge-source regen requires --regen-csv <path>")
        inputs, _ = _load_sheets(creds)
        rows_df = _select_regen_rows(args.regen_csv, inputs)
        if args.sample is not None and args.sample < len(rows_df):
            rows_df = rows_df.sample(n=args.sample, random_state=42)
        rows = rows_df.to_dict(orient="records")
        frameworks = list(args.framework) if args.framework else list(cfg.FRAMEWORKS)
        verdicts = asyncio.run(_run(rows, frameworks))
    else:
        inputs, outputs = _load_sheets(creds)
        rows_df = _select_gold_rows(inputs, outputs) if args.gold else _select_rows(inputs, outputs, args.sample)
        rows = rows_df.to_dict(orient="records")
        frameworks = list(args.framework) if args.framework else list(cfg.FRAMEWORKS)
        verdicts = asyncio.run(_run(rows, frameworks))

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    out_path = args.out or (cfg.RUNS_DIR / f"{stamp}.csv")
    _write_csv(verdicts, out_path)
    print(f"Wrote {len(verdicts)} verdicts → {out_path}")


if __name__ == "__main__":
    main()
