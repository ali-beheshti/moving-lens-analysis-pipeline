"""Moving-lens directional matched-filter helpers.

This module is a compact, dependency-light re-expression of the moving-lens
filtering functionality developed for the research ThumbStack workflow.  It is
not a copy of the upstream ThumbStack package and is not intended to be a
full replacement for it.

The filters capture the pieces that are distinctive to the moving-lens
analysis:

* phi- and theta-oriented dipole templates,
* 90-degree rotated null templates,
* support for a gradient-nulled radial profile, and
* direct integration of a filter against a map cutout.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Literal

import numpy as np

Component = Literal["phi", "theta"]
RadialProfile = Callable[[np.ndarray], np.ndarray]


def _component_angle(component: Component) -> float:
    """Return the Cartesian orientation used for one transverse component."""
    if component == "phi":
        return 0.0
    if component == "theta":
        return -0.5 * np.pi
    raise ValueError("component must be 'phi' or 'theta'")


def build_directional_filter(
    dec_offset_rad: np.ndarray,
    ra_offset_rad: np.ndarray,
    radial_profile: RadialProfile,
    *,
    component: Component = "phi",
    rotate_90: bool = False,
    max_radius_rad: float = np.deg2rad(6.0 / 60.0),
) -> np.ndarray:
    """Construct an oriented moving-lens dipole filter on a map cutout.

    Parameters
    ----------
    dec_offset_rad, ra_offset_rad
        Two-dimensional angular-offset grids, centered on the object.
    radial_profile
        Callable returning the radial matched-filter amplitude for radii in
        radians.  A standard or gradient-nulled profile can be supplied.
    component
        ``"phi"`` for the horizontal transverse component or ``"theta"`` for
        the orthogonal component.
    rotate_90
        Rotate the dipole by 90 degrees.  This is useful as a null test.
    max_radius_rad
        Compact support radius for the filter.

    Returns
    -------
    numpy.ndarray
        Dimensionless directional filter weights.
    """
    dec = np.asarray(dec_offset_rad, dtype=float)
    ra = np.asarray(ra_offset_rad, dtype=float)
    if dec.shape != ra.shape:
        raise ValueError("dec_offset_rad and ra_offset_rad must have the same shape")

    radius = np.hypot(ra, dec)
    radial = np.asarray(radial_profile(radius), dtype=float)
    if radial.shape != radius.shape:
        radial = np.broadcast_to(radial, radius.shape)

    # The deflection direction is inward toward the halo center.
    deflection_angle = np.pi + np.arctan2(dec, ra)
    orientation = _component_angle(component)
    if rotate_90:
        orientation += 0.5 * np.pi

    support = radius <= max_radius_rad
    return support * radial * np.cos(orientation - deflection_angle)


def build_filter_bank(
    dec_offset_rad: np.ndarray,
    ra_offset_rad: np.ndarray,
    standard_profile: RadialProfile,
    *,
    gradient_null_profile: RadialProfile | None = None,
    max_radius_rad: float = np.deg2rad(6.0 / 60.0),
) -> Mapping[str, np.ndarray]:
    """Build the standard moving-lens filters and their null-test variants."""
    bank: dict[str, np.ndarray] = {}

    for component in ("phi", "theta"):
        bank[f"{component}_matched"] = build_directional_filter(
            dec_offset_rad,
            ra_offset_rad,
            standard_profile,
            component=component,
            max_radius_rad=max_radius_rad,
        )
        bank[f"{component}_matched_rot90"] = build_directional_filter(
            dec_offset_rad,
            ra_offset_rad,
            standard_profile,
            component=component,
            rotate_90=True,
            max_radius_rad=max_radius_rad,
        )

        if gradient_null_profile is not None:
            bank[f"{component}_matched_nullgrad"] = build_directional_filter(
                dec_offset_rad,
                ra_offset_rad,
                gradient_null_profile,
                component=component,
                max_radius_rad=max_radius_rad,
            )
            bank[f"{component}_matched_rot90_nullgrad"] = build_directional_filter(
                dec_offset_rad,
                ra_offset_rad,
                gradient_null_profile,
                component=component,
                rotate_90=True,
                max_radius_rad=max_radius_rad,
            )

    return bank


def apply_filter(
    map_cutout: np.ndarray,
    filter_weights: np.ndarray,
    pixel_area_sr: float | np.ndarray,
) -> float:
    """Integrate a filter against a map cutout using pixel solid angle."""
    data = np.asarray(map_cutout, dtype=float)
    weights = np.asarray(filter_weights, dtype=float)
    if data.shape != weights.shape:
        raise ValueError("map_cutout and filter_weights must have the same shape")
    return float(np.sum(np.asarray(pixel_area_sr) * weights * data))
