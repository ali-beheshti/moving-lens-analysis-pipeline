#!/bin/bash
#SBATCH --job-name=mpv_combine
#SBATCH --output=logs/mpv_combine_%j.out
#SBATCH --error=logs/mpv_combine_%j.err
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=00:30:00

set -euo pipefail

MODE="${MODE:-true}"
MAP_NAME="${MAP_NAME:-example_map}"
CATALOG_NAME="${CATALOG_NAME:-example_catalog}"
ENV_NAME="${ENV_NAME:-movinglens_mpv}"
REQUIRE_NCHUNKS="${REQUIRE_NCHUNKS:-}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
OUTDIR="${OUTDIR:-${REPO_ROOT}/outputs/mpv__map_${MAP_NAME}__cat_${CATALOG_NAME}}"
mkdir -p "${REPO_ROOT}/logs"

if command -v conda >/dev/null 2>&1; then
  eval "$(conda shell.bash hook)"
  conda activate "${ENV_NAME}"
fi

if [[ "${MODE}" == "true" ]]; then
  python "${REPO_ROOT}/pipelines/mpv_pipeline.py" combine --outdir "${OUTDIR}"
elif [[ "${MODE}" == "shuffle" || "${MODE}" == "shuffles" ]]; then
  CMD=(python "${REPO_ROOT}/pipelines/mpv_pipeline.py" combine --shuffle --outdir "${OUTDIR}")
  if [[ -n "${REQUIRE_NCHUNKS}" ]]; then CMD+=(--require-nchunks "${REQUIRE_NCHUNKS}"); fi
  "${CMD[@]}"
else
  echo "MODE must be true or shuffle" >&2
  exit 2
fi
