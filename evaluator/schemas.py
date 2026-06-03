"""Pydantic schemas for the judge output.

Passed to Vertex as ``response_schema`` so the judge cannot return malformed
JSON — same defensive posture as Lever 1 in docs/prompts-strategy.md.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

Verdict = Literal["Correct", "Incorrect", "Borderline", "NotApplicable"]
Framework = Literal["Reopen", "TTR", "Escalation", "DSAT", "Quality", "Workflow"]


class JudgeVerdict(BaseModel):
    case_number: str
    framework: Framework
    primary_driver_correct: Optional[bool] = None
    primary_driver_reason: str = ""
    secondary_driver_correct: Optional[bool] = None
    secondary_driver_reason: Optional[str] = None
    overall_verdict: Verdict
    confidence: float = Field(ge=0.0, le=1.0)
    judge_model: str
    judged_at: datetime


CSV_COLUMNS = [
    "case_number",
    "framework",
    "primary_driver_correct",
    "primary_driver_reason",
    "secondary_driver_correct",
    "secondary_driver_reason",
    "overall_verdict",
    "confidence",
    "judge_model",
    "judged_at",
]
