# Research ThumbStack changes represented in this portfolio

The research checkout used for the moving-lens analysis diverged from the
upstream ThumbStack code in several analysis-specific ways.  This public repo
represents those changes without copying the entire upstream package.

## Moving-lens filter family

The research implementation added directional filters for the two local
transverse components:

- `phimatched`
- `thetamatched`
- `phimatchedrot90`
- `thetamatchedrot90`
- `phimatchedNullGrad`
- `thetamatchedNullGrad`
- `phimatchedrot90NullGrad`
- `thetamatchedrot90NullGrad`

`extensions/moving_lens_filters.py` provides a cleaned standalone implementation
of the same filter concepts.  The radial profile is injected as a callable so
survey/research calibration products do not need to be committed.

## Moving-lens map/template generation

The private research tree also contained moving-lens map-painting code based on
halo transverse velocities and radial deflection profiles.  The original file
mixed exploratory versions and other sky components.  The public
`extensions/moving_lens_template.py` isolates the reusable moving-lens dipole
calculation in a compact form.

## Pipeline integration

`pipelines/ts_pipeline.py` captures the production orchestration layer used to:

1. load a compatible modified ThumbStack checkout;
2. run directional matched filters on a map/catalog pair;
3. preserve selection/outlier masks; and
4. save per-object transverse filter outputs for the MPV stage.

Legacy cluster paths, calibration pickle files, collaboration-only data, and
unrelated upstream scripts are intentionally excluded.

## Why the full ThumbStack tree is not vendored

The public upstream repository contains a large body of pre-existing stacking
software.  For a portfolio release, vendoring all of it would obscure which
parts are specific to this project and would copy a large amount of code that is
not needed to demonstrate the contribution.  The upstream project is therefore
linked and attributed, while this repository exposes the moving-lens-specific
software and integration layer directly.
