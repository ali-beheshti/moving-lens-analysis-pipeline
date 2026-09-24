# Upstream dependency and attribution

The moving-lens filter stage was developed by extending the public **ThumbStack**
stacking framework:

- Upstream repository: https://github.com/EmmanuelSchaan/ThumbStack
- Upstream README requests citation of the associated ThumbStack paper when used
  in scientific work.

This portfolio repository intentionally does **not** vendor the complete upstream
ThumbStack source tree. Instead:

- `extensions/` contains standalone, cleaned implementations of the
  moving-lens-specific filter/template functionality developed for this project;
- `pipelines/ts_pipeline.py` demonstrates the integration/orchestration layer;
- the production research checkout remains an external dependency for reproducing
  the original map-filtering run exactly.

No license is asserted here over the upstream ThumbStack code. The standalone
portfolio files in this repository should not be interpreted as relicensing the
upstream project.
