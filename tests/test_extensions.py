import unittest

import numpy as np

from extensions.moving_lens_filters import apply_filter, build_directional_filter
from extensions.moving_lens_template import moving_lens_dipole_template


class MovingLensExtensionTests(unittest.TestCase):
    def setUp(self):
        axis = np.linspace(-0.01, 0.01, 41)
        self.ra, self.dec = np.meshgrid(axis, axis)
        self.profile = lambda r: np.exp(-0.5 * (r / 0.003) ** 2)

    def test_rotated_filters_are_orthogonal_on_symmetric_grid(self):
        f0 = build_directional_filter(
            self.dec, self.ra, self.profile, component="phi", max_radius_rad=0.009
        )
        f90 = build_directional_filter(
            self.dec,
            self.ra,
            self.profile,
            component="phi",
            rotate_90=True,
            max_radius_rad=0.009,
        )
        dot = float(np.sum(f0 * f90))
        norm = float(np.sqrt(np.sum(f0**2) * np.sum(f90**2)))
        self.assertLess(abs(dot / norm), 1e-12)

    def test_zero_transverse_velocity_gives_zero_template(self):
        signal = moving_lens_dipole_template(
            self.dec,
            self.ra,
            v_theta_kms=0.0,
            v_phi_kms=0.0,
            radial_deflection=lambda r: 1e-5 * self.profile(r),
        )
        self.assertTrue(np.all(signal == 0.0))

    def test_filter_application_returns_scalar(self):
        filt = build_directional_filter(
            self.dec, self.ra, self.profile, component="theta", max_radius_rad=0.009
        )
        response = apply_filter(np.ones_like(filt), filt, 1e-8)
        self.assertIsInstance(response, float)


if __name__ == "__main__":
    unittest.main()
