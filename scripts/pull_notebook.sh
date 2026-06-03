#!/usr/bin/env bash
# Pull the live Rubrics notebook from the Dataform repo backing
# the rubrics-automation-run scheduler into notebook/content.ipynb.
set -euo pipefail

REPO="projects/gtm-cloud-helpdesk/locations/us-central1/repositories/1b4ad4ee-53ba-4541-9492-1dc89d100607"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$HERE/notebook/content.ipynb"

mkdir -p "$HERE/notebook"

TOKEN="$(gcloud auth print-access-token)"
curl -sf -H "Authorization: Bearer $TOKEN" \
  "https://dataform.googleapis.com/v1beta1/${REPO}:readFile?path=content.ipynb" \
| python3 -c "import json,sys,base64; sys.stdout.write(base64.b64decode(json.load(sys.stdin)['contents']).decode())" \
> "$OUT"

CELLS=$(python3 -c "import json; print(len(json.load(open('$OUT'))['cells']))")
echo "Pulled $(wc -c < "$OUT") bytes ($CELLS cells) to $OUT"
