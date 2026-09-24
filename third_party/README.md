# ThumbStack Dependency

The map-filtering stage uses the [ThumbStack](https://github.com/EmmanuelSchaan/ThumbStack) stacking framework by Emmanuel Schaan and collaborators.

`pipelines/ts_pipeline.py` loads ThumbStack from the path specified by `THUMBSTACK_ROOT` and uses it for cutout construction and filter orchestration. The moving-lens-specific directional filters and transverse-velocity template utilities are implemented under `extensions/`.

For scientific use of ThumbStack, follow the citation guidance in the upstream repository.
