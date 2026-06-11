"""Evaluator configuration.

Re-uses the same project / sheet / column shape as cells 2, 7, 8 of
``notebook/content.ipynb`` so the judge always reads the same rows the
production pipeline writes. The OAuth token is read from
``GOOGLE_OAUTH_TOKEN`` — never hardcoded here.
"""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ID = "gtm-cloud-helpdesk"
LOCATION = "us-central1"

JUDGE_MODEL = "gemini-2.5-pro"
JUDGE_TEMPERATURE = 0.0
JUDGE_CONCURRENCY = 50

SPREADSHEET_ID = "1Lmo5laSelj8Yp-ANjuZ_cQVnVM3W9XB6mNRt_J94juM"
INPUT_SHEET_NAME = "Cases for Summary"
OUTPUT_SHEET_NAME = "RCA_Analysis_Output_1"

# Copied verbatim from notebook cell 2 COL_MAPPING — keep in sync if cell 2
# ever changes. The evaluator only needs the read-side columns.
COL_MAPPING = {
    "case_number": "Case_Number",
    "case_status": "Case_Status",
    "transcript": "Concatenated_Summary",
    "reopen_counter": "Reopen_Counter",
    "aging_days": "Case_Aging_in_Days",
    "is_escalated": "Escalated",
    "survey_result": "Survey_Result",
    "created_date": "Created_date",
    "closed_date": "Closed_date",
    "reopen_date": "Modified_date",
    "issue_category": "Issue_Category",
    "case_subject": "Case_Subject",
    "case_description": "Case_Description",
    "case_history": "Case History ",
    "out_reopen": "Reopen_RCA_Output",
    "out_ttr": "TTR_RCA_Output",
    "out_escalation": "Escalation_RCA_Output",
    "out_dsat": "DSAT_RCA_Output",
    "out_quality": "Quality_RCA_Output",
    "out_workflow": "Workflow_RCA_Output",
}

FRAMEWORK_TO_OUTPUT_COL = {
    "Reopen": COL_MAPPING["out_reopen"],
    "TTR": COL_MAPPING["out_ttr"],
    "Escalation": COL_MAPPING["out_escalation"],
    "DSAT": COL_MAPPING["out_dsat"],
    "Quality": COL_MAPPING["out_quality"],
    "Workflow": COL_MAPPING["out_workflow"],
}
FRAMEWORKS = tuple(FRAMEWORK_TO_OUTPUT_COL.keys())

# --- QA dump: human-reviewer ground-truth labels (label-match mode) ---
# A separate sheet from the live I/O sheet. Its per-framework tabs carry the
# canonical L1/L2/L3 a human reviewer assigned; the RCA_Analysis_Output tab
# carries the bot's JSON predictions for the same cases. We join the two on
# case number and ask the matcher whether bot == human. See evaluator/README.md.
DUMP_SPREADSHEET_ID = "1tbrQxJbjRLEn6yKB7djXsPfkFMKWHICKTy-X8Y5KzRY"

# Bot-output tab inside the dump. NOTE: its real header is the *second* row
# (row index 1) — the first row is blank. gold_dump handles that offset.
DUMP_BOT_SHEET = "RCA_Analysis_Output"
DUMP_BOT_HEADER_ROW = 1  # zero-based index of the header row

# Human-label tab per framework. The four driver frameworks share an identical
# column layout. Quality is score-based (not driver-based) and Workflow's bot
# output is sparse here — both are deferred to a follow-on, so omit them.
DUMP_LABEL_TABS = {
    "TTR": "TTR",
    "Reopen": "Reopen",
    "Escalation": "Escalation",
    "DSAT": "DSAT",
}
MATCH_FRAMEWORKS = tuple(DUMP_LABEL_TABS.keys())

DUMP_LABEL_COLS = {
    "case_number": "Case Number",
    "gold_l1": "identify the primary level 1 driver",
    "gold_l2l3": "identify level 2 & level 3 drivers",
    "reviewer": "quality_reviewer",
}

# --- QA-2026 gold (ADOPTED 2026-05-29): the canonical gold case set ---
# Manual QA labels for recent (Jan–Apr 2026) cases in the *updated* taxonomy
# (Product/Tools Gap + Quarter Freeze actually appear). One combined tab for the
# four driver frameworks, split by a `Stage` column. Unlike the older dump, the
# bot predictions for these (recent) cases live in the LIVE output tab — so the
# bot side joins from there, not from this sheet. Default source for --match-labels.
QA2026_SPREADSHEET_ID = "1_MvXAMTIUcHS9ne9vJHnA_l9wviNW87mcmgNYnGkXlg"
QA2026_DRIVER_TAB = "DSAT/Reopen/Escalation/TTR"
QA2026_STAGE_MAP = {              # gold 'Stage' value  ->  framework
    "TTR RCA": "TTR",
    "Reopen RCA": "Reopen",
    "Escalation RCA": "Escalation",
    "DSAT RCA": "DSAT",
}
QA2026_LABEL_COLS = {
    "case_number": "Case Number",
    "gold_l1": "identify the primary level 1 driver",
    "gold_l2l3": "identify level 2 & level 3 drivers",
    "reviewer": "quality_reviewer",
    "stage": "Stage",
    "closed_date": "closed_date",
}
# Gold window. The UPDATED taxonomy (the framework rebuild we are auditing
# against) is only reliably in use from **March 2026** for at least some
# frameworks — Jan/Feb cases were labelled under the OLD taxonomy and must NOT
# be scored as gold for the new rubric. The audit confirms the cutover: Quarter
# Freeze / YoY appears in 0 cases before March, then jumps in (`evaluator.
# gold_audit`, `docs/gold-audit-2026-06-05.md`). So the valid gold window is
# **March-onward** (April is the latest labelled month; no May/Jun yet). Kept as
# an EXPLICIT allow-list (not a moving lower-bound) so an A/B denominator stays
# fixed and runs weeks apart compare; add the next month deliberately when QA
# labels it. (Earlier locks — ("2026-02","2026-03"), then a too-wide Jan–Apr —
# both pulled in pre-cutover months; March-onward is the correct window.)
QA2026_MONTHS = ("2026-03", "2026-04")
# Bot predictions for these recent cases come from the live I/O output tab.
LIVE_OUTPUT_SPREADSHEET_ID = SPREADSHEET_ID
LIVE_OUTPUT_TAB = OUTPUT_SHEET_NAME

