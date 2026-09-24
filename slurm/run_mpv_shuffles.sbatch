#!/bin/bash
#SBATCH --job-name=mpv_shuffle
#SBATCH --output=logs/mpv_shuffle_%A_%a.out
#SBATCH --error=logs/mpv_shuffle_%A_%a.err
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=32G
#SBATCH --time=08:00:00
#SBATCH --array=0-49999%25

set -euo pipefail

MAP_NAME="${MAP_NAME:-example_map}"
CATALOG_NAME="${CATALOG_NAME:-example_catalog}"
CHUNK_SIZE="${CHUNK_SIZE:-100000}"
N_CHUNKS_MAX="${N_CHUNKS_MAX:-100}"
N_SHUFFLES="${N_SHUFFLES:-500}"
SEED_OFFSET="${SEED_OFFSET:-12345}"
MASK_MODE="${MASK_MODE:-intersection}"
FILTER_THETA="${FILTER_THETA:-thetamatched}"
FILTER_PHI="${FILTER_PHI:-phimatched}"
VTH_SCALE="${VTH_SCALE:-1.0}"
VPH_SCALE="${VPH_SCALE:-1.0}"
ENV_NAME="${ENV_NAME:-movinglens_mpv}"
CATALOG_NPZ="${CATALOG_NPZ:-}"
THUMBSTACK_ROOT="${THUMBSTACK_ROOT:-}"

TASK_ID="${SLURM_ARRAY_TASK_ID}"
SHUFFLE_ID=$(( TASK_ID / N_CHUNKS_MAX ))
CHUNK_ID=$(( TASK_ID % N_CHUNKS_MAX ))
if [[ "${SHUFFLE_ID}" -ge "${N_SHUFFLES}" ]]; then exit 0; fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TS_DIR="${TS_DIR:-${REPO_ROOT}/outputs/ts__map_${MAP_NAME}__cat_${CATALOG_NAME}}"
mkdir -p "${REPO_ROOT}/logs"

if command -v conda >/dev/null 2>&1; then
  eval "$(conda shell.bash hook)"
  conda activate "${ENV_NAME}"
fi

CMD=(python "${REPO_ROOT}/pipelines/mpv_pipeline.py" chunk
  --shuffle --shuffle-id "${SHUFFLE_ID}" --seed-offset "${SEED_OFFSET}"
  --ts-dir "${TS_DIR}"
  --chunk-id "${CHUNK_ID}" --chunk-size "${CHUNK_SIZE}"
  --mask-mode "${MASK_MODE}"
  --theta-filter-name "${FILTER_THETA}" --phi-filter-name "${FILTER_PHI}"
  --vth-scale "${VTH_SCALE}" --vph-scale "${VPH_SCALE}"
  --catalog-name "${CATALOG_NAME}")

if [[ -n "${CATALOG_NPZ}" ]]; then
  CMD+=(--catalog-npz "${CATALOG_NPZ}")
elif [[ -n "${THUMBSTACK_ROOT}" ]]; then
  CMD+=(--thumbstack-dir "${THUMBSTACK_ROOT}")
fi

"${CMD[@]}"
