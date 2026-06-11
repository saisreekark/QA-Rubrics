"""Regen harness — re-run the production pipeline locally with the *current*
local prompts + HIERARCHY_CONFIG, so a prompt/driver change yields a
measurable accuracy delta instead of nothing.

Why this exists: `--match-labels` scores the *frozen* bot predictions already
sitting in a sheet. To see the effect of a Phase-4 prompt/driver edit we must
regenerate predictions. This loads the pipeline definition cells out of
``notebook/content.ipynb`` (cells 2,4,5,6,8,9 — config, hierarchy, prompts,
agent config, helpers, pipeline), wires auth + KB context-caching, runs the
four driver frameworks on the QA-2026 gold cases (inputs read live from
``Cases for Summary``), and writes a CSV in the ``*_RCA_Output`` shape that
``evaluator.regen_score`` then label-matches against the QA-2026 gold.

LOCAL ONLY. It never writes pipeline config back to the Dataform notebook
(the daily scheduler runs that copy) and never writes to a shared sheet.

    python3 -m evaluator.regen --sample 30 --framework TTR Reopen Escalation DSAT
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Imports the notebook cells expect in their namespace (cell 1 minus the pip line).
import datetime as _dt  # noqa: F401  (cells reference `datetime` the module)
import re  # noqa: F401
import numpy as np  # noqa: F401
import pandas as pd
import pytz  # noqa: F401
import vertexai
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build  # noqa: F401
from gspread_pandas import Spread
from tenacity import (  # noqa: F401
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from vertexai.generative_models import GenerativeModel, Part  # noqa: F401
from vertexai.preview import caching  # noqa: F401

from . import config as cfg
from . import gold_dump

NOTEBOOK = cfg.NOTEBOOK_PATH
PIPELINE_CELLS = [2, 4, 5, 6, 8, 9]  # config, hierarchy, prompts, agent cfg, helpers, pipeline
DRIVER_FRAMEWORKS = ("Reopen", "TTR", "Escalation", "DSAT")
# The pipeline worker (run_framework_pipeline) is framework-generic, so Quality
# and Workflow regen through the same path — they just score on a different
# (multi-label/detection) metric via evaluator.multilabel_score, not the driver
# judge. Keep them OUT of the default so a bare `regen` stays driver-only.
ALL_FRAMEWORKS = DRIVER_FRAMEWORKS + cfg.MULTILABEL_FRAMEWORKS


def _gold_case_set(gold, framework: str, driver_months) -> set[str]:
    """Case-number universe for one framework's gold (driver vs multilabel)."""
    if framework == "Quality":
        g = gold_dump.load_quality_labels_2026(gold, months=cfg.QA2026_QUALITY_MONTHS)
    elif framework == "Workflow":
        g = gold_dump.load_workflow_labels_2026(gold, months=cfg.QA2026_WORKFLOW_MONTHS)
    else:
        g = gold_dump.load_labels_2026(gold, framework, months=tuple(driver_months))
    return set(g["case_number"])


class _NoCacheKB:
    """Stand-in for SharedKnowledgeBase when --no-cache is set: the pipeline
    still calls .get_cache(), but every lookup misses so the use_cache agents
    fall back to a plain GenerativeModel (no KB context — lower fidelity)."""

    def get_cache(self, *args, **kwargs):
        return None


class _SnapshotKB:
    """KB from a local snapshot file instead of a live Drive read.

    The 4 KB docs (SOP/T&C/Plan/DND) are static and 403 for the personal
    `saisreekark@google.com` token (Drive ACL, not scope) — so they can't be
    read locally. But a KB-capable identity (the Colab-Enterprise runtime SA)
    can dump the assembled KB text once via ``evaluator.dump_kb_snapshot``;
    point ``--kb-snapshot`` at that file and every ``use_cache`` agent gets the
    SAME KB content prod bakes into its cache. Inlining (vs Vertex caching)
    changes cost/latency, NOT accuracy — so local absolutes become prod-faithful
    without any live Drive access. Returns an inline payload the global
    gemini-3 adapter understands."""

    def __init__(self, text: str):
        self._payload = {"inline": text}

    def get_cache(self, *args, **kwargs):
        return self._payload


