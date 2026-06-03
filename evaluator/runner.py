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
    framework: str, sample: int | None, creds: Credentials, source: str = "qa2026"
) -> list[JudgeVerdict]:
    if source == "qa2026":
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
        choices=["qa2026", "dump"],
        default="qa2026",
        help="Gold label source for --match-labels. 'qa2026' (default) = the "
        "adopted updated-taxonomy sheet, Feb/Mar 2026, bot side from the live "
        "output tab. 'dump' = the legacy big QA dump.",
    )
    p.add_argument(
        "--framework",
        choices=cfg.FRAMEWORKS,
        action="append",
        help="Restrict to one framework (repeatable). Defaults to all six.",
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
        unsupported = [f for f in frameworks if f not in cfg.DUMP_LABEL_TABS]
        if unsupported:
            raise SystemExit(
                f"--match-labels does not support {unsupported}; "
                f"supported: {tuple(cfg.DUMP_LABEL_TABS)}"
            )
        verdicts: list[JudgeVerdict] = []
        for fw in frameworks:
            verdicts.extend(asyncio.run(_run_match(fw, args.sample, creds, args.gold_source)))
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
