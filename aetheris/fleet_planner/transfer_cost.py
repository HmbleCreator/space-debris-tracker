"""
Non-Coplanar Orbital Transfer and Rendezvous Delta-V Cost Calculations.
Evaluates altitude changes, direct plane changes, phasing maneuvers, and combined burns.
"""

import math
from dataclasses import dataclass
from typing import Tuple
import numpy as np

from aetheris.core.constants import MU_EARTH, R_EARTH
from aetheris.core.orbital_elements import KeplerianElements


@dataclass
class TransferCostBreakdown:
    delta_v_altitude_ms: float
    delta_v_plane_change_ms: float
    delta_v_phasing_ms: float
    delta_v_total_ms: float
    transfer_time_seconds: float
    is_direct_impulsive: bool


def compute_hohmann_transfer_delta_v(
    r1: float,
    r2: float,
    mu: float = MU_EARTH
) -> Tuple[float, float, float, float]:
    """
    Compute coplanar Hohmann transfer between circular orbits of radius r1 and r2.
    Returns: (dv1, dv2, dv_total, transfer_time_seconds)
    """
    if r1 <= 0 or r2 <= 0:
        raise ValueError("Orbital radii must be positive.")

    v1 = math.sqrt(mu / r1)
    v2 = math.sqrt(mu / r2)

    a_trans = 0.5 * (r1 + r2)
    v_trans_1 = math.sqrt(mu * (2.0 / r1 - 1.0 / a_trans))
    v_trans_2 = math.sqrt(mu * (2.0 / r2 - 1.0 / a_trans))

    dv1 = abs(v_trans_1 - v1)
    dv2 = abs(v2 - v_trans_2)
    dv_total = dv1 + dv2

    tof = math.pi * math.sqrt((a_trans ** 3) / mu)

    return float(dv1), float(dv2), float(dv_total), float(tof)


def compute_direct_plane_change_delta_v(
    v_orbital: float,
    delta_inc_rad: float
) -> float:
    """
    Compute impulsive velocity increment for pure inclination change:
    dv = 2 * v * sin(delta_i / 2)
    """
    return float(2.0 * v_orbital * math.sin(abs(delta_inc_rad) * 0.5))


def compute_combined_plane_change_hohmann_delta_v(
    r1: float,
    r2: float,
    delta_inc_rad: float,
    mu: float = MU_EARTH
) -> Tuple[float, float, float, float]:
    """
    Combined Hohmann transfer with plane change performed at the apogee (slower velocity) for optimal efficiency.
    Returns: (dv1, dv2_combined, dv_total, tof_seconds)
    """
    v1 = math.sqrt(mu / r1)
    v2 = math.sqrt(mu / r2)

    r_peri = min(r1, r2)
    r_apo = max(r1, r2)
    a_trans = 0.5 * (r_peri + r_apo)

    v_trans_peri = math.sqrt(mu * (2.0 / r_peri - 1.0 / a_trans))
    v_trans_apo = math.sqrt(mu * (2.0 / r_apo - 1.0 / a_trans))

    # Burn 1 at perigee (pure in-plane)
    dv1 = abs(v_trans_peri - math.sqrt(mu / r_peri))

    # Burn 2 at apogee (combined circularization + plane change)
    v_target_circ = math.sqrt(mu / r_apo)
    dv2_combined = math.sqrt(
        v_trans_apo ** 2 + v_target_circ ** 2 - 2.0 * v_trans_apo * v_target_circ * math.cos(abs(delta_inc_rad))
    )

    dv_total = dv1 + dv2_combined
    tof = math.pi * math.sqrt((a_trans ** 3) / mu)

    return float(dv1), float(dv2_combined), float(dv_total), float(tof)


def compute_noncoplanar_direct_transfer(
    orbit_a: KeplerianElements,
    orbit_b: KeplerianElements
) -> TransferCostBreakdown:
    """
    Compute direct impulsive rendezvous cost from orbit_a to orbit_b without J2 drift waiting.
    Includes altitude adjustment, inclination plane change, and RAAN difference penalty.
    """
    r1 = orbit_a.semi_major_axis
    r2 = orbit_b.semi_major_axis

    delta_inc = orbit_b.inclination - orbit_a.inclination
    delta_raan = (orbit_b.raan - orbit_a.raan) % (2.0 * math.pi)
    if delta_raan > math.pi:
        delta_raan = 2.0 * math.pi - delta_raan

    # Total geometric plane change angle between orbital angular momentum vectors:
    # cos(theta) = cos(i1)*cos(i2) + sin(i1)*sin(i2)*cos(delta_raan)
    cos_theta = (
        math.cos(orbit_a.inclination) * math.cos(orbit_b.inclination)
        + math.sin(orbit_a.inclination) * math.sin(orbit_b.inclination) * math.cos(delta_raan)
    )
    total_plane_change_rad = math.acos(np.clip(cos_theta, -1.0, 1.0))

    _, _, dv_altitude, tof = compute_hohmann_transfer_delta_v(r1, r2)
    v_mean = math.sqrt(MU_EARTH / (0.5 * (r1 + r2)))
    dv_plane = compute_direct_plane_change_delta_v(v_mean, total_plane_change_rad)

    # Phasing cost (minor mean anomaly drift adjustment ~ 30-80 m/s)
    dv_phasing = 50.0

    dv_total = dv_altitude + dv_plane + dv_phasing

    return TransferCostBreakdown(
        delta_v_altitude_ms=dv_altitude,
        delta_v_plane_change_ms=dv_plane,
        delta_v_phasing_ms=dv_phasing,
        delta_v_total_ms=dv_total,
        transfer_time_seconds=tof,
        is_direct_impulsive=True
    )
