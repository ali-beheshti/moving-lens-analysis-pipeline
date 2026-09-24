# Moving-lens ThumbStack extensions

The private research workflow used a modified checkout of
[ThumbStack](https://github.com/EmmanuelSchaan/ThumbStack) to extract transverse
moving-lens observables from sky maps.

This public portfolio repository **does not redistribute the full upstream
ThumbStack source tree**. Instead, this directory contains compact standalone
implementations of the moving-lens-specific ideas added for the project:

- phi/theta directional dipole filters;
- radial matched-filter templates;
- 90-degree rotated null filters;
- gradient-nulled matched-filter variants; and
- transverse-velocity moving-lens temperature templates.

The production research version integrated these features into the ThumbStack
cutout/filtering workflow and added compatibility/orchestration code for modern
NumPy/pixell environments. The public implementations here are intended to make
those contributions inspectable without bundling unrelated legacy code,
collaboration data, or research calibration products.

For the original stacking framework and citation information, see the upstream
ThumbStack repository.
