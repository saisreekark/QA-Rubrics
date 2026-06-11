"""Deterministic re-resolution of "Unmapped" drivers (v4, noise-proof).

The pipeline's `HierarchyResolver.get_details` maps a bot L3 string to its
L1/L2/L3 by an **exact** (lower+strip) match, falling back to `Unmapped` when the
string differs by whitespace / punctuation / a trailing period / an `[L2]` bracket
form. The bot frequently emits the *right concept* with a slightly different
surface string, so it lands as `Unmapped` — and the reasonableness judge then
(correctly) marks "failed to classify". This is a deterministic resolver bug, not
a model error (cf. the Workflow hygiene-justification fix).

This module re-resolves `Unmapped` drivers with a **normalized + fuzzy** match
against the framework's real hierarchy (`evaluator.hierarchy.load_hierarchy`), and
is applied as a post-filter to a regen CSV. It only touches drivers whose L1 is
`Unmapped` and whose L3 is a genuine near-miss of a valid node — `None`/empty L3s
are left untouched (genuine no-driver). Noise-free: same bot outputs, only the
broken drivers are corrected.

Usage:
    python3 -m evaluator.reresolve --in <regen.csv> --out <fixed.csv>
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
from pathlib import Path

import pandas as pd

from . import config as cfg
from .hierarchy import load_hierarchy

_FUZZY_CUTOFF = 0.86


def _norm(s: str) -> str:
    s = str(s).lower().strip()
    s = re.sub(r"\[.*?\]", "", s)        # drop "[L2]" bracket forms
    s = re.sub(r"[^a-z0-9]+", " ", s)    # punctuation -> space
    return re.sub(r"\s+", " ", s).strip()


def build_lookup(framework: str) -> dict[str, tuple[str, str, str]]:
    """normalized-name -> (L1, L2, L3). Includes L2 names (→ that L2's first L3)
    so a bot emitting the L2 as the L3 still resolves to the right L1/L2."""
    h = load_hierarchy(framework)
    lut: dict[str, tuple[str, str, str]] = {}
    for l1, l2d in h.items():
        for l2, l3s in l2d.items():
            for l3 in l3s:
                lut[_norm(l3)] = (l1, l2, l3)
            if l3s:
                lut.setdefault(_norm(l2), (l1, l2, l3s[0]))
    return lut


def resolve_l3(framework: str, l3: str, lut: dict | None = None):
    """Return (L1, L2, L3) for a near-miss L3 string, or None if unresolvable
    (empty / 'None' / no close match)."""
    lut = lut if lut is not None else build_lookup(framework)
    n = _norm(l3)
    if not n or n == "none":
        return None
    if n in lut:
        return lut[n]
    m = difflib.get_close_matches(n, list(lut), n=1, cutoff=_FUZZY_CUTOFF)
    return lut[m[0]] if m else None


def reresolve_output(bot_output, framework: str, lut: dict | None = None):
    """Fix Unmapped drivers in one framework's bot output JSON. Returns
    (new_output_same_type, n_fixed)."""
    was_str = isinstance(bot_output, str)
    parsed = bot_output
    if was_str:
        s = bot_output.strip()
        if not s or s.lower() in {"none", "nan", "{}"}:
            return (bot_output, 0)
        try:
            parsed = json.loads(s)
        except json.JSONDecodeError:
            return (bot_output, 0)
    if not isinstance(parsed, dict):
        return (bot_output, 0)
    lut = lut if lut is not None else build_lookup(framework)
    fixed = 0
    for k, d in parsed.items():
        if not isinstance(d, dict):
            continue
        if str(d.get("L1", "")).strip().lower() == "unmapped":
            r = resolve_l3(framework, d.get("L3", ""), lut)
            if r:
                d["L1"], d["L2"], d["L3"] = r
                fixed += 1
    if not fixed:
        return (bot_output, 0)
    return (json.dumps(parsed) if was_str else parsed, fixed)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--in", dest="inp", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    df = pd.read_csv(args.inp, dtype=str)
    luts = {f: build_lookup(f) for f in cfg.FRAMEWORKS}
    total = 0
    for f in cfg.FRAMEWORKS:
        col = cfg.FRAMEWORK_TO_OUTPUT_COL[f]
        if col not in df.columns:
            continue
        newvals, n = [], 0
        for v in df[col]:
            nv, k = reresolve_output(v, f, luts[f])
            newvals.append(nv)
            n += k
        df[col] = newvals
        total += n
        print(f"  {f:<11} re-resolved {n} Unmapped drivers")
    df.to_csv(args.out, index=False)
    print(f"total re-resolved: {total}  ->  {args.out}")


if __name__ == "__main__":
    main()
