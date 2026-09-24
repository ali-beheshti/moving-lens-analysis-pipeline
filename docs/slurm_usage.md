# Slurm Usage

The batch files in `slurm/` provide templates for running the filtering and MPV stages on an HPC cluster.

## Environment

Create the environment once:

```bash
conda env create -f environment.yml
```

The scripts activate `movinglens_mpv` by default. Override the environment name with:

```bash
export ENV_NAME=my_environment
```

## Filter stage

Configure the map, mask, catalog, and ThumbStack path:

```bash
source configs/example.env
sbatch slurm/run_ts.sbatch
```

Required environment variables are `MAP_PATH`, `MASK_MAP`, `MAP_NAME`, `CATALOG_NAME`, and `THUMBSTACK_ROOT`.

## True MPV chunks

```bash
export MAP_NAME=example_map
export CATALOG_NAME=example_catalog
export CATALOG_NPZ=/path/to/catalog.npz
export TS_DIR=/path/to/ts__map_example__cat_example
sbatch slurm/run_mpv_true.sbatch
```

The array range may be larger than the number of required chunks. Tasks beyond the surviving catalog size exit without writing output.

## Shuffled/null realizations

`run_mpv_shuffles.sbatch` maps each Slurm array index to a shuffle realization and catalog chunk:

```text
shuffle_id = task_id // N_CHUNKS_MAX
chunk_id   = task_id %  N_CHUNKS_MAX
```

Configure `N_SHUFFLES` and `N_CHUNKS_MAX` before submission.

## Combine

True estimator:

```bash
MODE=true OUTDIR=/path/to/mpv_output sbatch slurm/combine_mpv.sbatch
```

Shuffle covariance:

```bash
MODE=shuffle OUTDIR=/path/to/mpv_output sbatch slurm/combine_mpv.sbatch
```
