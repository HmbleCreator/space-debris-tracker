"""
J2 Earth Oblateness Nodal Precession Drift Optimizer.
Solves for optimal drift orbits to match orbital planes at a fraction of direct impulsive Delta-V cost.
"""

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import numpy as np

from aetheris.core.constants import MU_EARTH, R_EARTH, J2
from aetheris.core.orbital_elements import KeplerianElements
from aetheris.fleet_planner.transfer_cost import (
    compute_hohmann_transfer_delta_v,
    compute_direct_plane_change_delta_v,
    TransferCostBreakdown
)


@dataclass
class J2DriftTransferPlan:
    origin_raan_deg: float
    target_raan_deg: float
    raan_difference_deg: float
    drift_altitude_km: float
    drift_duration_days: float
    delta_v_to_drift_ms: float
    delta_v_from_drift_ms: float
    delta_v_plane_trim_ms: float
    delta_v_phasing_ms: float
    delta_v_total_ms: float
    direct_impulsive_delta_v_ms: float
    propellant_savings_percent: float


def compute_j2_raan_precession_rate(semi_major_axis_m: float, inclination_rad: float, eccentricity: float = 0.0) -> float:
    """
    Compute nodal precession rate dOmega/dt in rad/s:
    dOmega/dt = -1.5 * J2 * (R_E / p)^2 * n * cos(i)
    """
    p = semi_major_axis_m * (1.0 - eccentricity ** 2)
    if p <= 0:
        return 0.0
    n = math.sqrt(MU_EARTH / (semi_major_axis_m ** 3))
    return float(-1.5 * J2 * ((R_EARTH / p) ** 2) * n * math.cos(inclination_rad))


