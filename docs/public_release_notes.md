# Public portfolio release notes

This repository is a curated public version of a larger research workspace.
The goal is to expose the technical contribution while avoiding accidental
publication of collaboration-only data, calibration products, cluster-specific
configuration, or unrelated upstream code.

## Included

- chunked mean-pairwise-velocity estimator;
- deterministic shuffle/null-test workflow;
- covariance and correlation-matrix aggregation;
- portable `.npz` catalog input;
- Slurm templates with cluster-specific settings removed;
- standalone moving-lens directional matched-filter extensions;
- rotated and gradient-null filter variants;
- standalone transverse-velocity moving-lens template utilities;
- production filter-stage orchestration wrapper; and
- synthetic examples/tests that require no collaboration data.

## Intentionally excluded

- survey maps and real object catalogs;
- generated `.npy`, `.npz`, `.pkl`, FITS, plots, and logs;
- research calibration/interpolation pickle files;
- usernames, scratch paths, environment-specific filesystem paths, and Slurm
  accounts/partitions;
- the full legacy ThumbStack source checkout; and
- unrelated exploratory scripts from the research workspace.

## ThumbStack attribution strategy

The research analysis was developed by extending the public ThumbStack framework.
Rather than copying the full upstream tree into this portfolio repo, the
moving-lens-specific functionality is exposed in `extensions/` and described in
`docs/research_thumbstack_changes.md`. The upstream project is linked and
attributed under `third_party/`.

This makes the project-specific work directly visible while keeping the boundary
between upstream software and portfolio code clear.