# --- QA-2026 multilabel gold: Quality + Workflow (the "6-driver" extension) ---
# The same gold sheet has two more tabs the driver path can't score, because the
# bot emits a *dynamic driver list* (driver_1..n of L1/L2/L3) that bypasses the
# agent4 aggregator, and the gold is multi-label / error-detection rather than a
# single Primary/Secondary verdict. See docs/quality-workflow-gold-scoping-2026-06-05.md.
QA2026_QUALITY_TAB = "Quality"
QA2026_WORKFLOW_TAB = "Workflow & Compliance"
MULTILABEL_FRAMEWORKS = ("Quality", "Workflow")

# Quality: the five graded dimensions. The *column name* is the dimension (== bot
# L2); the *cell value* is "no error" or a specific error string (== bot L3;
# comma-separated for multiples). Map each gold column -> the canonical bot L2.
QA2026_QUALITY_DIMENSIONS = {
    "accuracy-L2": "Accuracy",
    "completeness-L2": "Completeness",
    "relevance-L-2": "Relevance",
    "communication skills L-2": "Communication Skills",
    "responsiveness L-2": "Responsiveness",
}
QA2026_QUALITY_COLS = {
    "case_number": "Case_Number",
    "question_comment": "question_comment (L3)",
    "critical": "Critical/Non-critical error",
    "month": "Month",
}

# Workflow: only the workflow-adherence dimension carries learnable signal
# (~6% error). The compliance sub-dimension is effectively dead (2 positives) and
# is dropped. `Error Status` does NOT track the dimension errors (Yes=2031 vs ~164
# real errors) — open Q for Zaidul; not used as a label. Join key is `Case_ID`.
QA2026_WORKFLOW_COLS = {
    "case_number": "Case_ID",
    "adherence": "workflow adherence & compliance audits",
    "compliance": "compliance:data integrity & legal guidelines",
    "error_status": "Error Status",
    "month": "Month",
}
# Bot L2 label that signals a workflow-adherence error (vs "Unmapped"/compliance).
WORKFLOW_ADHERENCE_L2 = "Workflow Adherence Error"
# The "no error" sentinel used across both multilabel tabs.
MULTILABEL_NO_ERROR = "no error"

# These tabs label `Month` as "Mon'YY" (e.g. "Mar'26"), not a closed_date.
QA2026_MONTH_ABBR = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05", "jun": "06",
    "jul": "07", "aug": "08", "sep": "09", "oct": "10", "nov": "11", "dec": "12",
}
# Windows. Quality only has data through April; keep it on the March cutover.
# Workflow additionally has May'26 (the driver tab stops at April) and likely is
# NOT subject to the March driver-taxonomy cutover, so default to March-onward
# INCLUDING May for a larger error-class denominator — re-verify with gold_audit
# before quoting (open Q for Zaidul on the workflow cutover).
QA2026_QUALITY_MONTHS = QA2026_MONTHS
QA2026_WORKFLOW_MONTHS = ("2026-03", "2026-04", "2026-05")

# QA semantics: "People Gap" is the only agent-error L1. No People Gap = no error.
ERROR_L1 = "people gap"

# The dump's combined `product/tool gap` L1 (spelled `product/tools gap` on
# some tabs) maps to the rubric's split Product Gap / Tool Gap L1s. Normalize
# the variants so a code-side exact-match on L1 behaves. The matcher prompt
# treats the combined label as matching either rubric L1 — see open-questions.
L1_NORMALIZE = {
    "product/tool gap": "product/tool gap",
    "product/tools gap": "product/tool gap",
}

REPO_ROOT = Path(__file__).resolve().parent.parent
NOTEBOOK_PATH = REPO_ROOT / "notebook" / "content.ipynb"
EVAL_ROOT = REPO_ROOT / "evaluator"
PROMPT_PATH = EVAL_ROOT / "prompts" / "judge.md"
MATCH_PROMPT_PATH = EVAL_ROOT / "prompts" / "judge_match.md"
GOLD_PATH = EVAL_ROOT / "gold" / "cases.csv"
RUNS_DIR = EVAL_ROOT / "runs"
HIERARCHY_CACHE = EVAL_ROOT / ".hierarchy_cache.json"


def get_oauth_token() -> str:
    token = os.environ.get("GOOGLE_OAUTH_TOKEN")
    if not token:
        raise RuntimeError(
            "GOOGLE_OAUTH_TOKEN env var is required. Run "
            "`gcloud auth print-access-token` and export it before running "
            "the evaluator."
        )
    return token
