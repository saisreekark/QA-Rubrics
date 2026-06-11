"""Deterministic Reopen (and DSAT) primary re-attribution (v5, noise-proof).

For the **Reopen** framework the Primary driver must name the *reopen trigger* — why
the seller re-engaged the case — NOT the case's underlying cause. The bot frequently
emits an EXTERNAL/Process driver (Quarter Freeze, approval, dependency, product bug)
as Primary — that's *why the agent couldn't fulfil the request*, not *why the user
reopened*. When the bot ALSO surfaced a USER-/PEOPLE-/INVALID-side finding as a
secondary, that secondary is the real reopen reason → promote it to Primary.

Same idea for **DSAT**: the source of dissatisfaction is usually the agent's handling
(People Gap) rather than the underlying product issue, when both are present.

Deterministic post-filter on a regen CSV (no model re-run → noise-free). Only swaps
when a non-external secondary genuinely exists; never invents a driver.

Usage:
    python3 -m evaluator.reopen_demote --in <regen.csv> --out <fixed.csv>
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from . import config as cfg

_EXTERNAL_L1 = {"process gap", "product/tools gap", "product gap", "tool gap"}
# the reopen/DSAT *trigger* sides — these outrank an external case-cause as Primary
_TRIGGER_L1 = {"user gap", "people gap", "invalid reopen"}


def _l1(d) -> str:
    return str(d.get("L1", "")).strip().lower() if isinstance(d, dict) else ""


def demote_external_primary(bot_output, framework: str):
    """Promote the first USER/PEOPLE/INVALID secondary over an EXTERNAL primary.
    Returns (new_output_same_type, swapped:bool)."""
    if framework not in ("Reopen", "DSAT"):
        return (bot_output, False)
    was_str = isinstance(bot_output, str)
    parsed = bot_output
    if was_str:
        s = bot_output.strip()
        if not s or s.lower() in {"none", "nan", "{}"}:
            return (bot_output, False)
        try:
            parsed = json.loads(s)
        except json.JSONDecodeError:
            return (bot_output, False)
    if not isinstance(parsed, dict):
        return (bot_output, False)

    keys = sorted(parsed)  # driver_1, driver_2, ...
    if not keys:
        return (bot_output, False)
    d1 = parsed[keys[0]]
    if _l1(d1) not in _EXTERNAL_L1:
        return (bot_output, False)
    # find the first trigger-side secondary
    promote_key = None
    for k in keys[1:]:
        if _l1(parsed[k]) in _TRIGGER_L1:
            promote_key = k
            break
    if promote_key is None:
        return (bot_output, False)

    # rebuild: promoted secondary first, old primary next, then the rest (order kept)
    ordered = [parsed[promote_key], d1] + [
        parsed[k] for k in keys if k not in (keys[0], promote_key)
    ]
    new = {f"driver_{i}": d for i, d in enumerate(ordered, start=1)}
    return (json.dumps(new) if was_str else new, True)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--in", dest="inp", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--frameworks", nargs="+", default=["Reopen", "DSAT"])
    args = p.parse_args()
    df = pd.read_csv(args.inp, dtype=str)
    total = 0
    for f in args.frameworks:
        col = cfg.FRAMEWORK_TO_OUTPUT_COL[f]
        if col not in df.columns:
            continue
        newvals, n = [], 0
        for v in df[col]:
            nv, sw = demote_external_primary(v, f)
            newvals.append(nv)
            n += int(sw)
        df[col] = newvals
        total += n
        print(f"  {f:<11} swapped {n} external-primary -> trigger-primary")
    df.to_csv(args.out, index=False)
    print(f"total swapped: {total}  ->  {args.out}")


if __name__ == "__main__":
    main()
