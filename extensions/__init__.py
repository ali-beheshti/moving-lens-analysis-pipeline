"""Portable moving-lens extensions extracted from the research workflow."""

from .moving_lens_filters import (
    apply_filter,
    build_directional_filter,
    build_filter_bank,
)
from .moving_lens_template import moving_lens_dipole_template, velocity_angle

__all__ = [
    "apply_filter",
    "build_directional_filter",
    "build_filter_bank",
    "moving_lens_dipole_template",
    "velocity_angle",
]
