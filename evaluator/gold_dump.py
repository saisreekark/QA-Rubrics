"""Load human-reviewer ground-truth labels from the QA dump sheet.

The dump (``DUMP_SPREADSHEET_ID``) has one tab per framework holding the
canonical L1 / L2&L3 a human reviewer assigned, and a ``RCA_Analysis_Output``
tab holding the bot's JSON predictions for the same case population. This
module loads the human side; the runner joins it to the bot side on case
number and hands each pair to the label-match judge.

Read-only — never writes back.
"""

from __future__ import annotations

import re

import pandas as pd
from gspread_pandas import Spread

from . import config as cfg

# Real Salesforce case numbers are 7+ digit integers. The dump sheets carry a
# handful of manual placeholder rows (`12345`, `CASE-123`, `TTR_case_01`)
# clustered at the tail; this drops them so they never pollute a baseline.
_REAL_CASE = re.compile(r"^\d{7,}$")


def _is_real_case(series: pd.Series) -> pd.Series:
    return series.str.match(_REAL_CASE)


def normalize_l1(value: str | None) -> str:
    """Lower/strip an L1 label and fold the product/tool(s) gap variants."""
    if value is None:
        return ""
    key = str(value).strip().lower()
    return cfg.L1_NORMALIZE.get(key, key)


def _read_bot_sheet(spread: Spread) -> pd.DataFrame:
    """RCA_Analysis_Output's real header is the 2nd row; read raw + reframe."""
    ws = spread.spread.worksheet(cfg.DUMP_BOT_SHEET)
    values = ws.get_all_values()
    header = values[cfg.DUMP_BOT_HEADER_ROW]
    rows = values[cfg.DUMP_BOT_HEADER_ROW + 1 :]
    return pd.DataFrame(rows, columns=header)


def load_labels(spread: Spread, framework: str) -> pd.DataFrame:
    """Human gold labels for one framework.

    Returns columns: case_number, gold_l1, gold_l1_norm, gold_l2l3, reviewer.
    Rows with a blank primary L1 are dropped (nothing to match against).
    """
    if framework not in cfg.DUMP_LABEL_TABS:
        raise ValueError(
            f"No dump label tab for {framework!r}; "
            f"label-match supports {tuple(cfg.DUMP_LABEL_TABS)}."
        )
    df = spread.sheet_to_df(sheet=cfg.DUMP_LABEL_TABS[framework], index=None)
    c = cfg.DUMP_LABEL_COLS
    missing = [v for v in (c["case_number"], c["gold_l1"]) if v not in df.columns]
    if missing:
        raise RuntimeError(f"Dump tab {framework!r} missing columns: {missing}")

    out = pd.DataFrame(
        {
            "case_number": df[c["case_number"]].astype(str).str.strip(),
            "gold_l1": df[c["gold_l1"]].astype(str).str.strip(),
            "gold_l2l3": df.get(c["gold_l2l3"], "").astype(str).str.strip(),
            "reviewer": df.get(c["reviewer"], "").astype(str).str.strip(),
        }
    )
    out = out[_is_real_case(out["case_number"]) & (out["gold_l1"] != "")]
    # Last reviewer wins if a case was labelled more than once.
    out = out.drop_duplicates(subset="case_number", keep="last")
    out["gold_l1_norm"] = out["gold_l1"].map(normalize_l1)
    return out.reset_index(drop=True)


