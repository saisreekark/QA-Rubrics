"""Calibrate the deterministic multilabel scorer (Quality / Workflow) by hand.

The driver matchers are LLM judges that we calibrate against a human read
(`evaluator.calibrate_matcher`, ≥70% agreement bar). The multilabel scorer is
instead *deterministic* (`evaluator.multilabel_score`): dimension/L2 detection is
a closed-vocabulary exact match, and L3/error-type uses `phrase_match`
(normalized equality + truncation-tolerant substring). The thing that actually
needs a human check is therefore the **L3 / error-type match decision** — does
`phrase_match` agree with what a reviewer would call a hit?

This dumps a per-case, per-decision table (read-only on frozen-live preds, no
regen / no LLM) so a human can tick each L3 / error-type call. If agreement on
those falls below bar, swap `multilabel_score.phrase_match` for an LLM judge and
re-run. Detection (gold vs bot fired) is shown too, but that's mechanical.

Run:
  GOOGLE_OAUTH_TOKEN="$(gcloud auth print-access-token)" \
    python3 -m evaluator.calibrate_multilabel --framework Quality --sample 45
  # default: both multilabel frameworks, 45 cases each
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone

from gspread_pandas import Spread

from . import config as cfg, gold_dump, multilabel_score as ml
from .runner import _build_credentials


def _calibrate_quality(joined, sample) -> str:
    if sample < len(joined):
        joined = joined.sample(n=sample, random_state=7)
    col = cfg.FRAMEWORK_TO_OUTPUT_COL["Quality"]
    lines, n_l3, ok_l3 = [], 0, 0
    for _, r in joined.iterrows():
        drivers = ml.parse_drivers(r[col])
        res = ml.score_quality_case(r["case_number"], r["dims_in_error"], r["critical"], r[col])
        bot_by_l2 = {}
        for _, l2, l3 in drivers:
            bot_by_l2.setdefault(l2, []).append(l3)
        lines.append(f"\nCASE {res.case_number}  critical={res.critical}")
        for dim, d in res.per_dim.items():
            if not (d["gold"] or d["bot"]):
                continue
            tag = ("TP" if d["gold"] and d["bot"] else
                   "FP(bot only)" if d["bot"] else "FN(gold missed)")
            gold_errs = r["dims_in_error"].get(dim, [])
            bot_l3 = bot_by_l2.get(dim, [])
            lines.append(f"  [{tag:<14}] {dim}")
            lines.append(f"        GOLD L3: {gold_errs}")
            lines.append(f"        BOT  L3: {bot_l3}")
            if d["l3_match"] is not None:
                n_l3 += 1
                ok_l3 += int(d["l3_match"])
                lines.append(f"        -> phrase_match L3 = {d['l3_match']}  "
                             f"(human agrees? __)")
    head = [f"QUALITY scorer calibration — {len(joined)} cases — "
            f"{datetime.now(timezone.utc):%Y-%m-%dT%H-%M-%SZ}",
            "Tick each '-> phrase_match L3' line: does the hit/miss match your read?",
            f"Deterministic L3 agreement to confirm by hand: {ok_l3}/{n_l3} auto-hits.",
            "=" * 100]
    return "\n".join(head + lines)


def _calibrate_workflow_impl(joined, sample) -> str:
    import pandas as pd
    if sample < len(joined):
        # Oversample the rare error class so the dump is worth reading.
        err = joined[joined["wf_error"]]
        clean = joined[~joined["wf_error"]]
        take_err = min(len(err), max(sample // 2, 1))
        take_clean = min(len(clean), sample - take_err)
        joined = pd.concat([
            err.sample(n=take_err, random_state=7),
            clean.sample(n=take_clean, random_state=7),
        ])
    col = cfg.FRAMEWORK_TO_OUTPUT_COL["Workflow"]
    lines, n_t, ok_t = [], 0, 0
    for _, r in joined.iterrows():
        res = ml.score_workflow_case(r["case_number"], r["wf_error"], r["error_types"], r[col])
        drivers = ml.parse_drivers(r[col])
        adher = [l3 for _, l2, l3 in drivers if ml._norm(l2) == ml._norm(cfg.WORKFLOW_ADHERENCE_L2)]
        tag = ("TP" if res.gold_error and res.bot_error else
               "FP(bot only)" if res.bot_error else
               "FN(gold missed)" if res.gold_error else "TN")
        lines.append(f"\nCASE {res.case_number}  [{tag}]  unmapped_only={res.bot_unmapped_only}")
        lines.append(f"        GOLD error types: {r['error_types']}")
        lines.append(f"        BOT  adherence L3: {adher}")
        if res.type_match is not None:
            n_t += 1
            ok_t += int(res.type_match)
            lines.append(f"        -> phrase_match error-type = {res.type_match}  (human agrees? __)")
    head = [f"WORKFLOW scorer calibration — {len(joined)} cases — "
            f"{datetime.now(timezone.utc):%Y-%m-%dT%H-%M-%SZ}",
            "Tick each '-> phrase_match error-type' line on the true positives.",
            f"Deterministic error-type agreement to confirm by hand: {ok_t}/{n_t} auto-hits.",
            "=" * 100]
    return "\n".join(head + lines)


def main() -> None:
    p = argparse.ArgumentParser(description="Calibrate the multilabel scorer by hand.")
    p.add_argument("--framework", choices=list(cfg.MULTILABEL_FRAMEWORKS), action="append")
    p.add_argument("--sample", type=int, default=45)
    args = p.parse_args()
    frameworks = args.framework or list(cfg.MULTILABEL_FRAMEWORKS)

    creds = _build_credentials()
    gsp = Spread(cfg.QA2026_SPREADSHEET_ID, creds=creds)
    lsp = Spread(cfg.LIVE_OUTPUT_SPREADSHEET_ID, creds=creds)

    for fw in frameworks:
        win = cfg.QA2026_QUALITY_MONTHS if fw == "Quality" else cfg.QA2026_WORKFLOW_MONTHS
        joined = gold_dump.join_multilabel_2026(gsp, lsp, fw, win)
        text = (_calibrate_quality(joined, args.sample) if fw == "Quality"
                else _calibrate_workflow_impl(joined, args.sample))
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
        out = cfg.RUNS_DIR / f"calib_multilabel_{fw}_{stamp}.txt"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text)
        print(f"[{fw}] wrote {out}  ({len(joined)} cases)")


if __name__ == "__main__":
    main()
