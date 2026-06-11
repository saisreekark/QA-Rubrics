"""N-run accuracy measurement with confidence intervals.

The pipeline is non-deterministic even at temp 0 (~23% per-case driver churn
once the aggregator is also pinned to 0 — see `docs/execution-plan.md` 2.7),
so a single regen run can't measure a few-pp prompt change. This runs the regen
+ label-match N times on the *same* cases with the *current* notebook
(prompts + HIERARCHY_CONFIG), and reports per-framework accuracy as
**mean ± 95% CI** across the N runs.

A/B procedure (same as the regen harness): run this for the NEW (edited)
notebook, then `pull_notebook.sh` the OLD one and run it again — the prompt
effect is real only if the two means' CIs separate.

    python3 -m evaluator.ab_measure --label NEW --runs 5 --sample 120 \
        --framework TTR Reopen --temperature 0 --no-cache

LOCAL ONLY — never pushes to the Dataform notebook.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import math
import os
import statistics
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import vertexai
from gspread_pandas import Spread

from . import config as cfg
from . import gold_dump
from . import judge as judge_mod
from . import regen
from .runner import _parse_bot_output

# 95% two-sided t multipliers for small N (df = N-1).
_T95 = {2: 12.71, 3: 4.30, 4: 3.18, 5: 2.78, 6: 2.57, 7: 2.45, 8: 2.36, 9: 2.31, 10: 2.26}


async def _score_run(records: list[dict], labels_by_fw: dict[str, pd.DataFrame],
                     frameworks: list[str]) -> dict[str, tuple[float, int, int]]:
    """One regen run's records → per-framework (accuracy%, correct, audited)."""
    bot = pd.DataFrame(records)
    bot["case_number"] = bot["Case_Number"].astype(str).str.strip()
    sem = asyncio.Semaphore(cfg.JUDGE_CONCURRENCY)
    out: dict[str, tuple[float, int, int]] = {}
    for fw in frameworks:
        col = cfg.FRAMEWORK_TO_OUTPUT_COL[fw]
        joined = bot[["case_number", col]].merge(labels_by_fw[fw], on="case_number", how="inner")

        async def _one(row):
            parsed = _parse_bot_output(row.get(col))
            if parsed is None:
                return None  # NotApplicable — excluded from the denominator
            async with sem:
                try:
                    v = await judge_mod.match_case_framework(
                        fw, parsed, gold_l1=str(row.get("gold_l1", "")),
                        gold_l2l3=str(row.get("gold_l2l3", "")),
                        case_number=str(row.get("case_number", "")),
                    )
                    return v.overall_verdict
                except Exception:  # noqa: BLE001
                    return None

        verdicts = await asyncio.gather(*(_one(r) for _, r in joined.iterrows()))
        audited = [v for v in verdicts if v not in (None, "NotApplicable")]
        correct = sum(v == "Correct" for v in audited)
        pct = (correct / len(audited) * 100) if audited else float("nan")
        out[fw] = (pct, correct, len(audited))
    return out


def _ci(vals: list[float]) -> tuple[float, float, float]:
    """mean, sample-stdev, 95% CI half-width (t-based)."""
    clean = [v for v in vals if not math.isnan(v)]
    if len(clean) < 2:
        return (clean[0] if clean else float("nan"), 0.0, float("nan"))
    m = statistics.mean(clean)
    sd = statistics.stdev(clean)
    half = _T95.get(len(clean), 2.0) * sd / math.sqrt(len(clean))
    return m, sd, half


