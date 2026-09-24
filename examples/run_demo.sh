#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
OUT_ROOT="${REPO_ROOT}/outputs"
TS_DIR="${OUT_ROOT}/ts__map_synthetic__cat_synthetic"
CATALOG_NPZ="${OUT_ROOT}/synthetic_catalog.npz"
MPV_DIR="${OUT_ROOT}/mpv__map_synthetic__cat_synthetic"

python "${SCRIPT_DIR}/generate_synthetic_inputs.py" --output-root "${OUT_ROOT}" --nobj 300

python "${REPO_ROOT}/pipelines/mpv_pipeline.py" chunk \
  --ts-dir "${TS_DIR}" --catalog-npz "${CATALOG_NPZ}" \
  --chunk-id 0 --chunk-size 1000 --vth-scale 1 --vph-scale 1 \
  --bin-start 20 --bin-stop 220 --bin-step 20

python "${REPO_ROOT}/pipelines/mpv_pipeline.py" combine \
  --outdir "${MPV_DIR}" --bin-start 20 --bin-stop 220 --bin-step 20

for SID in 0 1 2 3; do
  python "${REPO_ROOT}/pipelines/mpv_pipeline.py" chunk \
    --shuffle --shuffle-id "${SID}" --seed-offset 12345 \
    --ts-dir "${TS_DIR}" --catalog-npz "${CATALOG_NPZ}" \
    --chunk-id 0 --chunk-size 1000 --vth-scale 1 --vph-scale 1 \
    --bin-start 20 --bin-stop 220 --bin-step 20
done

python "${REPO_ROOT}/pipelines/mpv_pipeline.py" combine --shuffle \
  --outdir "${MPV_DIR}" --bin-start 20 --bin-stop 220 --bin-step 20

echo "Demo complete. Results are under: ${MPV_DIR}/combined"
