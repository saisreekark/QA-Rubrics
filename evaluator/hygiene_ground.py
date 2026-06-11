"""Deterministic field-grounding for the Workflow "case hygiene" driver (task 4.7).

The Workflow bot fires the L3 driver ``Missing vector case hygiene fields`` on the
overwhelming majority of cases by *hallucinating* that ``Root_Cause`` /
``Root_Cause_Description`` are empty — the actual empty-rate is ~1% (diagnosed in the
2026-06-08 spike; see ``docs/session-2026-06-05-6driver.md`` §10). A prompt rewrite can't
fix it because the model ignores the real field values. So we ground the rule in code:
read the *actual* case fields and suppress the driver unless an emptiness genuinely exists.

This is the single source of truth for the grounding logic. ``evaluator.ground_hygiene_csv``
uses it to post-filter a regen CSV for measurement; the production notebook mirrors the same
function inline as a gated post-filter (the notebook can't import this package).

Rule 9 reference: ``prompts/workflow/agent2.md`` lines 85-88.

Note on ``Next_Steps``: the human gold keys the hygiene defect on **empty Next_Steps**,
not empty Root_Cause — on the 2026-06-08 held-out May set, 6/8 gold "missing hygiene"
cases have populated Root_Cause/Root_Cause_Description and empty ``Next_Steps``. So the
correct grounding is the *literal* rule 9 (any of the three fields empty), which is the
default (``include_next_steps=True``): it suppresses the pure-hallucination cases (every
hygiene field populated, bot fired anyway) while preserving the genuine empty-Next_Steps
firings → Workflow F1 17.0→23.9 on held-out May. The residual FPs (Next_Steps empty but
the reviewer did *not* flag a defect) are the genuine "does empty Next_Steps always
count?" one-line Zaidul confirm. Set ``include_next_steps=False`` for the Root_Cause/RCD-
only variant (kills ~98% of firings but also the real TPs — analysis only).
"""

from __future__ import annotations

import json

from . import config as cfg
from .multilabel_score import _norm, parse_drivers  # noqa: F401  (parse_drivers re-export)

HYGIENE_L3 = "Missing vector case hygiene fields"

# Case-field column names as they appear in the input sheet ("Cases for Summary")
# and the agent-2 prompt template variables.
F_CASE_STATUS = "Case_Status"
F_ROOT_CAUSE = "Root_Cause"
F_ROOT_CAUSE_DESC = "Root_Cause_Description"
F_NEXT_STEPS = "Next_Steps"
F_ISSUE_TYPE = "Issue_Type"  # falls back to Issue_Category if absent
# Compensation/Attainment-Help extra mandatory fields (rule 9, second clause).
F_COMP_EXTRA = ("Next Steps Due Date", "Deal Attribution Root Cause", "Channel_Neutrality")

_EMPTY_SENTINELS = {"", "none", "n/a", "na", "nan", "null"}


def _is_empty(v) -> bool:
    """True for None / blank / the usual empty sentinels (case-insensitive)."""
    if v is None:
        return True
    s = str(v).strip().lower()
    return s in _EMPTY_SENTINELS


def _field_empty(fields: dict, col: str) -> bool:
    """True only if the column is *present in the data* AND its value is empty.

    A column that is absent from the source is "unknown", not "empty" — we have no
    grounding signal for it, so it must not trigger a violation (otherwise a field
    the input sheet simply doesn't carry would resurrect the hallucinated firing).
    """
    return col in fields and _is_empty(fields[col])


def _issue_type(fields: dict) -> str:
    val = fields.get(F_ISSUE_TYPE)
    if val is None or str(val).strip() == "":
        val = fields.get("Issue_Category", "")
    return str(val or "").strip().lower()


