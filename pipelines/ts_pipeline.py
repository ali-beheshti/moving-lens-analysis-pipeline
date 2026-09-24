#!/usr/bin/env python3
"""Matched-filter orchestration wrapper for the moving-lens workflow.

The portfolio repository intentionally does not bundle the research ThumbStack
checkout. Point this script to a compatible local checkout with
``--thumbstack-root`` or the ``THUMBSTACK_ROOT`` environment variable.
"""

from __future__ import annotations

import argparse
import inspect
import logging
import os
import re
import sys
import time
import traceback
from pathlib import Path
from typing import Optional, Tuple

import matplotlib
import numpy as np

matplotlib.use("Agg")

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "outputs"


def install_numpy_alias_shim() -> None:
    """Restore NumPy aliases expected by some older scientific code."""
    aliases = {
        "float": float,
        "int": int,
        "bool": bool,
        "complex": complex,
        "object": object,
    }
    for name, alias in aliases.items():
        if not hasattr(np, name):
            setattr(np, name, alias)


def install_enmap_at_shim() -> None:
    """Ignore legacy keyword arguments that newer pixell ``ndmap.at`` rejects."""
    from pixell import enmap as enmap_module

    original_at = enmap_module.ndmap.at
    allowed_kwargs = set(inspect.signature(original_at).parameters)

    def at_compat(self, coords, *args, **kwargs):
        clean_kwargs = {key: val for key, val in kwargs.items() if key in allowed_kwargs}
        return original_at(self, coords, *args, **clean_kwargs)

    enmap_module.ndmap.at = at_compat


def load_thumbstack_modules(thumbstack_root: str):
    """Load the external research dependency only when the filter stage runs."""
    if not thumbstack_root:
        raise ValueError(
            "No ThumbStack checkout configured. Supply --thumbstack-root or set "
            "THUMBSTACK_ROOT. See third_party/README.md."
        )

    root = Path(thumbstack_root).expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"ThumbStack directory not found: {root}")

    install_numpy_alias_shim()
    install_enmap_at_shim()

    os.chdir(root)
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from pixell import enmap  # type: ignore
    from catalog import Catalog  # type: ignore
    from thumbstack import ThumbStack  # type: ignore
    from driver_catalogs import massConversion, u  # type: ignore

    return enmap, Catalog, ThumbStack, massConversion, u


def build_logger(log_file: Optional[str]) -> logging.Logger:
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if log_file:
        path = Path(log_file).expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(path))

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=handlers,
    )
    return logging.getLogger("ts_pipeline")


def get_nproc() -> int:
    nproc_env = os.environ.get("SLURM_CPUS_PER_TASK") or os.environ.get("SLURM_CPUS_ON_NODE")
    return max(1, int(nproc_env)) if nproc_env else 1


def require_file(path: str, label: str) -> None:
    if not Path(path).is_file():
        raise FileNotFoundError(f"{label} not found: {path}")


def clean_path_tag(value: str) -> str:
    tag = re.sub(r"[^A-Za-z0-9._+-]+", "_", str(value).strip()).strip("_")
    return tag or "untagged"


def build_output_dir(parent_dir: str, map_name: str, catalog_name: str) -> str:
    folder = f"ts__map_{clean_path_tag(map_name)}__cat_{clean_path_tag(catalog_name)}"
    return str(Path(parent_dir) / folder)


def compute_ps_keep(ts, filter_type: str) -> np.ndarray:
    filt_mask = ts.filtMask[filter_type]
    if filt_mask.ndim == 1:
        filt_mask = filt_mask[:, None]
    return np.abs(filt_mask[:, -1]) < 1


