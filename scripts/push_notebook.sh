#!/usr/bin/env bash
# Push notebook/content.ipynb back to the Dataform repo that the
# rubrics-automation-run scheduler executes. This writes to the LIVE pipeline.
#
# ⚠️ KNOWN-BROKEN for this repo (verified 2026-06-07): the scheduler's repo is a
# Dataform *single-file-asset notebook* (Colab Enterprise) — it exposes NO public
# write API. `:readFile`/`:fetchHistory` work, but `:writeFile` and
# `:commitRepositoryChanges` 404 on both v1 and v1beta1. Saves go through the
# Pantheon Colab Enterprise UI (prior commits are "Saved" by the notebook authors).
# Until an internal save RPC is found, DEPLOY by opening the notebook in Colab
# Enterprise and saving the local notebook/content.ipynb. See docs/stage-tracker.md.
set -euo pipefail

REPO="projects/gtm-cloud-helpdesk/locations/us-central1/repositories/1b4ad4ee-53ba-4541-9492-1dc89d100607"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$HERE/notebook/content.ipynb"

[ -f "$SRC" ] || { echo "Missing $SRC"; exit 1; }

echo "About to push $SRC to live Dataform repo:"
echo "  $REPO/content.ipynb"
echo "Daily scheduler 'rubrics-automation-run' will pick this up at 12:00 IST."
read -r -p "Continue? [y/N] " ans
[ "$ans" = "y" ] || { echo "Aborted."; exit 1; }

TOKEN="$(gcloud auth print-access-token)"

# Build the JSON payload in a temp file — the base64 notebook is far larger than
# ARG_MAX, so it must be streamed via --data @file, not passed on the cmdline.
PAYLOAD="$(mktemp)"
trap 'rm -f "$PAYLOAD"' EXIT
python3 - "$SRC" "$PAYLOAD" <<'PY'
import base64, json, sys
src, out = sys.argv[1], sys.argv[2]
data = base64.b64encode(open(src, "rb").read()).decode()
json.dump({"path": "content.ipynb", "contents": data}, open(out, "w"))
PY

curl -sf -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  --data @"$PAYLOAD" \
  "https://dataform.googleapis.com/v1beta1/${REPO}:writeFile" \
  | python3 -m json.tool

echo "Push complete."