def _install_global_genai(ns: dict, model_name: str, creds) -> None:
    """Route the bot pipeline through a global-endpoint model via google-genai.

    Gemini 3.x (e.g. gemini-3.1-pro-preview) is only served from the `global`
    location, which the legacy vertexai SDK in the notebook can't target. We
    swap `ModelRegistry.get_model` for an adapter that exposes the same
    `generate_content_async(prompt).text` interface the pipeline expects.
    Only valid with --no-cache (this path ignores Vertex context caching).
    The matcher/judge is untouched — the measurement instrument stays fixed.

    Auth: use auto-refreshing ADC credentials (not the static one-shot token),
    because the global v1beta1 endpoint intermittently 401s
    (ACCESS_TOKEN_TYPE_UNSUPPORTED) on the static token under concurrency — which
    silently decimated the Agent-4 aggregator. ADC handles concurrent calls
    cleanly; fall back to the passed static creds if ADC is unavailable.
    """
    from google import genai
    import google.auth

    try:
        gcreds, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"])
        try:
            gcreds = gcreds.with_quota_project(cfg.PROJECT_ID)
        except Exception:  # noqa: BLE001 — some cred types lack with_quota_project
            pass
    except Exception:  # noqa: BLE001 — no ADC: keep the static token
        gcreds = creds

    client = genai.Client(vertexai=True, project=cfg.PROJECT_ID, location="global", credentials=gcreds)

    class _GenAIModel:
        def __init__(self, system_prompt: str, temperature: float, inline_kb: str | None = None):
            self._sys, self._temp, self._inline = system_prompt, temperature, inline_kb

        async def generate_content_async(self, prompt):
            conf = {"temperature": self._temp, "response_mime_type": "text/plain"}
            sys = self._sys or ""
            if self._inline:  # KB snapshot inlined (same content prod caches; see _SnapshotKB)
                sys = self._inline + "\n\n" + sys
            if sys:
                conf["system_instruction"] = sys
            return await client.aio.models.generate_content(
                model=model_name, contents=prompt, config=conf
            )

    _cache: dict = {}

    def get_model(agent_name, system_prompt, temperature, use_cache=False, cache_obj=None):
        inline_kb = None
        if use_cache and isinstance(cache_obj, dict) and "inline" in cache_obj:
            inline_kb = cache_obj["inline"]
        key = (agent_name, temperature, bool(inline_kb))
        if key not in _cache:
            _cache[key] = _GenAIModel(system_prompt, temperature, inline_kb)
        return _cache[key]

    ns["ModelRegistry"].get_model = staticmethod(get_model)
    ns["JOB_CONFIG"]["agent_model"] = model_name


def _build_credentials() -> Credentials:
    token = cfg.get_oauth_token()
    return Credentials(
        token=token,
        token_uri="https://oauth2.googleapis.com/token",
        quota_project_id=cfg.PROJECT_ID,
    )


def _build_vertex_credentials():
    """Auto-refreshing ADC creds for the Vertex matcher (regional `vertexai.init`).

    The static `GOOGLE_OAUTH_TOKEN` is a one-shot access token with no refresh
    token, so it 401s ~1h in — which silently decimates long N-run A/Bs and
    calibration runs (the matcher call raises, the case drops from the
    denominator). ADC (`google.auth.default`) auto-refreshes. Vertex only needs
    the cloud-platform scope, so this is independent of the drive-scoped Sheets
    token (keep using `_build_credentials()` for `Spread`). Falls back to the
    static token if ADC isn't available.
    """
    try:
        import google.auth
        gcreds, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"])
        try:
            gcreds = gcreds.with_quota_project(cfg.PROJECT_ID)
        except Exception:  # noqa: BLE001 — some cred types lack with_quota_project
            pass
        return gcreds
    except Exception:  # noqa: BLE001 — no ADC: fall back to the static token
        return _build_credentials()


