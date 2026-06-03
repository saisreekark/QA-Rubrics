#!/usr/bin/env bash
# Push notebook/content.ipynb back to the Dataform repo that the
# rubrics-automation-run scheduler executes. This writes to the LIVE pipeline.
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

CONTENTS_B64=$(base64 -w0 < "$SRC")
TOKEN="$(gcloud auth print-access-token)"

curl -sf -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  --data "{\"path\":\"content.ipynb\",\"contents\":\"$CONTENTS_B64\"}" \
  "https://dataform.googleapis.com/v1beta1/${REPO}:writeFile" \
  | python3 -m json.tool

echo "Push complete."
