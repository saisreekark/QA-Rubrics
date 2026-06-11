"""Deterministic KSI (Known-Systemic-Issue) TTR-exclusion filter — Phase 4.3.

A closed case whose resolution is pending a **systemic / engineering fix** must not
be scored for TTR: its long age reflects an upstream Eng dependency, not an agent
responsiveness defect, so it would otherwise pollute the TTR / SLA signal. Zaidul
delegated the full qualifier to the SOP / T&C policy docs (2026-06-09); the
doc-derived definition (``docs/open-questions.md`` RESOLVED 2026-06-09 #2,
``docs/kb-source/SOP_Summary.txt`` "Outcome 3" / WOCA) is:

    A case is NULL for TTR (KSI exclusion) when BOTH
      (a) it carries a KNOWN-SYSTEMIC marker —
            * a ``KSI -`` / ``KSI:`` tag in ``Root_Cause_Description`` (seen in prod
              data), OR
            * a linked ``Bug_Id`` whose resolution note says the systemic fix is
              "under development / evaluation" (SOP "Outcome 3": system bugs /
              complex technical issues, resolution "days to months"),
      AND
      (b) the fix is pending a FUTURE / UNCOMMITTED resolution (Eng/system-dependent).

This is the deterministic-code half of objective #3 (the model can't be trusted to
read structured markers — cf. the hygiene hallucination, task 4.7). It extends the
already-shipped ``<7 days = null`` TTR gate (cell 9 ``aging_days >= 7``) and the SOP's
"WOCA pauses the SLA" logic.

Single source of truth for the logic. ``evaluator.ksi_measure`` uses it to profile
prevalence + gold agreement; the production notebook (cell 9) mirrors the same
predicate inline as a gated pre-LLM filter that suppresses the TTR framework run
(the notebook can't import this package).

Design mirrors ``evaluator/hygiene_ground.py``: a column ABSENT from the data is
"unknown", never a trigger — the filter only excludes on a positive, grounded marker,
so a missing ``Bug_Id``/``Root_Cause_Description`` column can never wrongly null a case.
"""

from __future__ import annotations

import re

# Input columns (as they appear in "Cases for Summary" / the agent template vars).
F_CASE_STATUS = "Case_Status"
F_ROOT_CAUSE = "Root_Cause"
F_ROOT_CAUSE_DESC = "Root_Cause_Description"
F_BUG_ID = "Bug_Id"

_EMPTY_SENTINELS = {"", "none", "n/a", "na", "nan", "null", "0", "-"}

# (a) systemic marker — the ``KSI -`` / ``KSI:`` tag. ``\bksi\b`` matches the tag in
# "KSI - quota mismatch", "KSI:", "(KSI)", "known systemic issue (KSI)" while NOT
# matching substrings like "ksid" or "skis". The expanded phrases are belt-and-braces.
_KSI_TAG_RE = re.compile(r"\bksi\b|\bknown[ -]?systemic[ -]?issue\b", re.IGNORECASE)

# (a)/(b) SOP "Outcome 3" — a system bug pending an Eng-side fix (also encodes "pending
# future resolution"). Used only in combination with a populated ``Bug_Id``.
_PENDING_BUG_RE = re.compile(
    r"under (development|evaluation|investigation|review)"
    r"|being (developed|evaluated|investigated|worked)"
    r"|(fix|resolution|patch) (is )?(pending|in progress|in-progress|awaited|eta)"
    r"|pending (eng|engineering|fix|deployment|release)"
    r"|engineering (team )?(is )?(working|investigating)"
    r"|system bug|known issue|days to months|work in progress|\bwip\b",
    re.IGNORECASE,
)


def _is_empty(v) -> bool:
    if v is None:
        return True
    try:  # pandas NaN, without importing pandas here
        if v != v:
            return True
    except Exception:  # noqa: BLE001
        pass
    return str(v).strip().lower() in _EMPTY_SENTINELS


def _get(fields: dict, col: str) -> str:
    return "" if col not in fields else str(fields.get(col) or "")


def is_ksi_excluded(fields: dict) -> bool:
    """True iff the case is a Known-Systemic-Issue that should be NULL for TTR.

    Requires a positive systemic marker grounded in the actual case fields:
      * a ``KSI -`` / ``KSI:`` tag in ``Root_Cause_Description`` (self-sufficient — the
        tag IS the known-systemic + pending-fix signal support stamps on these cases), OR
      * a populated ``Bug_Id`` AND a pending-Eng-fix phrase (SOP "Outcome 3") in
        ``Root_Cause_Description`` / ``Root_Cause`` (marker (a) + pending (b) together).

    A genuinely empty/absent marker never fires (conservative: wrongly nulling a real
    TTR defect is worse than auditing a KSI case the ``<7 days`` gate already largely
    handles).
    """
    rcd = _get(fields, F_ROOT_CAUSE_DESC)
    rc = _get(fields, F_ROOT_CAUSE)
    text = f"{rcd}\n{rc}"

    # Marker A: explicit KSI tag in the root-cause description (or root cause).
    if _KSI_TAG_RE.search(text):
        return True

    # Marker B: a real bug pending an Eng-side systemic fix (SOP Outcome 3).
    bug = _get(fields, F_BUG_ID)
    if not _is_empty(bug) and _PENDING_BUG_RE.search(text):
        return True

    return False


def ksi_reason(fields: dict) -> str:
    """Human-readable reason a case is KSI-excluded ("" if not). For audit dumps."""
    rcd = _get(fields, F_ROOT_CAUSE_DESC)
    rc = _get(fields, F_ROOT_CAUSE)
    text = f"{rcd}\n{rc}"
    if _KSI_TAG_RE.search(text):
        return "KSI tag in Root_Cause_Description"
    bug = _get(fields, F_BUG_ID)
    if not _is_empty(bug) and _PENDING_BUG_RE.search(text):
        return f"Bug_Id {bug.strip()} + pending-Eng-fix (Outcome 3)"
    return ""