def load_pipeline(agent4_temp: float | None = None) -> dict[str, Any]:
    """Exec the notebook's definition cells into a fresh namespace and return it.

    Provides the imports + a local logger the cells assume, then runs cells
    2,4,5,6,8,9 in order. Cells 1 (pip), 3 (cloud logging), 7 (auth) and 10/11
    (the production read/loop) are deliberately skipped.

    ``agent4_temp`` overrides the aggregator's temperature, which cell 9
    hardcodes to 0.2 (`ModelRegistry.get_model(... temperature = 0.2)`). The
    per-agent ``--temperature`` flag can't reach it because it's a literal in
    the pipeline source, so we patch the source string before exec. Needed for
    a deterministic A/B — the aggregator picks the *final* driver.
    """
    nb = json.loads(NOTEBOOK.read_text())
    ns: dict[str, Any] = {
        # modules / symbols the cells reference at module scope
        "asyncio": asyncio, "datetime": _dt, "pytz": pytz, "json": json, "re": re,
        "time": time, "pd": pd, "np": np, "vertexai": vertexai,
        "GenerativeModel": GenerativeModel, "Part": Part, "caching": caching,
        "Credentials": Credentials, "Spread": Spread, "build": build,
        "retry": retry, "wait_exponential": wait_exponential,
        "stop_after_attempt": stop_after_attempt,
        "retry_if_exception_type": retry_if_exception_type,
        "logger": logging.getLogger("regen"),
    }
    from google.api_core.exceptions import (
        InternalServerError, ResourceExhausted, ServiceUnavailable,
    )
    ns.update(ResourceExhausted=ResourceExhausted, ServiceUnavailable=ServiceUnavailable,
              InternalServerError=InternalServerError)
    for idx in PIPELINE_CELLS:
        src = "".join(nb["cells"][idx]["source"])
        # strip notebook-only shell/magic lines just in case
        src = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith(("!", "%")))
        if idx == 9 and agent4_temp is not None:
            patched = src.replace("temperature = 0.2", f"temperature = {agent4_temp}")
            if patched == src:
                raise RuntimeError("agent-4 'temperature = 0.2' not found in cell 9 to patch")
            src = patched
        exec(compile(src, f"<cell {idx}>", "exec"), ns)
    return ns


def _read_input_rows(ns: dict, creds: Credentials, case_numbers: set[str]) -> list[dict]:
    """Read the live input tab, keep only the requested gold cases."""
    io = ns["IO_CONFIG"]
    spread = Spread(io["spreadsheet_id"], creds=creds)
    df = spread.sheet_to_df(sheet=io["input_sheet_name"], index=None)
    key = ns["COL_MAPPING"]["case_number"]
    df[key] = df[key].astype(str).str.strip()
    df = df[df[key].isin(case_numbers)].drop_duplicates(subset=key, keep="last")
    return df.to_dict(orient="records")


REGEN_CONCURRENCY = int(os.environ.get("REGEN_CONCURRENCY", "2"))  # low default to
# stay under the regional per-minute quota; raise via env when the bot runs on the
# global endpoint (--force-global), whose pool is separate from the regional matcher.


async def _regen_rows(ns: dict, rows: list[dict], frameworks: list[str], kb,
                      concurrency: int = REGEN_CONCURRENCY) -> list[dict]:
    run_fw = ns["run_framework_pipeline"]
    fw_cfg = ns["FRAMEWORK_CONFIGS"]
    key = ns["COL_MAPPING"]["case_number"]
    out_col = {  # framework -> the *_RCA_Output column name
        fw: cfg.FRAMEWORK_TO_OUTPUT_COL[fw] for fw in frameworks
    }
    sem = asyncio.Semaphore(concurrency)

    async def one(row):
        rec = {"Case_Number": str(row.get(key, "")).strip()}
        async with sem:
            for fw in frameworks:
                try:
                    rec[out_col[fw]] = await run_fw(row, fw, fw_cfg[fw]["agents"], kb)
                except Exception as exc:  # noqa: BLE001 — keep the batch alive
                    rec[out_col[fw]] = json.dumps({"error": str(exc)})
        return rec

    return await asyncio.gather(*(one(r) for r in rows))