def main() -> None:
    p = argparse.ArgumentParser(description="N-run accuracy with confidence intervals")
    p.add_argument("--label", required=True, help="Run label (e.g. NEW / OLD) for outputs.")
    p.add_argument("--runs", type=int, default=5)
    p.add_argument("--sample", type=int, default=120)
    p.add_argument("--framework", nargs="+", choices=list(regen.DRIVER_FRAMEWORKS),
                   default=list(regen.DRIVER_FRAMEWORKS),
                   help="Driver frameworks only — OVERALL is pooled Correct/Audited "
                   "accuracy. Quality/Workflow use a different (detection) metric; "
                   "measure those via `regen --framework Quality Workflow` + "
                   "`runner --match-labels --gold-source regen`.")
    p.add_argument("--months", nargs="+", default=list(cfg.QA2026_MONTHS),
                   help="Gold closed_date months (default: cfg.QA2026_MONTHS, "
                   "currently the March-onward updated-taxonomy window).")
    p.add_argument("--temperature", type=float, default=0.0)
    p.add_argument("--model", default="gemini-3.1-pro-preview",
                   help="Bot model (default gemini-3.1-pro-preview, routed via "
                   "the global endpoint). Matcher stays on JUDGE_MODEL (2.5-pro, "
                   "regional). Pass an explicit 2.5-pro + --force-global for a "
                   "2.5 baseline on the same endpoint.")
    p.add_argument("--no-cache", action="store_true", default=True)
    p.add_argument("--force-global", action="store_true",
                   help="Route the bot through the global endpoint even for the "
                   "default model (2.5-pro), so its per-minute quota pool is "
                   "separate from the regional matcher (avoids self-saturation).")
    p.add_argument("--resume-file", type=Path, default=None,
                   help="Resume an interrupted run: seed completed runs from this "
                   "checkpoint JSON and only run the remaining (--runs minus done), "
                   "writing back to the SAME file. Cloud Shell reclaims the VM on "
                   "idle disconnect (killing the job) but $HOME + checkpoints "
                   "persist, so relaunch with this flag to continue losslessly.")
    args = p.parse_args()
    logging.basicConfig(level=logging.WARNING)

    creds = regen._build_credentials()  # static, drive-scoped — for Sheets reads
    # Matcher (regional vertexai) uses auto-refreshing ADC creds so long N-run
    # A/Bs don't 401 partway and silently shrink the denominator.
    vertexai.init(project=cfg.PROJECT_ID, location=cfg.LOCATION,
                  credentials=regen._build_vertex_credentials())
    ns = regen.load_pipeline(agent4_temp=args.temperature)
    ns["JOB_CONFIG"]["model_temperature"] = args.temperature
    for fw in ns["FRAMEWORK_CONFIGS"].values():
        for agent in fw["agents"]:
            agent["temperature"] = args.temperature
    if (args.model and args.model != ns["JOB_CONFIG"]["agent_model"]) or args.force_global:
        regen._install_global_genai(ns, args.model or ns["JOB_CONFIG"]["agent_model"], creds)

    # Fixed case set + gold labels, shared across all N runs.
    gold = Spread(cfg.QA2026_SPREADSHEET_ID, creds=creds)
    labels_by_fw, gold_cases = {}, set()
    for fw in args.framework:
        g = gold_dump.load_labels_2026(gold, fw, months=tuple(args.months))
        labels_by_fw[fw] = g
        gold_cases |= set(g["case_number"])
    rows = regen._read_input_rows(ns, creds, gold_cases)
    if args.sample < len(rows):
        rows = list(pd.DataFrame(rows).sample(n=args.sample, random_state=42).to_dict("records"))
    kb = regen._NoCacheKB()
    print(f"[{args.label}] {len(rows)} cases × {args.framework} × {args.runs} runs "
          f"(temp {args.temperature}, agent4 pinned)")

    # All N runs share ONE event loop — repeated asyncio.run() closes the loop
    # the cached async model clients are bound to, which silently nan'd runs 2+.
    # Matcher (regional 2.5-pro) and bot regen run in separate phases, so each can
    # burst higher than the conservative regional default. Bot uses the global
    # pool when --model/--force-global, so give it more concurrency there.
    on_global = bool(args.model) or args.force_global
    cfg.JUDGE_CONCURRENCY = int(os.environ.get("MATCH_CONCURRENCY", "16"))
    regen_conc = int(os.environ.get("REGEN_CONCURRENCY", "12" if on_global else "2"))
    print(f"  (regen_concurrency={regen_conc}, match_concurrency={cfg.JUDGE_CONCURRENCY})")

    # "OVERALL" is the pooled accuracy across frameworks (Σcorrect / Σaudited per
    # run) — the case-weighted number for stakeholder reporting.
    keys = list(args.framework) + ["OVERALL"]

    # Resume support: seed already-completed runs from a checkpoint and reuse its
    # file, so a Cloud Shell disconnect only costs the in-flight run, not all of it.
    seed_pct: dict[str, list[float]] = {k: [] for k in keys}
    seed_aud: dict[str, list[int]] = {k: [] for k in keys}
    if args.resume_file and args.resume_file.exists():
        prev = json.loads(args.resume_file.read_text())
        for k in keys:
            if k in prev:
                seed_pct[k] = list(prev[k].get("runs", []))
        done = len(seed_pct["OVERALL"])
        # audited counts aren't kept per-run in the checkpoint; backfill with the
        # stored mean so resumed CIs/denominators stay sensible.
        for k in keys:
            am = prev.get(k, {}).get("audited_mean", 0)
            seed_aud[k] = [am] * len(seed_pct[k])
        out = args.resume_file
        print(f"[resume] {done} run(s) already in {out.name}; "
              f"running {max(0, args.runs - done)} more.")
    else:
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
        out = cfg.RUNS_DIR / f"ab_{args.label}_{stamp}.json"

    def _write_summary(per_pct, per_aud, model_name, complete):
        summary = {"_meta": {"label": args.label, "model": model_name,
                             "matcher": cfg.JUDGE_MODEL, "runs_done": len(per_pct["OVERALL"]),
                             "runs_target": args.runs, "sample": args.sample,
                             "months": list(args.months), "complete": complete}}
        for k in keys:
            m, sd, half = _ci(per_pct[k])
            aud = [a for a in per_aud[k] if a is not None]
            summary[k] = {"runs": per_pct[k], "mean": m, "stdev": sd, "ci95_half": half,
                          "audited_mean": (statistics.mean(aud) if aud else 0)}
        out.write_text(json.dumps(summary, indent=2))
        return summary

    async def _measure():
        per_pct: dict[str, list[float]] = {k: list(seed_pct[k]) for k in keys}
        per_aud: dict[str, list[int]] = {k: list(seed_aud[k]) for k in keys}
        start = len(per_pct["OVERALL"])
        for i in range(start, args.runs):
            await asyncio.sleep(20)  # let the per-minute quota recover between runs
            records = await regen._regen_rows(ns, rows, args.framework, kb, concurrency=regen_conc)
            accs = await _score_run(records, labels_by_fw, args.framework)
            tot_c = tot_a = 0
            for fw in args.framework:
                pct, c, a = accs[fw]
                per_pct[fw].append(pct)
                per_aud[fw].append(a)
                tot_c += c
                tot_a += a
            per_pct["OVERALL"].append((tot_c / tot_a * 100) if tot_a else float("nan"))
            per_aud["OVERALL"].append(tot_a)
            print(f"  run {i+1}/{args.runs}: "
                  + "  ".join(f"{fw} {accs[fw][0]:.1f}%(n{accs[fw][2]})" for fw in args.framework)
                  + f"  | OVERALL {per_pct['OVERALL'][-1]:.1f}%(n{tot_a})", flush=True)
            _write_summary(per_pct, per_aud, model_name, complete=(i + 1 == args.runs))  # checkpoint
        return per_pct, per_aud

    model_name = ns["JOB_CONFIG"]["agent_model"]
    per_pct, per_aud = asyncio.run(_measure())

    print(f"\n=== [{args.label}] accuracy (mean ± 95% CI, n={args.runs}, bot={model_name}) ===")
    for k in keys:
        m, sd, half = _ci(per_pct[k])
        aud = [a for a in per_aud[k] if a is not None]
        an = statistics.mean(aud) if aud else 0
        print(f"  {k:11} {m:.1f}% ± {half:.1f}  (sd {sd:.1f}; n≈{an:.0f}; "
              f"runs {[round(x, 1) for x in per_pct[k]]})")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
