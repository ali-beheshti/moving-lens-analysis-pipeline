#!/usr/bin/env python3
"""Small smoke test for the standalone moving-lens extensions."""

from __future__ import annotations

from pathlib import Path
import sys

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from extensions.moving_lens_filters import apply_filter, build_filter_bank
from extensions.moving_lens_template import moving_lens_dipole_template


def gaussian_profile(radius: np.ndarray, sigma: float = np.deg2rad(1.5 / 60.0)) -> np.ndarray:
    return np.exp(-0.5 * (radius / sigma) ** 2)


def gradient_null_profile(radius: np.ndarray) -> np.ndarray:
    # Example compensated profile for a software demo only.
    sigma = np.deg2rad(1.5 / 60.0)
    core = np.exp(-0.5 * (radius / sigma) ** 2)
    broad = np.exp(-0.5 * (radius / (2.2 * sigma)) ** 2)
    return core - 0.45 * broad


def main() -> None:
    extent = np.deg2rad(8.0 / 60.0)
    axis = np.linspace(-extent, extent, 129)
    ra, dec = np.meshgrid(axis, axis)

    filters = build_filter_bank(
        dec,
        ra,
        gaussian_profile,
        gradient_null_profile=gradient_null_profile,
    )

    signal = moving_lens_dipole_template(
        dec,
        ra,
        v_theta_kms=240.0,
        v_phi_kms=410.0,
        radial_deflection=lambda r: 2.0e-5 * gaussian_profile(r),
    )

    pixel_area = float((axis[1] - axis[0]) ** 2)
    phi_response = apply_filter(signal, filters["phi_matched"], pixel_area)
    theta_response = apply_filter(signal, filters["theta_matched"], pixel_area)
    rot90_response = apply_filter(signal, filters["phi_matched_rot90"], pixel_area)

    print(f"filter bank entries: {len(filters)}")
    print(f"phi response:        {phi_response:.6e}")
    print(f"theta response:      {theta_response:.6e}")
    print(f"rot90 null response: {rot90_response:.6e}")


if __name__ == "__main__":
    main()
