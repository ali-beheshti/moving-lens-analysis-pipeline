# Moving-Lens Analysis Pipeline

A portfolio-oriented release of a research pipeline for extracting weak
transverse signals from sky maps and estimating the **mean pairwise velocity
(MPV)** of a large object catalog.

The project highlights transferable technical work in **Python pipeline design,
statistical estimation, matched filtering, null tests, covariance estimation,
spatial indexing, large-catalog processing, and HPC/Slurm workflows**.

> **Public portfolio release.** Survey data, collaboration-only products,
> calibration pickles, cluster paths, and the full legacy ThumbStack checkout
> are intentionally excluded. Moving-lens-specific ThumbStack extensions are
> represented directly in `extensions/`, and the MPV stage includes a synthetic
> end-to-end demo.

## What I added for the moving-lens analysis

The research workflow extended the public
[ThumbStack](https://github.com/EmmanuelSchaan/ThumbStack) stacking framework for
moving-lens measurements. The portfolio release exposes the project-specific
parts without vendoring the entire upstream codebase:

- **phi/theta directional matched filters** for the two transverse components;
- **90°-rotated null filters** for systematics checks;
- **gradient-nulled matched-filter variants**;
- **transverse-velocity moving-lens dipole templates**;
- compatibility/orchestration code for running the research filter stage; and
- a separate **chunked MPV estimator** with deterministic shuffle tests and
  covariance construction.

See `extensions/README.md` and `docs/research_thumbstack_changes.md` for details.

## Pipeline overview

```text
sky map + mask + object catalog
          |
          v
 moving-lens filter stage
 (ThumbStack integration + directional extensions)
          |
          +--> theta/phi matched-filter outputs
          +--> rotated / gradient-null diagnostics
          +--> object-selection masks
          |
          v
 catalog filtering + coordinate conversion
          |
          v
 chunked pairwise estimator
 (SciPy cKDTree neighbor queries)
          |
          +--> true MPV chunks
          +--> deterministic shuffled/null chunks
          |
          v
 exact numerator/denominator aggregation
          |
          +--> final MPV curve
          +--> null ensemble / covariance / errors / correlation matrix
```

## Engineering features

- **Chunked computation:** pairwise work is split over catalog index ranges for
  Slurm array jobs.
- **Exact aggregation:** chunks save estimator numerators and denominators; the
  final estimator is `sum(num) / sum(den)` rather than an average of chunk ratios.
- **Memory-aware I/O:** large arrays can be memory-mapped before catalog selection.
- **Spatial indexing:** `scipy.spatial.cKDTree` limits pair calculations to nearby
  objects within the largest separation bin.
- **Reproducible null tests:** shuffle realizations use deterministic seeds.
- **Covariance workflow:** shuffled realizations are combined into a null mean,
  covariance matrix, standard errors, and correlation matrix.
- **Portable public path:** the MPV stage accepts a simple `.npz` catalog and the
  included synthetic demo does not require private data.

## Repository layout

```text
extensions/
  moving_lens_filters.py    # phi/theta matched, rotated-null, gradient-null filters
  moving_lens_template.py   # transverse-velocity dipole template

pipelines/
  ts_pipeline.py            # production ThumbStack orchestration wrapper
  mpv_pipeline.py           # chunked MPV estimator + shuffle/covariance combine

examples/
  generate_synthetic_inputs.py
  demo_moving_lens_extensions.py
  run_demo.sh

slurm/
  run_ts.sbatch
  run_mpv_true.sbatch
  run_mpv_shuffles.sbatch
  combine_mpv.sbatch

configs/
  example.env

docs/
  research_thumbstack_changes.md
  slurm_usage.md
  public_release_notes.md

third_party/
  README.md                 # upstream ThumbStack attribution
```

## Quick start: synthetic MPV demo

Create the environment:

```bash
conda env create -f environment.yml
conda activate movinglens_mpv
```

Run the self-contained MPV smoke test:

```bash
bash examples/run_demo.sh
```

The demo generates a small synthetic catalog and mock transverse-filter outputs,
runs one true estimator realization, runs deterministic shuffled realizations,
and builds a sample covariance matrix. Generated files are written under
`outputs/` and ignored by Git.

You can also exercise the standalone moving-lens filter/template extensions:

```bash
python examples/demo_moving_lens_extensions.py
```

These examples test the software path only; they do not reproduce collaboration
measurements or published science results.

Run the lightweight extension tests with:

```bash
python -m unittest discover -s tests
```

## Standalone MPV usage

The portable public workflow expects:

1. `thetamatched.npy` and `phimatched.npy` (or alternate filter names),
2. `thumbstack_masks.npz` containing post-selection masks, and
3. a catalog `.npz` containing either `ra_deg`, `dec_deg`, `redshift` or
   `RA`, `DEC`, `Z`.

Example:

```bash
python pipelines/mpv_pipeline.py chunk \
  --ts-dir outputs/ts__map_example__cat_example \
  --catalog-npz /path/to/catalog.npz \
  --chunk-id 0 \
  --chunk-size 100000
```

Combine completed chunks:

```bash
python pipelines/mpv_pipeline.py combine \
  --outdir outputs/mpv__map_example__cat_example
```

A shuffled/null realization uses the same estimator with a deterministic
velocity permutation:

```bash
python pipelines/mpv_pipeline.py chunk \
  --shuffle --shuffle-id 0 --seed-offset 12345 \
  --ts-dir outputs/ts__map_example__cat_example \
  --catalog-npz /path/to/catalog.npz \
  --chunk-id 0 --chunk-size 100000
```

After multiple shuffled realizations:

```bash
python pipelines/mpv_pipeline.py combine --shuffle \
  --outdir outputs/mpv__map_example__cat_example
```

## Research-data filter stage

`pipelines/ts_pipeline.py` is the orchestration layer used with the modified
research ThumbStack checkout. The full upstream/legacy source tree is not
redistributed here; `extensions/` makes the moving-lens-specific filter logic
inspectable in standalone form.

For a local research checkout:

```bash
export THUMBSTACK_ROOT=/path/to/compatible/thumbstack_checkout

python pipelines/ts_pipeline.py \
  --map /path/to/cmb_temperature_map.fits \
  --mask-map /path/to/analysis_mask.fits \
  --map-name example_map \
  --catalog-name example_catalog
```

## HPC / Slurm

The `slurm/` directory contains portable templates for the filter stage, true MPV
chunks, shuffled/null chunks, and aggregation. Cluster-specific partition,
account, username, and filesystem settings are intentionally omitted.

## Attribution and data note

This project builds on the public **ThumbStack** stacking framework by Emmanuel
Schaan and collaborators. See `third_party/README.md` for the upstream link and
citation note. This repository does **not** claim authorship of the upstream
ThumbStack codebase and does not vendor it wholesale.

Real survey maps, catalogs, collaboration products, and research calibration
files are not included. They must be obtained through their appropriate public
releases or collaboration channels.