def optimize_j2_drift_transfer(
    orbit_a: KeplerianElements,
    orbit_b: KeplerianElements,
    max_drift_days: float = 90.0,
    min_drift_alt_km: float = 400.0,
    max_drift_alt_km: float = 1200.0
) -> J2DriftTransferPlan:
    """
    Optimize J2 drift transfer between orbit_a and orbit_b.
    Searches for the optimal intermediate drift altitude that aligns RAAN within max_drift_days
    while minimizing total Delta-V.
    """
    raan_a_deg = math.degrees(orbit_a.raan) % 360.0
    raan_b_deg = math.degrees(orbit_b.raan) % 360.0

    delta_raan_deg = (raan_b_deg - raan_a_deg) % 360.0
    if delta_raan_deg > 180.0:
        delta_raan_deg -= 360.0  # Allow negative or positive drift

    delta_raan_rad = math.radians(delta_raan_deg)

    # If RAAN difference is nearly zero (< 1 deg), direct Hohmann transfer is best
    r_a = orbit_a.semi_major_axis
    r_b = orbit_b.semi_major_axis
    delta_inc = abs(orbit_b.inclination - orbit_a.inclination)

    _, _, dv_alt_direct, _ = compute_hohmann_transfer_delta_v(r_a, r_b)
    v_mean = math.sqrt(MU_EARTH / (0.5 * (r_a + r_b)))
    dv_plane_direct = compute_direct_plane_change_delta_v(v_mean, delta_inc)

    # Brute-force direct plane change with RAAN change
    cos_theta = (
        math.cos(orbit_a.inclination) * math.cos(orbit_b.inclination)
        + math.sin(orbit_a.inclination) * math.sin(orbit_b.inclination) * math.cos(delta_raan_rad)
    )
    direct_tot_plane_rad = math.acos(np.clip(cos_theta, -1.0, 1.0))
    direct_impulsive_dv = dv_alt_direct + compute_direct_plane_change_delta_v(v_mean, direct_tot_plane_rad) + 50.0

    if abs(delta_raan_deg) < 1.5:
        # Coplanar or near-coplanar
        return J2DriftTransferPlan(
            origin_raan_deg=round(raan_a_deg, 2),
            target_raan_deg=round(raan_b_deg, 2),
            raan_difference_deg=round(delta_raan_deg, 2),
            drift_altitude_km=round((r_b - R_EARTH) / 1000.0, 1),
            drift_duration_days=0.5,
            delta_v_to_drift_ms=round(dv_alt_direct * 0.5, 2),
            delta_v_from_drift_ms=round(dv_alt_direct * 0.5, 2),
            delta_v_plane_trim_ms=round(dv_plane_direct, 2),
            delta_v_phasing_ms=40.0,
            delta_v_total_ms=round(dv_alt_direct + dv_plane_direct + 40.0, 2),
            direct_impulsive_delta_v_ms=round(direct_impulsive_dv, 2),
            propellant_savings_percent=round(max(0.0, 100.0 * (1.0 - (dv_alt_direct + dv_plane_direct + 40.0) / direct_impulsive_dv)), 1)
        )

    # Precession rate of target orbit B
    dot_omega_b = compute_j2_raan_precession_rate(r_b, orbit_b.inclination, orbit_b.eccentricity)

    # Grid search across candidate drift altitudes to find minimum Delta-V within max_drift_days
    candidate_altitudes = np.linspace(300.0, 1800.0, 151)

    best_plan: Optional[J2DriftTransferPlan] = None
    min_dv = float("inf")

    angle_options = [delta_raan_rad, delta_raan_rad - 2.0 * math.pi, delta_raan_rad + 2.0 * math.pi]

    for alt_km in candidate_altitudes:
        r_drift = R_EARTH + alt_km * 1000.0
        dot_omega_drift = compute_j2_raan_precession_rate(r_drift, orbit_a.inclination, 0.0)

        delta_dot_omega = dot_omega_drift - dot_omega_b
        if abs(delta_dot_omega) < 1e-12:
            continue

        for target_d_raan in angle_options:
            drift_time_sec = target_d_raan / delta_dot_omega
            if drift_time_sec <= 0:
                continue

            drift_days = drift_time_sec / 86400.0
            if drift_days > max_drift_days or drift_days < 0.2:
                continue

            # Delta-V costs:
            _, _, dv_to_drift, _ = compute_hohmann_transfer_delta_v(r_a, r_drift)
            _, _, dv_from_drift, _ = compute_hohmann_transfer_delta_v(r_drift, r_b)
            dv_inc_trim = compute_direct_plane_change_delta_v(math.sqrt(MU_EARTH / max(r_drift, r_b)), delta_inc)
            dv_phasing = 40.0

            dv_total = dv_to_drift + dv_from_drift + dv_inc_trim + dv_phasing
            cost = dv_total + (drift_days / max_drift_days) * 25.0

            if cost < min_dv:
                min_dv = cost
                savings_pct = max(0.0, 100.0 * (1.0 - dv_total / max(1.0, direct_impulsive_dv)))
                best_plan = J2DriftTransferPlan(
                    origin_raan_deg=round(raan_a_deg, 2),
                    target_raan_deg=round(raan_b_deg, 2),
                    raan_difference_deg=round(delta_raan_deg, 2),
                    drift_altitude_km=round(alt_km, 1),
                    drift_duration_days=round(drift_days, 1),
                    delta_v_to_drift_ms=round(dv_to_drift, 2),
                    delta_v_from_drift_ms=round(dv_from_drift, 2),
                    delta_v_plane_trim_ms=round(dv_inc_trim, 2),
                    delta_v_phasing_ms=round(dv_phasing, 2),
                    delta_v_total_ms=round(dv_total, 2),
                    direct_impulsive_delta_v_ms=round(direct_impulsive_dv, 2),
                    propellant_savings_percent=round(savings_pct, 1)
                )



    if best_plan is None:
        # Fallback to direct transfer if no drift solution within max_drift_days
        best_plan = J2DriftTransferPlan(
            origin_raan_deg=round(raan_a_deg, 2),
            target_raan_deg=round(raan_b_deg, 2),
            raan_difference_deg=round(delta_raan_deg, 2),
            drift_altitude_km=round((r_b - R_EARTH) / 1000.0, 1),
            drift_duration_days=1.0,
            delta_v_to_drift_ms=round(dv_alt_direct, 2),
            delta_v_from_drift_ms=0.0,
            delta_v_plane_trim_ms=round(direct_impulsive_dv - dv_alt_direct - 50.0, 2),
            delta_v_phasing_ms=50.0,
            delta_v_total_ms=round(direct_impulsive_dv, 2),
            direct_impulsive_delta_v_ms=round(direct_impulsive_dv, 2),
            propellant_savings_percent=0.0
        )

    return best_plan