def main() -> None:
    p = argparse.ArgumentParser(description="Regen harness (local pipeline re-run)")
    p.add_argument("--sample", type=int, default=10, help="Number of gold cases to regen.")
    p.add_argument("--framework", nargs="+", choices=list(ALL_FRAMEWORKS),
                   default=list(DRIVER_FRAMEWORKS),
                   help="Frameworks to regen. Adds Quality/Workflow (scored by "
                   "the multilabel detection metric, not the driver judge).")
    p.add_argument("--months", nargs="+", default=["2026-02", "2026-03"])
    p.add_argument("--no-cache", action="store_true",
                   help="Skip KB context-cache creation (faster, lower fidelity).")
    p.add_argument("--kb-snapshot", type=Path, default=None,
                   help="Path to a KB snapshot text file (produced by "
                   "`python3 -m evaluator.dump_kb_snapshot` from a KB-capable "
                   "identity, e.g. Colab Enterprise). Inlines the REAL KB into the "
                   "use_cache agents so local absolutes are prod-faithful without "
                   "live Drive access. Implies the global gemini-3 path; overrides "
                   "--no-cache for the KB.")
    p.add_argument("--model", default="gemini-3.1-pro-preview",
                   help="Bot model (default gemini-3.1-pro-preview). Gemini 3.x "
                   "is routed via the global endpoint (google-genai) and forces "
                   "--no-cache (no regional context cache). Pass "
                   "--model gemini-2.5-pro for the regional cached path.")
    p.add_argument("--temperature", type=float, default=None,
                   help="Override every agent's temperature. Use 0.0 for a "
                   "deterministic A/B so the old-vs-new delta isn't swamped by "
                   "run-to-run noise (production default is 0.3).")
    p.add_argument("--out", type=Path, default=None)
    args = p.parse_args()
    logging.basicConfig(level=logging.WARNING)

    creds = _build_credentials()
    vertexai.init(project=cfg.PROJECT_ID, location=cfg.LOCATION, credentials=creds)
    # --temperature drives sub-agents (config) AND the aggregator (source patch).
    ns = load_pipeline(agent4_temp=args.temperature)

    if args.temperature is not None:  # deterministic A/B: isolate the prompt effect
        ns["JOB_CONFIG"]["model_temperature"] = args.temperature
        for fw in ns["FRAMEWORK_CONFIGS"].values():
            for agent in fw["agents"]:
                agent["temperature"] = args.temperature

    if args.model and args.model != ns["JOB_CONFIG"]["agent_model"]:
        if not args.no_cache:  # global endpoint can't use the regional KB cache
            logging.warning("--model %s is global-only; forcing --no-cache.", args.model)
            args.no_cache = True
        _install_global_genai(ns, args.model, creds)

    # Which gold cases to regen (union across requested frameworks).
    gold = Spread(cfg.QA2026_SPREADSHEET_ID, creds=creds)
    gold_cases: set[str] = set()
    for fw in args.framework:
        gold_cases |= _gold_case_set(gold, fw, args.months)
    rows = _read_input_rows(ns, creds, gold_cases)
    if args.sample < len(rows):
        rows = list(pd.DataFrame(rows).sample(n=args.sample, random_state=42).to_dict("records"))
    print(f"Regenerating {len(rows)} cases × {len(args.framework)} frameworks "
          f"(of {len(gold_cases)} gold cases)")

    # KB context caches for the use_cache=True final agents (fidelity).
    if args.kb_snapshot:
        kb_text = Path(args.kb_snapshot).read_text()
        kb = _SnapshotKB(kb_text)
        print(f"KB: inlining snapshot {args.kb_snapshot} ({len(kb_text):,} chars) "
              f"into use_cache agents — prod-faithful, no live Drive read.")
    elif args.no_cache:
        kb = _NoCacheKB()
    else:
        kb = ns["SharedKnowledgeBase"](ns["DOC_MAPPING"], ns["SHEET_MAPPING"], creds)
        kb.create_agent_caches(ns["FRAMEWORK_CONFIGS"], ns["JOB_CONFIG"]["agent_model"])

    verdicts = asyncio.run(_regen_rows(ns, rows, args.framework, kb))
    if not args.no_cache:
        try:
            kb.delete_all()
        except Exception:  # noqa: BLE001
            pass

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    out_path = args.out or (cfg.RUNS_DIR / f"regen_{stamp}.csv")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cols = ["Case_Number"] + [cfg.FRAMEWORK_TO_OUTPUT_COL[fw] for fw in args.framework]
    with out_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for rec in verdicts:
            w.writerow({c: rec.get(c, "") for c in cols})
    print(f"Wrote {len(verdicts)} regen predictions → {out_path}")


if __name__ == "__main__":
    main()
