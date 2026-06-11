"""Dump the live KB (SOP / T&C / Plan / DND) to a local snapshot file.

WHY: the 4 KB docs are static but 403 (`PERMISSION_DENIED`) for the personal
`saisreekark@google.com` token — a Drive ACL issue, not scope. So the regen
inner loop runs `--no-cache` and its absolutes are lower-fidelity than prod.
This script assembles the KB text EXACTLY as the pipeline does
(`SharedKnowledgeBase._load_docs_once`, the same readers + concatenation) and
writes it to a file. Point `regen --kb-snapshot <file>` at it and every
`use_cache` agent gets the real KB inlined → prod-faithful local absolutes.

WHERE TO RUN: any identity that CAN read the KB —
  * **Colab Enterprise** (Pantheon, project `gtm-cloud-helpdesk`): the runtime
    SA already has KB access (the daily scheduler reads these docs fine). Paste
    the cell printed by `--colab-cell`, or copy this module in and call `main()`.
    Write the snapshot to GCS, then `gsutil cp` it down locally.
  * **Locally**, only AFTER the 4 files are shared with `saisreekark@google.com`
    or Token-Creator is granted on the pipeline SA (then it just works here).

The KB is static (SOPs change rarely) so a periodic re-dump is enough; it is
NOT part of the per-iteration loop.

    # from a KB-capable identity:
    python3 -m evaluator.dump_kb_snapshot --out evaluator/kb_snapshot.txt
    python3 -m evaluator.dump_kb_snapshot --gcs gs://analytics_genai/kb_snapshot.txt
    # then, anywhere:
    gsutil cp gs://analytics_genai/kb_snapshot.txt evaluator/kb_snapshot.txt
    python3 -m evaluator.regen --framework Workflow --sample 200 \
        --kb-snapshot evaluator/kb_snapshot.txt --temperature 0
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from . import config as cfg
from . import regen

# Paste-ready, dependency-light cell for a Colab Enterprise notebook (runs as the
# KB-capable runtime SA). Reads the same 4 docs and writes the snapshot to GCS.
COLAB_CELL = r'''
# --- KB snapshot dumper (run in Colab Enterprise; runtime SA has KB access) ---
import datetime
from google.auth import default as _adc
from googleapiclient.discovery import build
creds, _ = _adc(scopes=["https://www.googleapis.com/auth/drive"])
DOC_MAPPING = {
    "SOP_Guide": "1LJPbOEi7eUB21ndEFx8NFLc3QRBxjF_lVf1lusRIvkw",
    "Terms_Conditions": "14uSCmn0OZB9x3Mm2Zi6HsrVI5I181mpx_ESlA2kQmak",
    "Plan_Summary": "1A3lwFGFAmiNHCTsKg2lNhn74eC0tRGYg6vaPzdyUr9g",
}
SHEET_MAPPING = {
    "Do_Not_Contact_Data": {"file_id": "1J0VyGVmWjoZBbyk7Ra9vl2Bh3mdG6ZCMADkCzBhUh6Y",
                            "tabs": ["Do NOT tag"]},
}
def _doc(doc_id):
    svc = build("docs", "v1", credentials=creds)
    def walk(els):
        out = []
        for v in els or []:
            if "paragraph" in v:
                for e in v["paragraph"]["elements"]:
                    out.append(e.get("textRun", {}).get("content", ""))
            elif "table" in v:
                for r in v["table"]["tableRows"]:
                    out.append("| " + " | ".join(
                        walk(c.get("content")).strip().replace("\n", " ")
                        for c in r["tableCells"]) + " |\n")
        return "".join(out)
    return walk(svc.documents().get(documentId=doc_id).execute()["body"]["content"])
def _sheet(file_id, tabs):
    svc = build("sheets", "v4", credentials=creds)
    meta = svc.spreadsheets().get(spreadsheetId=file_id).execute()
    titles = [s["properties"]["title"] for s in meta["sheets"]
              if (not tabs or s["properties"]["title"] in tabs)]
    res = svc.spreadsheets().values().batchGet(
        spreadsheetId=file_id, ranges=[f"'{t}'!A1:Z" for t in titles]).execute()
    out = []
    for t, vr in zip(titles, res.get("valueRanges", [])):
        out.append(f"\n--- TAB: {t} ---\n")
        for row in vr.get("values", []):
            out.append("| " + " | ".join(str(c).replace("\n", " ").strip() for c in row) + " |")
    return "\n".join(out)
text = ""
for name, did in DOC_MAPPING.items():
    text += f"\n\n=== DOCUMENT: {name} ===\n{_doc(did)}\n"
for name, cfg_ in SHEET_MAPPING.items():
    text += f"\n\n=== SPREADSHEET: {name} ===\n{_sheet(cfg_['file_id'], cfg_['tabs'])}\n"
print(f"KB assembled: {len(text):,} chars")
open("/tmp/kb_snapshot.txt", "w").write(text)
!gsutil cp /tmp/kb_snapshot.txt gs://analytics_genai/kb_snapshot.txt
print("wrote gs://analytics_genai/kb_snapshot.txt  (then: gsutil cp it down locally)")
'''


def build_snapshot() -> str:
    """Assemble the KB text exactly as the prod pipeline does."""
    creds = regen._build_credentials()
    ns = regen.load_pipeline()
    kb = ns["SharedKnowledgeBase"](ns["DOC_MAPPING"], ns["SHEET_MAPPING"], creds)
    kb._load_docs_once()
    text = kb.common_docs_text or ""
    # `_load_docs_once` still appends the `=== DOCUMENT: name ===` headers even when
    # every body 403s empty, so a headers-only result (~150 chars) is NOT a real
    # snapshot. The genuine KB (SOP+T&C+Plan+DND) is many KB — guard on length.
    if len(text.strip()) < 1000:
        raise RuntimeError(
            f"KB came back near-empty ({len(text.strip())} chars — headers only). The "
            "current identity cannot read the KB docs (403 PERMISSION_DENIED for "
            "saisreekark@google.com). Run this from a KB-capable identity (Colab "
            "Enterprise runtime SA), or get the 4 files shared / Token-Creator granted "
            "on the pipeline SA. See `--colab-cell`.")
    return text


def main() -> None:
    p = argparse.ArgumentParser(description="Dump the live KB to a snapshot file.")
    p.add_argument("--out", type=Path, default=cfg.EVAL_ROOT / "kb_snapshot.txt")
    p.add_argument("--gcs", default=None, help="Also upload to a gs:// path (via gsutil).")
    p.add_argument("--colab-cell", action="store_true",
                   help="Print a paste-ready Colab Enterprise cell and exit (no local read).")
    args = p.parse_args()

    if args.colab_cell:
        print(COLAB_CELL)
        return

    text = build_snapshot()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text)
    print(f"wrote {args.out} ({len(text):,} chars)")
    if args.gcs:
        subprocess.run(["gsutil", "cp", str(args.out), args.gcs], check=True)
        print(f"uploaded → {args.gcs}")


if __name__ == "__main__":
    main()