def load_labels_2026(spread: Spread, framework: str, months=None) -> pd.DataFrame:
    """Human gold labels for one framework from the QA-2026 sheet.

    Filters the combined driver tab by `Stage` (-> framework) and, if `months`
    is given, by `closed_date` month (e.g. ("2026-02","2026-03")). Returns the
    same columns as `load_labels`.
    """
    c = cfg.QA2026_LABEL_COLS
    stage_for_fw = {v: k for k, v in cfg.QA2026_STAGE_MAP.items()}.get(framework)
    if stage_for_fw is None:
        raise ValueError(f"No QA-2026 Stage mapping for framework {framework!r}.")
    df = spread.sheet_to_df(sheet=cfg.QA2026_DRIVER_TAB, index=None)
    missing = [v for v in (c["case_number"], c["gold_l1"], c["stage"]) if v not in df.columns]
    if missing:
        raise RuntimeError(f"QA-2026 tab missing columns: {missing}")

    df = df[df[c["stage"]].astype(str).str.strip() == stage_for_fw]
    if months and c["closed_date"] in df.columns:
        closed = pd.to_datetime(df[c["closed_date"]].astype(str).str.strip(), errors="coerce")
        df = df[closed.dt.to_period("M").astype(str).isin(months)]

    def _opt(name):  # optional column -> stripped Series, or blanks if absent
        if name in df.columns:
            return df[name].astype(str).str.strip()
        return pd.Series([""] * len(df), index=df.index)

    out = pd.DataFrame(
        {
            "case_number": df[c["case_number"]].astype(str).str.strip(),
            "gold_l1": df[c["gold_l1"]].astype(str).str.strip(),
            "gold_l2l3": _opt(c["gold_l2l3"]),
            "reviewer": _opt(c["reviewer"]),
        }
    )
    out = out[_is_real_case(out["case_number"]) & (out["gold_l1"] != "")]
    out = out.drop_duplicates(subset="case_number", keep="last")
    out["gold_l1_norm"] = out["gold_l1"].map(normalize_l1)
    return out.reset_index(drop=True)


def join_bot_and_labels_2026(
    gold_spread: Spread, live_spread: Spread, framework: str, months=None
) -> pd.DataFrame:
    """Join LIVE bot predictions to QA-2026 human labels on case number.

    Bot side = the live I/O output tab (`cfg.LIVE_OUTPUT_TAB`); these recent
    cases are not in the old dump. Returns the bot output column for this
    framework plus the gold_* columns.
    """
    bot = live_spread.sheet_to_df(sheet=cfg.LIVE_OUTPUT_TAB, index=None)
    bot_col = cfg.FRAMEWORK_TO_OUTPUT_COL[framework]
    if "Case_Number" not in bot.columns or bot_col not in bot.columns:
        raise RuntimeError(f"{cfg.LIVE_OUTPUT_TAB} missing 'Case_Number' or {bot_col!r}")
    bot = bot[["Case_Number", bot_col]].copy()
    bot["case_number"] = bot["Case_Number"].astype(str).str.strip()
    bot = bot[(bot[bot_col].astype(str).str.strip() != "") & _is_real_case(bot["case_number"])]
    bot = bot.drop_duplicates(subset="case_number", keep="last")

    labels = load_labels_2026(gold_spread, framework, months)
    return bot.merge(labels, on="case_number", how="inner")


def join_regen_and_labels_2026(
    regen_csv, gold_spread: Spread, framework: str, months=None
) -> pd.DataFrame:
    """Join *regenerated* predictions (a regen CSV) to QA-2026 human labels.

    Same shape as `join_bot_and_labels_2026`, but the bot side is a local CSV
    produced by `evaluator.regen` (current local prompts) instead of the frozen
    live output tab — this is what makes a prompt/driver change measurable.
    """
    bot = pd.read_csv(regen_csv, dtype=str)
    bot_col = cfg.FRAMEWORK_TO_OUTPUT_COL[framework]
    if "Case_Number" not in bot.columns or bot_col not in bot.columns:
        raise RuntimeError(f"{regen_csv} missing 'Case_Number' or {bot_col!r}")
    bot = bot[["Case_Number", bot_col]].copy()
    bot["case_number"] = bot["Case_Number"].astype(str).str.strip()
    bot = bot[bot[bot_col].astype(str).str.strip() != ""]
    bot = bot.drop_duplicates(subset="case_number", keep="last")

    labels = load_labels_2026(gold_spread, framework, months)
    return bot.merge(labels, on="case_number", how="inner")


# --- QA-2026 multilabel gold: Quality + Workflow ---------------------------
# Different shape from the driver tabs: the gold is multi-label / error-detection
# (a per-dimension grade, not one Primary L1). These loaders return structured
# columns the multilabel scorer consumes; see evaluator/multilabel_score.py.

_MONTH_ABBR_RE = re.compile(r"^\s*([A-Za-z]{3,})'?\s*(\d{2,4})\s*$")


