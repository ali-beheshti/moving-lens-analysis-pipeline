#!/bin/bash
#SBATCH --job-name=synthetic-pairs
#SBATCH --array=0-7
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:20:00
#SBATCH --output=logs/synthetic-%A_%a.out

# Submit from the repository root after creating logs/.
# Generate demo_output/catalog.npz first; edit resources to fit your cluster.
set -euo pipefail
mkdir -p demo_output/chunks
python -m portfolio.chunk \
  --catalog demo_output/catalog.npz \
  --output "demo_output/chunks/chunk_$(printf '%04d' "$SLURM_ARRAY_TASK_ID").npz" \
  --chunk-index "$SLURM_ARRAY_TASK_ID" --chunks 8 --trials 20
