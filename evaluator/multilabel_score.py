"""Deterministic scorer for the multi-label frameworks (Quality + Workflow).

These two frameworks do not fit the driver path's single Primary/Secondary
L1→L2→L3 verdict. The bot emits a *dynamic driver list* (driver_1..n of
L1/L2/L3) and the gold is graded per-dimension:

- **Quality**: five dimensions (Accuracy / Completeness / Relevance /
  Communication Skills / Responsiveness), each independently "no error" or a
  specific error. The dimension name == the bot's L2; the specific error ==
  the bot's L3. Metric = per-dimension **detection** (did the bot emit a driver
  for a dimension the human flagged?) + **classification** (did the bot's L3
  match the human's specific error?), aggregated to precision / recall / F1.
- **Workflow**: one live dimension (workflow adherence). ~94% of cases are
  "no error", so raw accuracy is meaningless — metric = **precision / recall /
  F1 on the error class**, plus error-type classification on the true positives.

Deterministic-first by design (the L2/dimension vocabulary is closed and the L3
strings mostly match case-insensitively). `phrase_match` is the single hook to
swap in an LLM judge for L3/error-type semantic equivalence if calibration shows
the deterministic match misses the bar — see
docs/quality-workflow-gold-scoping-2026-06-05.md.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from . import config as cfg


# --- normalization & matching ----------------------------------------------

# Domain synonyms folded before matching. In GTM support the *user* IS the
# seller / client / customer / requester, and the gold and bot vocabularies use
# these interchangeably — gold "did not tailor a solution to client's needs" ==
# bot "...to user's needs". Confirmed by the 2026-06-05 calibration hand-read:
# this was the ONLY deterministic Quality-L3 miss in 13 TPs (12/13 → 13/13 with
# the fold). Targeted and safe: these words appear in the L3 vocab only as the
# end-party noun. Keeps the scorer deterministic — no LLM judge needed.
_SYNONYMS = {"client": "user", "customer": "user", "seller": "user", "requester": "user"}


def _norm(s) -> str:
    """Lowercase, drop punctuation, fold party synonyms, collapse whitespace."""
    words = re.sub(r"[^a-z0-9 ]", " ", str(s).lower()).split()
    return " ".join(_SYNONYMS.get(w, w) for w in words)


def phrase_match(gold: str, bot: str) -> bool:
    """Deterministic L3 / error-type equivalence.

    Equal after normalization, or — to tolerate the gold's frequent truncation
    ("...comprehension of" vs "...comprehension of the issue") — a substring
    either direction once both sides are long enough to be unambiguous.
    """
    a, b = _norm(gold), _norm(bot)
    if not a or not b:
        return False
    if a == b:
        return True
    if len(a) >= 15 and len(b) >= 15 and (a in b or b in a):
        return True
    return False


def parse_drivers(bot_output) -> list[tuple[str, str, str]]:
    """Bot RCA JSON -> list of (L1, L2, L3). Tolerant of empties/errors.

    Accepts a dict (driver_1..n), a JSON string, or already-parsed input;
    skips an ``{"error": ...}`` payload and non-dict drivers.
    """
    if bot_output is None:
        return []
    if isinstance(bot_output, str):
        s = bot_output.strip()
        if not s:
            return []
        try:
            bot_output = json.loads(s)
        except json.JSONDecodeError:
            return []
    if not isinstance(bot_output, dict) or "error" in bot_output:
        return []
    drivers = []
    for key in sorted(bot_output):  # driver_1, driver_2, ...
        d = bot_output[key]
        if isinstance(d, dict):
            drivers.append((
                str(d.get("L1", "")).strip(),
                str(d.get("L2", "")).strip(),
                str(d.get("L3", "")).strip(),
            ))
    return drivers


# --- per-case scoring -------------------------------------------------------

@dataclass
class QualityCaseResult:
    case_number: str
    critical: bool
    # dimension -> {"gold": bool, "bot": bool, "l3_match": bool|None}
    per_dim: dict[str, dict] = field(default_factory=dict)


@dataclass
class WorkflowCaseResult:
    case_number: str
    gold_error: bool
    bot_error: bool          # bot emitted a Workflow-Adherence-Error driver
    type_match: bool | None  # among true positives, did an error type match?
    bot_unmapped_only: bool  # bot emitted only "Unmapped" drivers (diagnostic)


def score_quality_case(case_number, dims_in_error, critical, bot_output) -> QualityCaseResult:
    drivers = parse_drivers(bot_output)
    res = QualityCaseResult(case_number=str(case_number), critical=bool(critical))
    for dim in cfg.QA2026_QUALITY_DIMENSIONS.values():
        gold_errs = dims_in_error.get(dim, []) if isinstance(dims_in_error, dict) else []
        bot_l3s = [l3 for (_, l2, l3) in drivers if _norm(l2) == _norm(dim)]
        gold, bot = bool(gold_errs), bool(bot_l3s)
        l3_match = None
        if gold and bot:  # true positive on detection -> grade classification
            l3_match = any(phrase_match(g, b) for g in gold_errs for b in bot_l3s)
        res.per_dim[dim] = {"gold": gold, "bot": bot, "l3_match": l3_match}
    return res


def score_workflow_case(case_number, gold_error, gold_error_types, bot_output) -> WorkflowCaseResult:
    drivers = parse_drivers(bot_output)
    adher_l3s = [l3 for (_, l2, l3) in drivers if _norm(l2) == _norm(cfg.WORKFLOW_ADHERENCE_L2)]
    bot_error = bool(adher_l3s)
    type_match = None
    if gold_error and bot_error:
        types = gold_error_types if isinstance(gold_error_types, (list, tuple)) else []
        type_match = any(phrase_match(g, b) for g in types for b in adher_l3s)
    unmapped_only = (not bot_error) and bool(drivers) and all(
        _norm(l2) == _norm("Unmapped") for (_, l2, _) in drivers)
    return WorkflowCaseResult(
        case_number=str(case_number), gold_error=bool(gold_error),
        bot_error=bot_error, type_match=type_match, bot_unmapped_only=unmapped_only)


# --- aggregation ------------------------------------------------------------

def _prf(tp: int, fp: int, fn: int) -> dict:
    precision = tp / (tp + fp) if (tp + fp) else float("nan")
    recall = tp / (tp + fn) if (tp + fn) else float("nan")
    f1 = (2 * precision * recall / (precision + recall)
          if precision and recall and not (precision != precision or recall != recall)
          else float("nan"))
    return {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "f1": f1}


def aggregate_quality(results: list[QualityCaseResult], critical_only: bool = False) -> dict:
    """Per-dimension + overall (micro) detection P/R/F1 and L3 classification acc."""
    rows = [r for r in results if (r.critical or not critical_only)]
    out: dict = {"n_cases": len(rows), "per_dim": {}}
    tot_tp = tot_fp = tot_fn = tot_cls_hit = tot_cls_den = 0
    for dim in cfg.QA2026_QUALITY_DIMENSIONS.values():
        tp = fp = fn = 0
        cls_hit = cls_den = 0
        for r in rows:
            d = r.per_dim.get(dim, {})
            g, b = d.get("gold"), d.get("bot")
            if g and b:
                tp += 1
                cls_den += 1
                cls_hit += int(bool(d.get("l3_match")))
            elif b and not g:
                fp += 1
            elif g and not b:
                fn += 1
        m = _prf(tp, fp, fn)
        m["l3_classification_acc"] = (cls_hit / cls_den) if cls_den else float("nan")
        m["l3_classified_of"] = cls_den
        out["per_dim"][dim] = m
        tot_tp += tp; tot_fp += fp; tot_fn += fn
        tot_cls_hit += cls_hit; tot_cls_den += cls_den
    out["overall"] = _prf(tot_tp, tot_fp, tot_fn)
    out["overall"]["l3_classification_acc"] = (tot_cls_hit / tot_cls_den) if tot_cls_den else float("nan")
    out["overall"]["l3_classified_of"] = tot_cls_den
    return out


def aggregate_workflow(results: list[WorkflowCaseResult]) -> dict:
    """Binary error-class P/R/F1 + error-type classification on the true positives."""
    tp = sum(r.gold_error and r.bot_error for r in results)
    fp = sum((not r.gold_error) and r.bot_error for r in results)
    fn = sum(r.gold_error and (not r.bot_error) for r in results)
    tn = sum((not r.gold_error) and (not r.bot_error) for r in results)
    m = _prf(tp, fp, fn)
    type_den = sum(1 for r in results if r.gold_error and r.bot_error)
    type_hit = sum(1 for r in results if r.gold_error and r.bot_error and r.type_match)
    m.update({
        "tn": tn,
        "n_cases": len(results),
        "n_gold_error": sum(r.gold_error for r in results),
        "n_bot_error": sum(r.bot_error for r in results),
        "error_type_acc": (type_hit / type_den) if type_den else float("nan"),
        "error_type_classified_of": type_den,
        "n_unmapped_only": sum(r.bot_unmapped_only for r in results),
    })
    return m


# --- reporting --------------------------------------------------------------

def _fmt(x) -> str:
    return "  nan" if x != x else f"{x * 100:5.1f}%"  # NaN-safe percent


def _dim_line(name: str, m: dict) -> str:
    counts = f"{m['tp']}/{m['fp']}/{m['fn']}"
    return (f"  {name:<22} {_fmt(m['precision'])} {_fmt(m['recall'])} {_fmt(m['f1'])}"
            f"  {counts:>10}  {_fmt(m['l3_classification_acc'])}({m['l3_classified_of']})")


def format_quality_report(agg: dict, label: str = "") -> str:
    lines = [f"QUALITY detection P/R/F1 + L3 classification  {label}".rstrip(),
             f"  cases={agg['n_cases']}",
             f"  {'dimension':<22} {'P':>6} {'R':>6} {'F1':>6}  {'tp/fp/fn':>10}  L3-acc(n)"]
    for dim, m in agg["per_dim"].items():
        lines.append(_dim_line(dim, m))
    lines.append(_dim_line("OVERALL (micro)", agg["overall"]))
    return "\n".join(lines)


def format_workflow_report(m: dict, label: str = "") -> str:
    return "\n".join([
        f"WORKFLOW error-class P/R/F1  {label}".rstrip(),
        f"  cases={m['n_cases']}  gold_errors={m['n_gold_error']}  bot_errors={m['n_bot_error']}"
        f"  unmapped_only={m['n_unmapped_only']}",
        f"  precision={_fmt(m['precision'])}  recall={_fmt(m['recall'])}  f1={_fmt(m['f1'])}"
        f"  (tp/fp/fn/tn={m['tp']}/{m['fp']}/{m['fn']}/{m['tn']})",
        f"  error-type classification acc (of {m['error_type_classified_of']} TPs)="
        f"{_fmt(m['error_type_acc'])}",
    ])
