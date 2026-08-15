"""
Atmospheric Density Models and Drag Acceleration Calculations.
Includes multi-scale-height US Standard Atmosphere 1976 and thermosphere solar activity scaling.
"""

import math
from typing import Tuple
import numpy as np

from aetheris.core.constants import OMEGA_EARTH, R_EARTH, RHO_0

# US Standard Atmosphere 1976 piecewise scale-height table
# (Base Altitude [km], Nominal Density [kg/m^3], Scale Height H [km])
ATMOSPHERE_TABLE = [
    (0.0,    1.225,       7.249),
    (25.0,   3.899e-2,    6.349),
    (50.0,   1.027e-3,    6.682),
    (75.0,   3.492e-5,    5.877),
    (100.0,  5.297e-7,    5.777),
    (120.0,  2.438e-8,    7.410),
    (150.0,  2.076e-9,    22.30),
    (200.0,  2.541e-10,   37.10),
    (250.0,  6.073e-11,   45.50),
    (300.0,  1.916e-11,   53.62),
    (350.0,  7.014e-12,   53.29),
    (400.0,  2.801e-12,   58.51),
    (450.0,  1.184e-12,   60.82),
    (500.0,  5.215e-13,   63.82),
    (600.0,  1.137e-13,   71.83),
    (700.0,  3.070e-14,   88.66),
    (800.0,  1.136e-14,   124.64),
    (900.0,  5.759e-15,   181.05),
    (1000.0, 3.561e-15,   268.00),
]


def get_atmospheric_density(
    altitude_m: float,
    f107_flux: float = 150.0,
    ap_index: float = 15.0
) -> float:
    """
    Compute atmospheric density rho [kg/m^3] at given altitude in meters.
    Interpolates US Standard Atmosphere 1976 and scales for solar activity (F10.7) and geomagnetic index (Ap).
    """
    alt_km = altitude_m / 1000.0

    if alt_km <= 0:
        return RHO_0
    if alt_km >= 1200.0:
        return 1.0e-17

    # Find atmospheric table bracket
    base_alt, base_rho, scale_h = ATMOSPHERE_TABLE[0]
    for i in range(len(ATMOSPHERE_TABLE) - 1):
        if ATMOSPHERE_TABLE[i][0] <= alt_km < ATMOSPHERE_TABLE[i + 1][0]:
            base_alt, base_rho, scale_h = ATMOSPHERE_TABLE[i]
            break
    else:
        base_alt, base_rho, scale_h = ATMOSPHERE_TABLE[-1]

    # Exponential barometric formula: rho = base_rho * exp(-(alt - base_alt) / scale_h)
    delta_h = alt_km - base_alt
    rho_base = base_rho * math.exp(-delta_h / scale_h)

    # Solar activity scaling in thermosphere (above 150 km)
    if alt_km > 150.0:
        # Solar flux modifier (F10.7 baseline is 150 sfu, ranges from 70 quiet to 250 active)
        solar_factor = 1.0 + (f107_flux - 150.0) / 300.0
        # Geomagnetic storm modifier
        geomag_factor = 1.0 + (ap_index - 15.0) / 100.0
        rho = rho_base * max(0.2, solar_factor * geomag_factor)
    else:
        rho = rho_base

    return float(rho)


def compute_drag_acceleration(
    r_eci: np.ndarray,
    v_eci: np.ndarray,
    cd: float,
    area_m2: float,
    mass_kg: float,
    f107_flux: float = 150.0,
    ap_index: float = 15.0
) -> np.ndarray:
    """
    Compute aerodynamic drag acceleration vector in ECI frame:
    a_drag = -0.5 * Cd * (A / m) * rho * |v_rel| * v_rel
    """
    r_mag = np.linalg.norm(r_eci)
    alt_m = r_mag - R_EARTH

    if alt_m > 1000000.0 or mass_kg <= 0:
        return np.zeros(3, dtype=np.float64)

    # Relative velocity accounting for Earth atmosphere co-rotation:
    # v_rel = v_eci - omega x r_eci
    omega_vec = np.array([0.0, 0.0, OMEGA_EARTH], dtype=np.float64)
    v_rel = v_eci - np.cross(omega_vec, r_eci)
    v_rel_mag = np.linalg.norm(v_rel)

    if v_rel_mag < 1e-6:
        return np.zeros(3, dtype=np.float64)

    rho = get_atmospheric_density(alt_m, f107_flux, ap_index)

    # Compute drag acceleration vector
    drag_factor = -0.5 * cd * (area_m2 / mass_kg) * rho * v_rel_mag
    a_drag = drag_factor * v_rel

    return a_drag
