"""
Earth Geopotential Spherical Harmonics Perturbations (J2 through J6).
Implements exact Cartesian gradient of the zonal geopotential field.
"""

import math
import numpy as np

from aetheris.core.constants import (
    MU_EARTH,
    R_EARTH,
    J2,
    J3,
    J4,
    J5,
    J6
)


def compute_geopotential_acceleration(
    r_eci: np.ndarray,
    max_zonal_degree: int = 4
) -> np.ndarray:
    """
    Compute Earth gravitational acceleration vector in ECI frame including
    point-mass and zonal harmonics up to max_zonal_degree (J2..J6).
    r_eci: Position vector in meters [x, y, z]
    """
    x, y, z = float(r_eci[0]), float(r_eci[1]), float(r_eci[2])
    r2 = x * x + y * y + z * z
    r = math.sqrt(r2)

    if r < 1e-6:
        return np.zeros(3, dtype=np.float64)

    r_inv = 1.0 / r
    r_inv2 = r_inv * r_inv
    r_inv3 = r_inv2 * r_inv

    # Central two-body gravity: a0 = -mu / r^3 * r
    mu_r3 = MU_EARTH * r_inv3
    ax = -mu_r3 * x
    ay = -mu_r3 * y
    az = -mu_r3 * z

    if max_zonal_degree < 2:
        return np.array([ax, ay, az], dtype=np.float64)

    # Unit ratios and powers
    re_r = R_EARTH * r_inv
    re_r2 = re_r * re_r
    z_r = z * r_inv
    z_r2 = z_r * z_r

    # -----------------------------------------------------------------------
    # J2 Perturbation
    # U_J2 = -mu/r * J2/2 * (R_E/r)^2 * (3*z_r^2 - 1)
    # Grad_J2:
    # ax_J2 = 1.5 * J2 * (mu / r^2) * (R_E / r)^2 * (x/r) * (5*z_r^2 - 1)
    # az_J2 = 1.5 * J2 * (mu / r^2) * (R_E / r)^2 * (z/r) * (5*z_r^2 - 3)
    # -----------------------------------------------------------------------
    factor_j2 = 1.5 * J2 * MU_EARTH * r_inv2 * re_r2
    ax += factor_j2 * (x * r_inv) * (5.0 * z_r2 - 1.0)
    ay += factor_j2 * (y * r_inv) * (5.0 * z_r2 - 1.0)
    az += factor_j2 * (z * r_inv) * (5.0 * z_r2 - 3.0)

    if max_zonal_degree >= 3:
        # J3 Perturbation (Pear-shaped Earth asymmetry)
        re_r3 = re_r2 * re_r
        factor_j3 = 0.5 * J3 * MU_EARTH * r_inv2 * re_r3
        ax += factor_j3 * (x * r_inv) * (35.0 * (z_r ** 3) - 15.0 * z_r)
        ay += factor_j3 * (y * r_inv) * (35.0 * (z_r ** 3) - 15.0 * z_r)
        az += factor_j3 * (35.0 * (z_r ** 4) - 30.0 * z_r2 + 3.0)

    if max_zonal_degree >= 4:
        # J4 Perturbation
        re_r4 = re_r2 * re_r2
        factor_j4 = -0.625 * J4 * MU_EARTH * r_inv2 * re_r4
        ax += factor_j4 * (x * r_inv) * (63.0 * (z_r ** 4) - 42.0 * z_r2 + 3.0)
        ay += factor_j4 * (y * r_inv) * (63.0 * (z_r ** 4) - 42.0 * z_r2 + 3.0)
        az += factor_j4 * (z * r_inv) * (63.0 * (z_r ** 4) - 70.0 * z_r2 + 15.0)

    if max_zonal_degree >= 5:
        # J5 Perturbation
        re_r5 = re_r4 * re_r
        factor_j5 = -0.125 * J5 * MU_EARTH * r_inv2 * re_r5
        ax += factor_j5 * (x * r_inv) * (693.0 * (z_r ** 5) - 630.0 * (z_r ** 3) + 105.0 * z_r)
        ay += factor_j5 * (y * r_inv) * (693.0 * (z_r ** 5) - 630.0 * (z_r ** 3) + 105.0 * z_r)
        az += factor_j5 * (693.0 * (z_r ** 6) - 945.0 * (z_r ** 4) + 315.0 * z_r2 - 15.0)

    if max_zonal_degree >= 6:
        # J6 Perturbation
        re_r6 = re_r4 * re_r2
        factor_j6 = 0.046875 * J6 * MU_EARTH * r_inv2 * re_r6
        ax += factor_j6 * (x * r_inv) * (3003.0 * (z_r ** 6) - 3465.0 * (z_r ** 4) + 945.0 * z_r2 - 35.0)
        ay += factor_j6 * (y * r_inv) * (3003.0 * (z_r ** 6) - 3465.0 * (z_r ** 4) + 945.0 * z_r2 - 35.0)
        az += factor_j6 * (z * r_inv) * (3003.0 * (z_r ** 6) - 4095.0 * (z_r ** 4) + 1575.0 * z_r2 - 105.0)

    return np.array([ax, ay, az], dtype=np.float64)
