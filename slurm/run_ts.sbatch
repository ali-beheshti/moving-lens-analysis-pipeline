#!/bin/bash
#SBATCH --job-name=ml_filter
#SBATCH --output=logs/ml_filter_%j.out
#SBATCH --error=logs/ml_filter_%j.err
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=08:00:00

set -euo pipefail

: "${MAP_PATH:?Set MAP_PATH to the input FITS map}"
: "${MASK_MAP:?Set MASK_MAP to the mask FITS file}"
: "${MAP_NAME:?Set MAP_NAME to a short map tag}"
: "${CATALOG_NAME:?Set CATALOG_NAME to the catalog name}"
: "${THUMBSTACK_ROOT:?Set THUMBSTACK_ROOT to a compatible local checkout}"

FILTER_TYPES="${FILTER_TYPES:-matchedboth}"
ENV_NAME="${ENV_NAME:-movinglens_mpv}"
NOBJ="${NOBJ:-}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
mkdir -p "${REPO_ROOT}/logs" "${REPO_ROOT}/outputs"

if command -v conda >/dev/null 2>&1; then
  eval "$(conda shell.bash hook)"
  conda activate "${ENV_NAME}"
fi

CMD=(python "${REPO_ROOT}/pipelines/ts_pipeline.py"
  --thumbstack-root "${THUMBSTACK_ROOT}"
  --map "${MAP_PATH}"
  --mask-map "${MASK_MAP}"
  --map-name "${MAP_NAME}"
  --catalog-name "${CATALOG_NAME}"
  --filter-types "${FILTER_TYPES}"
  --output-dir "${REPO_ROOT}/outputs")

if [[ -n "${NOBJ}" ]]; then CMD+=(--nobj "${NOBJ}"); fi
"${CMD[@]}"
