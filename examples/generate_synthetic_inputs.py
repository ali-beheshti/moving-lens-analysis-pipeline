#!/usr/bin/env python3
"""Generate a tiny, non-scientific dataset for exercising the public MPV pipeline."""

from __future__ import annotations

import argparse
from pathlib import Path
import numpy as np


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", default="outputs")
    parser.add_argument("--nobj", type=int, default=300)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)
    root = Path(args.output_root).resolve()
    ts_dir = root / "ts__map_synthetic__cat_synthetic"
    ts_dir.mkdir(parents=True, exist_ok=True)

    # Small sky patch and redshift interval -> many pairs within the demo bins.
    ra_deg = rng.uniform(145.0, 155.0, args.nobj)
    dec_deg = rng.uniform(-2.5, 2.5, args.nobj)
    redshift = rng.uniform(0.28, 0.34, args.nobj)

    # Smooth signal + noise. These are illustrative filter outputs, not physical data.
    theta = 0.8 * np.sin(np.deg2rad(ra_deg * 3.0)) + rng.normal(0.0, 0.35, args.nobj)
    phi = 0.8 * np.cos(np.deg2rad(dec_deg * 8.0)) + rng.normal(0.0, 0.35, args.nobj)

    keep_theta = rng.random(args.nobj) > 0.04
    keep_phi = rng.random(args.nobj) > 0.04
    overlap = rng.random(args.nobj) > 0.02
    keep_theta &= overlap
    keep_phi &= overlap

    np.save(ts_dir / "thetamatched.npy", theta)
    np.save(ts_dir / "phimatched.npy", phi)
    np.savez(
        ts_dir / "thumbstack_masks.npz",
        mask_overlap=overlap,
        mask_post_outlier_thetamatched=keep_theta,
        mask_post_outlier_phimatched=keep_phi,
    )
    np.savez(ts_dir / "metadata.npz", catalog_name="synthetic", map_name="synthetic")

    catalog_path = root / "synthetic_catalog.npz"
    np.savez(catalog_path, ra_deg=ra_deg, dec_deg=dec_deg, redshift=redshift)

    print(f"TS_DIR={ts_dir}")
    print(f"CATALOG_NPZ={catalog_path}")


if __name__ == "__main__":
    main()
