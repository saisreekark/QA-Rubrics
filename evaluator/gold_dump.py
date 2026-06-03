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