def hygiene_violation(fields: dict, include_next_steps: bool = True) -> bool:
    """Deterministic rule-9 verdict from the *actual* case fields.

    A violation exists only when the case is Closed AND a mandatory categorization
    field is genuinely empty. ``Root_Cause`` / ``Root_Cause_Description`` are the
    always-required fields; ``Next_Steps`` is gated (see module docstring). For
    Compensation / Attainment-Help cases the extra fields are also required.
    """
    if _norm(fields.get(F_CASE_STATUS, "")) != _norm("Closed"):
        return False
    if _field_empty(fields, F_ROOT_CAUSE) or _field_empty(fields, F_ROOT_CAUSE_DESC):
        return True
    if include_next_steps and _field_empty(fields, F_NEXT_STEPS):
        return True
    itype = _issue_type(fields)
    if "compensation" in itype or "attainment" in itype:
        if any(_field_empty(fields, c) for c in F_COMP_EXTRA):
            return True
    return False


def empty_hygiene_fields(fields: dict, include_next_steps: bool = True) -> list[str]:
    """Display-names of the mandatory hygiene fields that are *genuinely* empty.

    Used to rewrite a legit hygiene driver's justification precisely — the bot's
    own boilerplate claims all three fields are empty even when only ``Next_Steps``
    is, which a field-aware reviewer rightly rejects.
    """
    out: list[str] = []
    if _field_empty(fields, F_ROOT_CAUSE):
        out.append("Root_Cause")
    if _field_empty(fields, F_ROOT_CAUSE_DESC):
        out.append("Root_Cause_Description")
    if include_next_steps and _field_empty(fields, F_NEXT_STEPS):
        out.append("Next_Steps")
    itype = _issue_type(fields)
    if "compensation" in itype or "attainment" in itype:
        out += [c for c in F_COMP_EXTRA if _field_empty(fields, c)]
    return out


def _precise_hygiene_justification(fields: dict, include_next_steps: bool = True) -> str | None:
    empties = empty_hygiene_fields(fields, include_next_steps=include_next_steps)
    if not empties:
        return None
    return (f"Case is Closed and the mandatory hygiene field(s) "
            f"{', '.join(empties)} are empty at closure.")


def _is_hygiene_driver(d: dict) -> bool:
    return (
        isinstance(d, dict)
        and _norm(d.get("L2", "")) == _norm(cfg.WORKFLOW_ADHERENCE_L2)
        and _norm(d.get("L3", "")) == _norm(HYGIENE_L3)
    )


def ground_workflow_output(bot_output, fields: dict, include_next_steps: bool = True):
    """Suppress a *hallucinated* hygiene driver; return ``(new_output, suppressed)``.

    Drops any ``Missing vector case hygiene fields`` driver when the actual case
    fields show no genuine emptiness, then re-keys the survivors ``driver_1..n``.
    Non-hygiene drivers and a legitimate hygiene firing are left untouched. The
    return type mirrors the input (JSON string in → JSON string out; dict in → dict
    out) so it drops into both the CSV transform and the notebook unchanged.
    """
    was_str = isinstance(bot_output, str)
    parsed = bot_output
    if was_str:
        s = bot_output.strip()
        if not s:
            return (bot_output, False)
        try:
            parsed = json.loads(s)
        except json.JSONDecodeError:
            return (bot_output, False)
    if not isinstance(parsed, dict) or "error" in parsed:
        return (bot_output, False)

    legit = hygiene_violation(fields, include_next_steps=include_next_steps)
    precise = _precise_hygiene_justification(fields, include_next_steps=include_next_steps)
    kept: list[dict] = []
    suppressed = False
    rewritten = False
    for key in sorted(parsed):  # driver_1, driver_2, ...
        d = parsed[key]
        if _is_hygiene_driver(d):
            if not legit:
                suppressed = True
                continue
            # Legit firing: replace the bot's over-claiming boilerplate with a
            # justification naming ONLY the genuinely-empty field(s).
            if precise and isinstance(d, dict) and _norm(d.get("Justification", "")) != _norm(precise):
                d = {**d, "Justification": precise}
                rewritten = True
        kept.append(d)

    if not suppressed and not rewritten:
        return (bot_output, False)

    new = {f"driver_{i}": d for i, d in enumerate(kept, start=1)}
    return (json.dumps(new) if was_str else new, suppressed or rewritten)
