"""Verify the 4-doc KB read — the gate for prod-faithful ABSOLUTE local scoring.

Background: the inner loop runs ``--no-cache`` because the 4 KB docs 403 for the local
identity, so local absolutes are KB-lite (delta-only). The 2026-06-09 finding
([[reference_kb_source_docs]]) is that 2 of the docs DO read via the Drive **export**
API once the ``x-goog-user-project: gtm-cloud-helpdesk`` quota-project header is attached
— i.e. the earlier 403 may have been a missing quota project, not a hard Drive ACL. If
all 4 read, the prod-faithful KB-snapshot path is unblocked with **no SA ACL grant** and
we can quote true "% toward 80%".

This probe tests, per KB doc, BOTH read paths with quota-project creds:
  * path A — the pipeline's NATIVE readers (Docs API ``documents().get`` /
    Sheets API), exactly what ``SharedKnowledgeBase`` uses in prod;
  * path B — the Drive **export** endpoint (``files().export``, text/plain), the one
    the 2026-06-09 read used.
Then, if every doc came back with real content on at least one path, it assembles the
snapshot and writes it (``--out``) so ``regen --kb-snapshot`` yields prod-faithful
absolutes.

    export GOOGLE_OAUTH_TOKEN="$(gcloud auth print-access-token)"
    python3 -m evaluator.kb_probe                       # probe only
    python3 -m evaluator.kb_probe --write               # probe + write snapshot if all 4 read
"""

from __future__ import annotations

import argparse
import io

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from . import config as cfg

DOC_MAPPING = {
    "SOP_Guide": "1LJPbOEi7eUB21ndEFx8NFLc3QRBxjF_lVf1lusRIvkw",
    "Terms_Conditions": "14uSCmn0OZB9x3Mm2Zi6HsrVI5I181mpx_ESlA2kQmak",
    "Plan_Summary": "1A3lwFGFAmiNHCTsKg2lNhn74eC0tRGYg6vaPzdyUr9g",
}
SHEET_MAPPING = {
    "Do_Not_Contact_Data": {"file_id": "1J0VyGVmWjoZBbyk7Ra9vl2Bh3mdG6ZCMADkCzBhUh6Y",
                            "tabs": ["Do NOT tag"]},
}
_REAL = 200  # chars: below this, treat as a 403/empty (headers-only) non-read


def _creds() -> Credentials:
    return Credentials(
        token=cfg.get_oauth_token(),
        token_uri="https://oauth2.googleapis.com/token",
        quota_project_id=cfg.PROJECT_ID,
    )


def _short(e: Exception) -> str:
    s = str(e).replace("\n", " ")
    return (s[:120] + "…") if len(s) > 120 else s


# --- path A: native pipeline readers ---------------------------------------
def read_doc_native(creds, doc_id: str) -> tuple[str, str]:
    try:
        svc = build("docs", "v1", credentials=creds)
        body = svc.documents().get(documentId=doc_id).execute().get("body", {}).get("content", [])
        out = []
        def walk(els):
            for v in els or []:
                if "paragraph" in v:
                    for e in v["paragraph"]["elements"]:
                        out.append(e.get("textRun", {}).get("content", ""))
                elif "table" in v:
                    for r in v["table"]["tableRows"]:
                        for c in r["tableCells"]:
                            walk(c.get("content"))
        walk(body)
        return "".join(out), ""
    except Exception as e:  # noqa: BLE001
        return "", _short(e)


def read_sheet_native(creds, file_id: str, tabs) -> tuple[str, str]:
    try:
        svc = build("sheets", "v4", credentials=creds)
        meta = svc.spreadsheets().get(spreadsheetId=file_id).execute()
        titles = [s["properties"]["title"] for s in meta["sheets"]
                  if (not tabs or s["properties"]["title"] in tabs)]
        res = svc.spreadsheets().values().batchGet(
            spreadsheetId=file_id, ranges=[f"'{t}'!A1:Z" for t in titles]).execute()
        out = []
        for t, vr in zip(titles, res.get("valueRanges", [])):
            out.append(f"\n--- TAB: {t} ---")
            for row in vr.get("values", []):
                out.append("| " + " | ".join(str(c).strip() for c in row) + " |")
        return "\n".join(out), ""
    except Exception as e:  # noqa: BLE001
        return "", _short(e)


# --- path B: Drive export endpoint -----------------------------------------
def read_doc_export(creds, doc_id: str) -> tuple[str, str]:
    try:
        svc = build("drive", "v3", credentials=creds)
        req = svc.files().export_media(fileId=doc_id, mimeType="text/plain")
        buf = io.BytesIO()
        dl = MediaIoBaseDownload(buf, req)
        done = False
        while not done:
            _, done = dl.next_chunk()
        return buf.getvalue().decode("utf-8", "replace"), ""
    except Exception as e:  # noqa: BLE001
        return "", _short(e)


def main() -> None:
    ap = argparse.ArgumentParser(description="Verify the 4-doc KB read.")
    ap.add_argument("--write", action="store_true", help="Write the snapshot if all 4 read.")
    ap.add_argument("--out", default=str(cfg.EVAL_ROOT / "kb_snapshot.txt"))
    args = ap.parse_args()

    creds = _creds()
    print(f"identity: quota_project={cfg.PROJECT_ID}; token len={len(cfg.get_oauth_token())}\n")

    assembled: dict[str, str] = {}
    all_ok = True
    print(f"{'doc':<22}{'native':<28}{'export':<28}")
    for name, did in DOC_MAPPING.items():
        a_txt, a_err = read_doc_native(creds, did)
        b_txt, b_err = read_doc_export(creds, did)
        a_ok, b_ok = len(a_txt) >= _REAL, len(b_txt) >= _REAL
        best = a_txt if a_ok else (b_txt if b_ok else "")
        if best:
            assembled[name] = best
        else:
            all_ok = False
        print(f"{name:<22}"
              f"{(f'{len(a_txt):,} chars' if a_ok else f'403/empty: {a_err[:14]}'):<28}"
              f"{(f'{len(b_txt):,} chars' if b_ok else f'403/empty: {b_err[:14]}'):<28}")

    for name, sc in SHEET_MAPPING.items():
        a_txt, a_err = read_sheet_native(creds, sc["file_id"], sc["tabs"])
        a_ok = len(a_txt) >= _REAL
        if a_ok:
            assembled[name] = a_txt
        else:
            all_ok = False
        print(f"{name:<22}"
              f"{(f'{len(a_txt):,} chars' if a_ok else f'403/empty: {a_err[:14]}'):<28}"
              f"{'(sheet: native only)':<28}")

    n = len(DOC_MAPPING) + len(SHEET_MAPPING)
    print(f"\n→ {len(assembled)}/{n} KB docs read with real content.")
    if all_ok:
        print("  ✅ ALL 4 read — prod-faithful absolute scoring is UNBLOCKED.")
    else:
        print("  ❌ Not all 4 read — absolutes stay KB-lite / delta-only.")

    if args.write and all_ok:
        text = ""
        for name in DOC_MAPPING:
            text += f"\n\n=== DOCUMENT: {name} ===\n{assembled[name]}\n"
        for name in SHEET_MAPPING:
            text += f"\n\n=== SPREADSHEET: {name} ===\n{assembled[name]}\n"
        with open(args.out, "w") as f:
            f.write(text)
        print(f"  wrote {args.out} ({len(text):,} chars) → regen --kb-snapshot {args.out}")
    elif args.write:
        print("  (not writing: need all 4 docs to read for a prod-faithful snapshot)")


if __name__ == "__main__":
    main()