def _month_to_period(value: str | None) -> str:
    """`"Mar'26"` -> `"2026-03"`. Returns '' if it can't be parsed."""
    if not value:
        return ""
    m = _MONTH_ABBR_RE.match(str(value))
    if not m:
        return ""
    mm = cfg.QA2026_MONTH_ABBR.get(m.group(1)[:3].lower())
    if not mm:
        return ""
    yr = m.group(2)
    yr = yr if len(yr) == 4 else f"20{yr}"
    return f"{yr}-{mm}"


def _split_top_level(value: str) -> list[str]:
    """Split on commas that are NOT inside () or [].

    Error phrases can themselves contain commas inside parentheses — e.g.
    "did not use language correctly (grammar, spelling, syntax)" — so a naive
    str.split(',') over-fragments them. This only breaks at the top level.
    """
    parts, buf, depth = [], [], 0
    for ch in value:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth = max(0, depth - 1)
        if ch == "," and depth == 0:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    parts.append("".join(buf))
    return parts


def _split_errors(value: str | None) -> list[str]:
    """Split a gold quality cell into its specific-error strings.

    Cells are 'no error', blank, or one-or-more comma-separated error strings
    (e.g. "did not structure response,asked for information repeatedly"). Drops
    'no error' fragments and blanks; returns [] when the dimension is clean.
    """
    if value is None:
        return []
    out = []
    for part in _split_top_level(str(value)):
        p = part.strip()
        if p and p.lower() != cfg.MULTILABEL_NO_ERROR:
            out.append(p)
    return out


_WF_BRACKET_RE = re.compile(r"\[([^\]]+)\]")


def _workflow_error_types(value: str | None) -> list[str]:
    """Extract the error type(s) from a workflow-adherence cell.

    Value looks like "workflow adherence error [missing vector case hygiene
    fields]" (possibly comma-joined for multiples). The error type lives inside
    the brackets; 'no error' / blank yields []. Falls back to the whole non-'no
    error' string if there are no brackets (defensive).
    """
    if value is None:
        return []
    s = str(value).strip()
    if not s or s.lower() == cfg.MULTILABEL_NO_ERROR:
        return []
    bracketed = [b.strip() for b in _WF_BRACKET_RE.findall(s) if b.strip()]
    if bracketed:
        return bracketed
    # No brackets: keep the non-'no error' fragments verbatim.
    return _split_errors(s)


def load_quality_labels_2026(spread: Spread, months=None) -> pd.DataFrame:
    """Quality gold: per-dimension multi-label errors from the QA-2026 sheet.

    Returns columns: case_number, dims_in_error (dict {bot-L2 dimension: [error
    strings]} — only dimensions actually in error), critical (bool), month.
    Rows are kept only if they have a real case number and at least one column.
    """
    df = spread.sheet_to_df(sheet=cfg.QA2026_QUALITY_TAB, index=None)
    qc = cfg.QA2026_QUALITY_COLS
    if qc["case_number"] not in df.columns:
        raise RuntimeError(f"Quality tab missing {qc['case_number']!r}")

    month = df.get(qc["month"], pd.Series([""] * len(df))).map(_month_to_period)
    if months:
        df = df[month.isin(months)]
        month = month[month.isin(months)]

    case = df[qc["case_number"]].astype(str).str.strip()
    critical = df.get(qc["critical"], pd.Series([""] * len(df))).astype(str).str.strip()

    def _dims_for_row(row) -> dict[str, list[str]]:
        dims: dict[str, list[str]] = {}
        for col, l2 in cfg.QA2026_QUALITY_DIMENSIONS.items():
            if col in df.columns:
                errs = _split_errors(row.get(col))
                if errs:
                    dims[l2] = errs
        return dims

    out = pd.DataFrame(
        {
            "case_number": case,
            "dims_in_error": [_dims_for_row(r) for _, r in df.iterrows()],
            "critical": critical.str.lower().str.startswith("crit"),
            "month": month.values,
        }
    )
    out = out[_is_real_case(out["case_number"])]
    return out.drop_duplicates(subset="case_number", keep="last").reset_index(drop=True)


