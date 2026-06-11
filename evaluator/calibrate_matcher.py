"""Calibrate the label-match judge against a human read, per framework.

The matcher (`evaluator.judge.match_case_framework`) is itself an unvalidated
LLM judge: before we quote its accuracy numbers as absolute we need to confirm
it agrees with a human on a sample (≥70% agreement bar — see
`docs/execution-plan.md` §2.6). This regenerates predictions with the *current
local* prompts (global bot, temp 0, no-cache), joins them to QA-2026 gold, runs
the matcher, and dumps a per-case table (`evaluator/runs/calib_<fw>_<stamp>.txt`)
for a human to read verdict-by-verdict. Reopen passed at ~90% (2026-06-04); this
generalises that one-off to TTR / DSAT / Escalation too.

Run:
  GOOGLE_OAUTH_TOKEN="$(gcloud auth print-access-token)" \
    python3 -m evaluator.calibrate_matcher --framework Reopen --sample 45
  # default: all four driver frameworks, 45 cases each
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from collections import Counter
from datetime import datetime, timezone

import pandas as pd
import vertexai
from gspread_pandas import Spread

from . import config as cfg, gold_dump, regen
from . import judge as judge_mod

DRIVER_FRAMEWORKS = ("Reopen", "TTR", "Escalation", "DSAT")

# The bot regen runs on the GLOBAL endpoint (separate quota pool) and finishes
# before any matcher call, so the two phases never share the regional bucket —
# both can run well above the conservative regional defaults. Override via env.
REGEN_CONCURRENCY = int(os.environ.get("REGEN_CONCURRENCY", "12"))  # global bot pool (separate quota)
MATCH_CONCURRENCY = int(os.environ.get("MATCH_CONCURRENCY", "24"))  # regional matcher, runs alone


def _parse(out):
    try:
        d = json.loads(out) if isinstance(out, str) else out
        if not isinstance(d, dict) or "error" in d:
            return None
        return d
    except Exception:
        return None


def _bot_drivers(bot):
    """Short 'L1 > L2 > L3' for driver_1 (+driver_2 if present)."""
    if not bot:
        return "(empty)"
    parts = []
    for k in ("driver_1", "driver_2"):
        d = bot.get(k)
        if isinstance(d, dict):
            parts.append(" > ".join(str(d.get(x, "")).strip() for x in ("L1", "L2", "L3")))
    return "  ||  ".join(parts) if parts else "(no drivers)"


async def _calibrate_one(fw: str, sample: int, ns, creds, gold: Spread) -> str:
    """Regen + match one framework; write the per-case dump; return a summary line."""
    labels = gold_dump.load_labels_2026(gold, fw, months=cfg.QA2026_MONTHS)
    gold_by_case = {str(r["case_number"]).strip(): r for _, r in labels.iterrows()}

    rows = regen._read_input_rows(ns, creds, set(gold_by_case))
    if sample < len(rows):
        rows = list(pd.DataFrame(rows).sample(n=sample, random_state=7).to_dict("records"))
    kb = regen._NoCacheKB()
    print(f"[{fw}] gold={len(gold_by_case)}  regenerating {len(rows)} cases "
          f"(global bot, temp 0, no-cache, regen_concurrency={REGEN_CONCURRENCY})...")
    recs = await regen._regen_rows(ns, rows, [fw], kb, concurrency=REGEN_CONCURRENCY)

    col = cfg.FRAMEWORK_TO_OUTPUT_COL[fw]
    sem = asyncio.Semaphore(MATCH_CONCURRENCY)

    async def one(rec):
        case = str(rec.get("Case_Number", "")).strip()
        if case not in gold_by_case:
            return None
        g = gold_by_case[case]
        bot = _parse(rec.get(col, ""))
        if bot is None:
            return (case, g, "(bot empty/error)", "NotApplicable", 0.0, "bot produced no output")
        async with sem:
            try:
                v = await judge_mod.match_case_framework(
                    fw, bot, gold_l1=str(g.get("gold_l1", "")),
                    gold_l2l3=str(g.get("gold_l2l3", "")), case_number=case)
                return (case, g, _bot_drivers(bot), v.overall_verdict,
                        v.confidence, v.primary_driver_reason)
            except Exception as e:
                return (case, g, _bot_drivers(bot), f"MATCH_ERR:{type(e).__name__}", 0.0, str(e)[:80])

    results = [r for r in await asyncio.gather(*(one(r) for r in recs)) if r]
    vc = Counter(r[3] for r in results)
    audited = [r for r in results if r[3] in ("Correct", "Incorrect", "Borderline")]
    correct = [r for r in audited if r[3] == "Correct"]
    acc = 100 * len(correct) / len(audited) if audited else float("nan")

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    dump = cfg.RUNS_DIR / f"calib_{fw}_{stamp}.txt"
    dump.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"Matcher calibration — {fw} — {len(results)} cases — {stamp}",
             "Read each: does the verdict agree with what a human would say given GOLD vs BOT?",
             "=" * 100]
    for case, g, botd, verdict, conf, reason in results:
        lines += [f"\nCASE {case}   verdict={verdict}  conf={conf:.2f}",
                  f"  GOLD: L1={g.get('gold_l1','')!r}  L2/L3={g.get('gold_l2l3','')!r}",
                  f"  BOT : {botd}",
                  f"  WHY : {reason[:300]}"]
    lines += ["\n" + "=" * 100,
              f"verdict counts: {dict(vc)}",
              f"audited={len(audited)}  correct={len(correct)}  judge_says_correct={acc:.1f}%",
              "(judge↔human agreement is the % of these verdicts a human read confirms — fill in by hand)"]
    dump.write_text("\n".join(lines))
    return (f"  {fw:<11}: {len(results):>3} cases  verdicts={dict(vc)}  "
            f"judge-says-correct={acc:.1f}%  → {dump}")


async def main_async(frameworks: list[str], sample: int) -> None:
    creds = regen._build_credentials()  # static, drive-scoped — for Sheets reads
    # Matcher uses auto-refreshing ADC creds so a multi-framework run doesn't 401
    # partway (the Escalation calibration died this way on the static token).
    vertexai.init(project=cfg.PROJECT_ID, location=cfg.LOCATION,
                  credentials=regen._build_vertex_credentials())
    ns = regen.load_pipeline(agent4_temp=0.0)
    ns["JOB_CONFIG"]["model_temperature"] = 0.0
    for fwc in ns["FRAMEWORK_CONFIGS"].values():
        for a in fwc["agents"]:
            a["temperature"] = 0.0
    # Route the bot through the global endpoint (separate quota pool, ADC auth) so
    # higher concurrency doesn't saturate the regional bucket the matcher uses.
    regen._install_global_genai(ns, "gemini-2.5-pro", creds)

    gold = Spread(cfg.QA2026_SPREADSHEET_ID, creds=creds)
    summaries = []
    for fw in frameworks:
        summaries.append(await _calibrate_one(fw, sample, ns, creds, gold))

    print("\n" + "=" * 100 + "\nCALIBRATION SUMMARY (hand-read each dump to confirm ≥70% agreement)\n" + "=" * 100)
    for s in summaries:
        print(s)


def main() -> None:
    p = argparse.ArgumentParser(description="Calibrate the label-match judge, per framework.")
    p.add_argument("--framework", choices=DRIVER_FRAMEWORKS, action="append",
                   help="Framework to calibrate (repeatable). Default: all four driver frameworks.")
    p.add_argument("--sample", type=int, default=45, help="Cases per framework (default 45).")
    args = p.parse_args()
    frameworks = args.framework or list(DRIVER_FRAMEWORKS)
    asyncio.run(main_async(frameworks, args.sample))


if __name__ == "__main__":
    main()
