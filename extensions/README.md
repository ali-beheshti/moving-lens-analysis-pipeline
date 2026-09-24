# Moving-Lens Filter Extensions

This directory contains the moving-lens filtering and template modules used by the analysis pipeline.

## Directional filters

`moving_lens_filters.py` implements the transverse filter family used to measure the two local moving-lens components:

- `phimatched`
- `thetamatched`
- `phimatchedrot90`
- `thetamatchedrot90`
- `phimatchedNullGrad`
- `thetamatchedNullGrad`
- `phimatchedrot90NullGrad`
- `thetamatchedrot90NullGrad`

The filters support radial matched-filter profiles, 90° rotations for null tests, and gradient-nulled variants for suppressing large-scale gradient contamination.

## Moving-lens template

`moving_lens_template.py` constructs the temperature dipole produced by transverse motion for a supplied radial deflection profile and transverse velocity components.

## Pipeline integration

The filtering stage is orchestrated by `pipelines/ts_pipeline.py`, which connects these moving-lens components to the ThumbStack map/catalog workflow. Filter outputs are then passed to `pipelines/mpv_pipeline.py` for the pairwise-velocity analysis.

See `docs/moving_lens_extensions.md` for additional implementation notes.