def load_workflow_labels_2026(spread: Spread, months=None) -> pd.DataFrame:
    """Workflow gold: binary error-detection on the workflow-adherence dimension.

    Returns columns: case_number (from Case_ID), wf_error (bool), error_types
    (list[str], the bracketed error type(s)), error_status, month. The compliance
    sub-dimension is dropped (2 positives — no learnable signal).
    """
    df = spread.sheet_to_df(sheet=cfg.QA2026_WORKFLOW_TAB, index=None)
    wc = cfg.QA2026_WORKFLOW_COLS
    if wc["case_number"] not in df.columns or wc["adherence"] not in df.columns:
        raise RuntimeError(
            f"Workflow tab missing {wc['case_number']!r} or {wc['adherence']!r}")

    month = df.get(wc["month"], pd.Series([""] * len(df))).map(_month_to_period)
    if months:
        df = df[month.isin(months)]
        month = month[month.isin(months)]

    case = df[wc["case_number"]].astype(str).str.strip()
    adherence = df[wc["adherence"]].astype(str)
    error_types = [_workflow_error_types(v) for v in adherence]

    out = pd.DataFrame(
        {
            "case_number": case,
            "wf_error": [len(t) > 0 for t in error_types],
            "error_types": error_types,
            "error_status": df.get(wc["error_status"], pd.Series([""] * len(df))).astype(str).str.strip().values,
            "month": month.values,
        }
    )
    out = out[_is_real_case(out["case_number"])]
    return out.drop_duplicates(subset="case_number", keep="last").reset_index(drop=True)


_MULTILABEL_LOADER = {
    "Quality": load_quality_labels_2026,
    "Workflow": load_workflow_labels_2026,
}


def _bot_side(bot_df: pd.DataFrame, framework: str, real_only: bool) -> pd.DataFrame:
    """Shared bot-side prep: keep [case_number, <out col>], non-blank, dedup."""
    bot_col = cfg.FRAMEWORK_TO_OUTPUT_COL[framework]
    if "Case_Number" not in bot_df.columns or bot_col not in bot_df.columns:
        raise RuntimeError(f"bot source missing 'Case_Number' or {bot_col!r}")
    bot = bot_df[["Case_Number", bot_col]].copy()
    bot["case_number"] = bot["Case_Number"].astype(str).str.strip()
    keep = bot[bot_col].astype(str).str.strip() != ""
    if real_only:
        keep &= _is_real_case(bot["case_number"])
    return bot[keep].drop_duplicates(subset="case_number", keep="last")


def join_multilabel_2026(
    gold_spread: Spread, live_spread: Spread, framework: str, months=None
) -> pd.DataFrame:
    """Join LIVE bot predictions to QA-2026 multilabel gold (Quality/Workflow)."""
    bot = _bot_side(live_spread.sheet_to_df(sheet=cfg.LIVE_OUTPUT_TAB, index=None),
                    framework, real_only=True)
    labels = _MULTILABEL_LOADER[framework](gold_spread, months)
    return bot.merge(labels, on="case_number", how="inner")


def join_regen_multilabel_2026(
    regen_csv, gold_spread: Spread, framework: str, months=None
) -> pd.DataFrame:
    """Join *regenerated* Quality/Workflow predictions to the multilabel gold."""
    bot = _bot_side(pd.read_csv(regen_csv, dtype=str), framework, real_only=False)
    labels = _MULTILABEL_LOADER[framework](gold_spread, months)
    return bot.merge(labels, on="case_number", how="inner")


def join_bot_and_labels(spread: Spread, framework: str) -> pd.DataFrame:
    """Inner-join bot predictions to human labels on case number.

    The returned frame has the bot output column for this framework
    (``cfg.FRAMEWORK_TO_OUTPUT_COL[framework]``) plus the gold_* columns.
    """
    bot = _read_bot_sheet(spread)
    bot_col = cfg.FRAMEWORK_TO_OUTPUT_COL[framework]
    if "Case_Number" not in bot.columns or bot_col not in bot.columns:
        raise RuntimeError(
            f"{cfg.DUMP_BOT_SHEET} missing 'Case_Number' or {bot_col!r}"
        )
    bot = bot[["Case_Number", bot_col]].copy()
    bot["case_number"] = bot["Case_Number"].astype(str).str.strip()
    bot = bot[(bot[bot_col].astype(str).str.strip() != "") & _is_real_case(bot["case_number"])]
    bot = bot.drop_duplicates(subset="case_number", keep="last")

    labels = load_labels(spread, framework)
    return bot.merge(labels, on="case_number", how="inner")
