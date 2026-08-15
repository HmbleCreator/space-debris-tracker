"""
High-Precision Universal Variable Lambert Solver for Orbital Rendezvous & Targeting.
References: Vallado (2013), Bate-Mueller-White (1971), Gooding (1990).
"""

import math
from dataclasses import dataclass
from typing import Optional, Tuple
import numpy as np

from aetheris.core.constants import MU_EARTH


@dataclass
class LambertSolution:
    v1: np.ndarray          # Departure velocity vector [m/s]
    v2: np.ndarray          # Arrival velocity vector [m/s]
    time_of_flight: float   # Time of flight [s]
    transfer_type: str      # "short_way" or "long_way"
    converged: bool         # Solver convergence flag


def _stumpff_c(z: float) -> float:
    """Stumpff function C(z)."""
    if z > 0:
        return (1.0 - math.cos(math.sqrt(z))) / z
    elif z < 0:
        return (math.cosh(math.sqrt(-z)) - 1.0) / (-z)
    else:
        return 0.5


def _stumpff_s(z: float) -> float:
    """Stumpff function S(z)."""
    if z > 0:
        sqrt_z = math.sqrt(z)
        return (sqrt_z - math.sin(sqrt_z)) / (sqrt_z ** 3)
    elif z < 0:
        sqrt_neg_z = math.sqrt(-z)
        return (math.sinh(sqrt_neg_z) - sqrt_neg_z) / (sqrt_neg_z ** 3)
    else:
        return 1.0 / 6.0


def solve_lambert(
    r1_vec: np.ndarray,
    r2_vec: np.ndarray,
    tof: float,
    mu: float = MU_EARTH,
    prograde: bool = True,
    max_iter: int = 150,
    tolerance: float = 1e-4
) -> LambertSolution:
    """
    Solve Lambert's problem for orbital transfer from r1 to r2 in time tof.
    r1_vec: Departure position vector [m]
    r2_vec: Arrival position vector [m]
    tof: Time of flight in seconds (> 0)
    mu: Gravitational parameter [m^3/s^2]
    prograde: True for prograde transfer, False for retrograde
    """
    r1 = np.linalg.norm(r1_vec)
    r2 = np.linalg.norm(r2_vec)

    if r1 <= 0 or r2 <= 0 or tof <= 0:
        raise ValueError("Invalid parameters for Lambert solver.")

    cos_dnu = np.clip(np.dot(r1_vec, r2_vec) / (r1 * r2), -1.0, 1.0)
    cross_prod = np.cross(r1_vec, r2_vec)

    if prograde:
        dnu = math.acos(cos_dnu) if cross_prod[2] >= 0 else (2.0 * math.pi - math.acos(cos_dnu))
    else:
        dnu = (2.0 * math.pi - math.acos(cos_dnu)) if cross_prod[2] >= 0 else math.acos(cos_dnu)

    transfer_type = "short_way" if dnu < math.pi else "long_way"

    # Constant A
    a_param = math.sin(dnu) * math.sqrt((r1 * r2) / (1.0 - cos_dnu))
    if abs(a_param) < 1e-12:
        # 180 degree transfer singularity fallback
        a_param = 1e-6

    # Initial guess for universal variable z
    z = 0.0
    ratio = 1.0
    converged = False

    for _ in range(max_iter):
        s_z = _stumpff_s(z)
        c_z = _stumpff_c(z)

        # y(z)
        if c_z == 0:
            z += 0.1
            continue

        y_z = r1 + r2 + a_param * (z * s_z - 1.0) / math.sqrt(c_z)

        if a_param > 0.0 and y_z < 0.0:
            # Adjust z to ensure positive y_z
            z += 0.1
            continue

        if y_z < 0:
            y_z = 1e-6

        sqrt_y = math.sqrt(y_z)
        x_z = sqrt_y / math.sqrt(c_z)

        # Time of flight t(z)
        t_z = (x_z ** 3 * s_z + a_param * sqrt_y) / math.sqrt(mu)

        # Derivative dt/dz
        if abs(z) > 1e-6:
            dt_dz = (
                (x_z ** 3 * (s_z - 1.5 * s_z / c_z + 0.5 * c_z / (s_z if s_z != 0 else 1e-6))
                 + 0.125 * a_param * (3.0 * s_z * sqrt_y / c_z + a_param / x_z))
                / math.sqrt(mu)
            )
        else:
            dt_dz = (math.sqrt(2.0) / 40.0) * (y_z ** 1.5) + (a_param / 8.0) * (
                math.sqrt(y_z) + a_param * math.sqrt(0.5 / y_z)
            )
            dt_dz /= math.sqrt(mu)

        f_z = t_z - tof

        if abs(dt_dz) < 1e-12:
            dt_dz = 1e-6 if dt_dz >= 0 else -1e-6

        delta_z = f_z / dt_dz
        z -= delta_z

        if abs(f_z) < tolerance * tof or abs(delta_z) < tolerance:
            converged = True
            break

    # Calculate Lagrange coefficients f, g, g_dot
    s_z = _stumpff_s(z)
    c_z = _stumpff_c(z)
    y_z = max(r1 + r2 + a_param * (z * s_z - 1.0) / math.sqrt(c_z), 1e-6)

    f = 1.0 - y_z / r1
    g = a_param * math.sqrt(y_z / mu)
    g_dot = 1.0 - y_z / r2

    if abs(g) < 1e-12:
        g = 1e-6

    v1 = (r2_vec - f * r1_vec) / g
    v2 = (g_dot * r2_vec - r1_vec) / g

    return LambertSolution(
        v1=v1,
        v2=v2,
        time_of_flight=tof,
        transfer_type=transfer_type,
        converged=converged
    )
