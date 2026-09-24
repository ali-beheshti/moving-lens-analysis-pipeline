"""Portable moving-lens dipole template utilities.

The research code painted moving-lens signals using each halo's transverse
velocity and a radial deflection profile.  These helpers isolate that idea in a
small, testable form that does not depend on the legacy ThumbStack codebase or
survey-specific catalogs.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

RadialDeflection = Callable[[np.ndarray], np.ndarray]


def velocity_angle(v_theta_kms: float, v_phi_kms: float) -> float:
    """Angle of the transverse velocity vector in the local tangent plane."""
    return float(np.arctan2(v_theta_kms, v_phi_kms))


def moving_lens_dipole_template(
    dec_offset_rad: np.ndarray,
    ra_offset_rad: np.ndarray,
    *,
    v_theta_kms: float,
    v_phi_kms: float,
    radial_deflection: RadialDeflection,
    tcmb_uk: float = 2.726e6,
    c_kms: float = 299_792.458,
) -> np.ndarray:
    """Generate a moving-lens temperature dipole for one object.

    ``radial_deflection(radius)`` supplies the magnitude of the lensing
    deflection angle (dimensionless).  The template then projects the object's
    transverse velocity onto the local deflection direction.

    This decomposition mirrors the research workflow while leaving the halo
    profile/model choice explicit and replaceable.
    """
    dec = np.asarray(dec_offset_rad, dtype=float)
    ra = np.asarray(ra_offset_rad, dtype=float)
    if dec.shape != ra.shape:
        raise ValueError("dec_offset_rad and ra_offset_rad must have the same shape")

    radius = np.hypot(ra, dec)
    deflection = np.asarray(radial_deflection(radius), dtype=float)
    if deflection.shape != radius.shape:
        deflection = np.broadcast_to(deflection, radius.shape)

    transverse_speed = float(np.hypot(v_theta_kms, v_phi_kms))
    if transverse_speed == 0.0:
        return np.zeros_like(radius)

    v_angle = velocity_angle(v_theta_kms, v_phi_kms)
    position_angle = np.arctan2(dec, ra)

    return (
        deflection
        * (transverse_speed / c_kms)
        * np.cos(v_angle - position_angle)
        * tcmb_uk
    )
