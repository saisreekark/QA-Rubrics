"""Run the TUNED pipeline locally with REAL KB + genai caching (prod-faithful).

Unlocked by Rishita's creds (the prod cell-7 identity, read from Dataform HEAD):
they read all 4 KB docs AND can call Vertex. This driver uses the *notebook's own*
global-genai caching path (not regen's inline path): the real KB is baked into a
google-genai context cache ONCE, so per-case calls are small → fast + network-resilient
(unlike `regen --kb-snapshot`, which re-inlines ~197K of KB on every call and crawls).

Identity:
  * KB docs   -> Rishita's creds (SharedKnowledgeBase creds)
  * Vertex / genai cache+calls -> Rishita via ADC (written to the ADC well-known path)
  * input sheet -> Rishita's creds (she can read the Tricks I/O sheet)

Output: a regen-shaped CSV (Case_Number + 6 *_RCA_Output), gated + grounded exactly as
prod (process_single_row applies the cell-9 gates: Reopen_Counter>0 / aging>=7 / KSI /
hygiene). Feed it to ground_hygiene_csv -> merge -> runner --judge-source regen ->
gated_reason -> export_send, same as any regen CSV.

Usage:
  python3 -m evaluator.run_prod_kb --sample 3   --out evaluator/runs/_kbtest.csv     # smoke
  python3 -m evaluator.run_prod_kb --sample 500 --out evaluator/runs/curate_prod_500.csv
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import time
from pathlib import Path

import pandas as pd
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from . import config as cfg
from . import regen

RISHITA_PATH = os.path.expanduser("~/.rishita_creds.json")
ADC_PATH = os.path.expanduser("~/.config/gcloud/application_default_credentials.json")
OUT_KEYS = {  # process_single_row results_map key -> output column
    "out_reopen": "Reopen_RCA_Output", "out_ttr": "TTR_RCA_Output",
    "out_escalation": "Escalation_RCA_Output", "out_dsat": "DSAT_RCA_Output",
    "out_quality": "Quality_RCA_Output", "out_workflow": "Workflow_RCA_Output",
}


def _rishita() -> dict:
    return json.load(open(RISHITA_PATH))


def _kb_creds(rc: dict) -> Credentials:
    c = Credentials(token=rc.get("token"), refresh_token=rc["refresh_token"],
                    client_id=rc["client_id"], client_secret=rc["client_secret"],
                    token_uri=rc["token_uri"],
                    scopes=["https://www.googleapis.com/auth/drive"])
    c.refresh(Request())
    return c


def _install_adc(rc: dict) -> None:
    """Write Rishita's authorized_user ADC so the notebook's _global_genai_client()
    (google.auth.default) calls Vertex as Rishita — the identity that can both read
    the KB and run the pipeline in prod."""
    os.makedirs(os.path.dirname(ADC_PATH), exist_ok=True)
    if os.path.exists(ADC_PATH) and not os.path.exists(ADC_PATH + ".bak"):
        os.rename(ADC_PATH, ADC_PATH + ".bak")
    json.dump({"type": "authorized_user", "client_id": rc["client_id"],
               "client_secret": rc["client_secret"], "refresh_token": rc["refresh_token"]},
              open(ADC_PATH, "w"))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--sample", type=int, default=3)
    p.add_argument("--months", nargs="+", default=["2026-03", "2026-04"])
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--concurrency", type=int, default=12)
    p.add_argument("--model", default="gemini-3.1-pro-preview")
    args = p.parse_args()

    rc = _rishita()
    _install_adc(rc)
    kb_creds = _kb_creds(rc)            # Rishita: KB docs only
    sheet_creds = regen._build_credentials()  # saisreekark: gold + input sheets

    import vertexai
    vertexai.init(project=cfg.PROJECT_ID, location=cfg.LOCATION, credentials=kb_creds)
    ns = regen.load_pipeline(agent4_temp=0.0)  # installs the notebook global caching path
    ns["JOB_CONFIG"]["agent_model"] = args.model
    ns["JOB_CONFIG"]["model_temperature"] = 0.0
    for fw in ns["FRAMEWORK_CONFIGS"].values():
        for a in fw["agents"]:
            a["temperature"] = 0.0

    # gold cases (union across frameworks), then sample — read with saisreekark
    from gspread_pandas import Spread
    gold = Spread(cfg.QA2026_SPREADSHEET_ID, creds=sheet_creds)
    cases: set[str] = set()
    for fw in ["Reopen", "TTR", "Escalation", "DSAT", "Quality", "Workflow"]:
        cases |= regen._gold_case_set(gold, fw, tuple(args.months))
    rows = regen._read_input_rows(ns, sheet_creds, cases)
    if args.sample < len(rows):
        rows = list(pd.DataFrame(rows).sample(n=args.sample, random_state=42).to_dict("records"))
    print(f"running {len(rows)} cases (of {len(cases)} gold) with REAL KB + genai caching")

    # REAL KB -> genai context caches (created once)
    kb = ns["SharedKnowledgeBase"](ns["DOC_MAPPING"], ns["SHEET_MAPPING"], kb_creds)
    t0 = time.time()
    kb.create_agent_caches(ns["FRAMEWORK_CONFIGS"], ns["JOB_CONFIG"]["agent_model"])
    print(f"KB caches created in {time.time()-t0:.0f}s; KB text = {len(kb.common_docs_text):,} chars")

    psr = ns["process_single_row"]
    sem = asyncio.Semaphore(args.concurrency)

    async def go():
        return await asyncio.gather(*(psr(r, sem, kb) for r in rows))

    t0 = time.time()
    results = asyncio.run(go())
    print(f"pipeline done in {time.time()-t0:.0f}s")

    key = ns["COL_MAPPING"]["case_number"]
    recs = []
    for r, res in zip(rows, results):
        rec = {"Case_Number": str(r.get(key, "")).strip()}
        for k, col in OUT_KEYS.items():
            v = res.get(k)
            rec[col] = "" if v is None else (v if isinstance(v, str) else json.dumps(v))
        recs.append(rec)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["Case_Number", *OUT_KEYS.values()])
        w.writeheader()
        w.writerows(recs)
    print(f"wrote {len(recs)} -> {args.out}")

    try:
        kb.delete_all()
    except Exception:
        pass


if __name__ == "__main__":
    main()