def compute_outlier_masks(
    ts,
    filter_type: str,
    mvir: Optional[Tuple[float, float]] = None,
    z: Tuple[float, float] = (0.0, 100.0),
    extra_selection: float = 1.0,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    if mvir is None:
        mvir = (ts.Catalog.Mvir.min(), ts.Catalog.Mvir.max())

    pre_mask = ts.catalogMask(
        overlap=True,
        psMask=True,
        filterType=filter_type,
        mVir=mvir,
        z=z,
        extraSelection=extra_selection,
        outlierReject=False,
    )
    post_mask = ts.catalogMask(
        overlap=True,
        psMask=True,
        filterType=filter_type,
        mVir=mvir,
        z=z,
        extraSelection=extra_selection,
        outlierReject=True,
    )
    return pre_mask, post_mask, pre_mask & ~post_mask


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a compatible ThumbStack matched-filter stage and save compact outputs."
    )
    parser.add_argument(
        "--thumbstack-root",
        default=os.environ.get("THUMBSTACK_ROOT", ""),
        help="Path to a compatible external ThumbStack checkout (or set THUMBSTACK_ROOT).",
    )
    parser.add_argument("--map", dest="input_map", required=True, help="Input map FITS file.")
    parser.add_argument("--mask-map", required=True, help="Input mask FITS file.")
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help=f"Parent output directory. Default: {DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument("--catalog-name", required=True, help="Catalog name understood by the local ThumbStack checkout.")
    parser.add_argument("--map-name", required=True, help="Short map tag used in output folder names.")
    parser.add_argument(
        "--filter-types",
        default="matchedboth",
        help="ThumbStack filterTypes value used by the research workflow.",
    )
    parser.add_argument("--nobj", type=int, default=None, help="Optional object limit for debugging.")
    parser.add_argument("--log-file", default=None, help="Optional log file.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.input_map = str(Path(args.input_map).expanduser().resolve())
    args.mask_map = str(Path(args.mask_map).expanduser().resolve())
    args.output_dir = str(Path(args.output_dir).expanduser().resolve())

    log = build_logger(args.log_file)
    start_time = time.time()

    require_file(args.input_map, "Input map")
    require_file(args.mask_map, "Mask map")
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)

    enmap, Catalog, ThumbStack, massConversion, u = load_thumbstack_modules(args.thumbstack_root)
    nproc = get_nproc()

    log.info("Reading map and mask")
    map_enmap = enmap.read_fits(args.input_map)
    mask_enmap = enmap.read_fits(args.mask_map)

    catalog = Catalog(
        u,
        massConversion,
        name=args.catalog_name,
        nameLong=args.catalog_name,
        save=False,
        nObj=args.nobj,
    )
    log.info("Loaded catalog %s with nObj=%d", catalog.name, catalog.nObj)

    output_dir = build_output_dir(args.output_dir, args.map_name, catalog.name)
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    ts = ThumbStack(
        u,
        catalog,
        map_enmap,
        mask_enmap,
        None,
        name=f"{args.map_name} {catalog.name}",
        nameLong=None,
        save=True,
        filterTypes=args.filter_types,
        nProc=nproc,
    )

    filter_map_names = sorted(ts.filtMap.keys())
    if not filter_map_names:
        raise RuntimeError(f"No filter outputs produced for filterTypes={args.filter_types!r}")

    mask_overlap = ts.overlapFlag.astype(bool)
    saved_filter_paths: dict[str, str] = {}
    mask_outputs: dict[str, np.ndarray] = {
        "mask_overlap": mask_overlap,
        "idx_overlap_keep": np.where(mask_overlap)[0],
    }

    for filter_name in filter_map_names:
        safe_name = clean_path_tag(filter_name)
        output_path = str(Path(output_dir) / f"{safe_name}.npy")
        np.save(output_path, ts.filtMap[filter_name])
        saved_filter_paths[filter_name] = output_path

        if filter_name in ts.filtMask:
            ps_keep = compute_ps_keep(ts, filter_name)
            pre_mask, post_mask, outliers = compute_outlier_masks(ts, filter_name)
            mask_outputs[f"mask_ps_keep_{safe_name}"] = ps_keep
            mask_outputs[f"mask_pre_outlier_{safe_name}"] = pre_mask
            mask_outputs[f"mask_post_outlier_{safe_name}"] = post_mask
            mask_outputs[f"mask_outliers_{safe_name}"] = outliers
            mask_outputs[f"idx_ps_fail_{safe_name}"] = np.where(mask_overlap & ~ps_keep)[0]
            mask_outputs[f"idx_outliers_{safe_name}"] = np.where(outliers)[0]

    mask_path = Path(output_dir) / "thumbstack_masks.npz"
    meta_path = Path(output_dir) / "metadata.npz"
    np.savez(mask_path, **mask_outputs)
    np.savez(
        meta_path,
        catalog_name=catalog.name,
        map_name=args.map_name,
        filter_types=args.filter_types,
        filter_map_names=np.array(filter_map_names, dtype=object),
        nproc=nproc,
        nobj=args.nobj if args.nobj is not None else -1,
    )

    log.info("Saved %d filter outputs to %s", len(filter_map_names), output_dir)
    log.info("Finished in %.2f seconds", time.time() - start_time)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        traceback.print_exc()
        print(f"ERROR: {exc!r}", file=sys.stderr)
        sys.exit(1)
