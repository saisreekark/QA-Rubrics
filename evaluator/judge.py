"""One async judge call per (case, framework) → JudgeVerdict.

Mirrors the cell-9 retry posture: exponential backoff on
ResourceExhausted / ServiceUnavailable / InternalServerError, plus
ValueError so a malformed JSON response is retried instead of crashing the
batch.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from google.api_core.exceptions import (
    InternalServerError,
    ResourceExhausted,
    ServiceUnavailable,
)
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from vertexai.generative_models import GenerationConfig, GenerativeModel

from .config import JUDGE_MODEL, JUDGE_TEMPERATURE, MATCH_PROMPT_PATH, PROMPT_PATH
from .hierarchy import render_excerpt
from .schemas import JudgeVerdict


_PROMPT_CACHE: dict[str, str] = {}


def _strip_null_types(node: Any) -> Any:
    if isinstance(node, dict):
        if "anyOf" in node:
            branches = [_strip_null_types(b) for b in node["anyOf"] if not (isinstance(b, dict) and b.get("type") == "null")]
            if len(branches) == 1:
                merged = {k: v for k, v in node.items() if k != "anyOf"}
                merged.update(branches[0])
                return _strip_null_types(merged)
            node = {k: v for k, v in node.items() if k != "anyOf"}
            node["anyOf"] = branches
        return {k: _strip_null_types(v) for k, v in node.items()}
    if isinstance(node, list):
        return [_strip_null_types(v) for v in node]
    return node


def _load_prompt(path) -> str:
    key = str(path)
    if key not in _PROMPT_CACHE:
        _PROMPT_CACHE[key] = path.read_text()
    return _PROMPT_CACHE[key]


def _build_transcript_block(case_row: dict[str, Any]) -> str:
    keys = (
        "Case_Number",
        "Case_Status",
        "Case_Subject",
        "Issue_Category",
        "Reopen_Counter",
        "Case_Aging_in_Days",
        "Escalated",
        "Survey_Result",
        "Concatenated_Summary",
    )
    lines = []
    for k in keys:
        if k in case_row and case_row[k] not in (None, ""):
            lines.append(f"{k}: {case_row[k]}")
    return "\n".join(lines)


@retry(
    wait=wait_exponential(multiplier=2, min=2, max=30),
    stop=stop_after_attempt(4),
    retry=retry_if_exception_type(
        (ResourceExhausted, ServiceUnavailable, InternalServerError, ValueError)
    ),
)
async def _invoke(prompt: str, case_number: str, framework: str) -> JudgeVerdict:
    """Run one Gemini call against a formatted prompt → validated verdict.

    Shared by the from-scratch judge and the label-match judge. The retry
    posture mirrors cell 9: backoff on transient API errors, plus ValueError
    so a malformed JSON response is retried instead of crashing the batch.
    """
    model = GenerativeModel(JUDGE_MODEL)
    config = GenerationConfig(
        temperature=JUDGE_TEMPERATURE,
        response_mime_type="application/json",
        response_schema=_strip_null_types(JudgeVerdict.model_json_schema()),
    )
    response = await model.generate_content_async(prompt, generation_config=config)
    try:
        payload = json.loads(response.text)
    except (json.JSONDecodeError, AttributeError) as exc:
        raise ValueError(f"Judge returned unparseable JSON: {exc}") from exc

    # All four are authoritative from the caller — never let the model's own
    # (often hallucinated) values win. setdefault was the bug here.
    payload["case_number"] = case_number
    payload["framework"] = framework
    payload["judge_model"] = JUDGE_MODEL
    payload["judged_at"] = datetime.now(timezone.utc).isoformat()
    return JudgeVerdict.model_validate(payload)


async def judge_case_framework(
    case_row: dict[str, Any],
    framework: str,
    bot_output: Any,
) -> JudgeVerdict:
    """From-scratch judge: decide if the bot's classification fits the rubric."""
    prompt = _load_prompt(PROMPT_PATH).format(
        framework=framework,
        hierarchy_excerpt=render_excerpt(framework),
        transcript_block=_build_transcript_block(case_row),
        bot_output_json=json.dumps(bot_output, indent=2, default=str),
    )
    return await _invoke(prompt, str(case_row.get("Case_Number", "")), framework)


async def match_case_framework(
    framework: str,
    bot_output: Any,
    gold_l1: str,
    gold_l2l3: str,
    case_number: str,
) -> JudgeVerdict:
    """Label-match judge: decide if the bot agrees with the human gold label."""
    prompt = _load_prompt(MATCH_PROMPT_PATH).format(
        framework=framework,
        hierarchy_excerpt=render_excerpt(framework),
        gold_l1=gold_l1,
        gold_l2l3=gold_l2l3,
        bot_output_json=json.dumps(bot_output, indent=2, default=str),
    )
    return await _invoke(prompt, case_number, framework)
