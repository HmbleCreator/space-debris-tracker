"""
Statistical Characterization and Physical Parameter Estimator for Space Debris.
Implements empirical power laws from NASA Standard Breakup Model & ESA DISCOS typologies.
"""

import math
from typing import Dict, Tuple
import numpy as np

from aetheris.catalog.debris_object import ObjectType
from aetheris.core.constants import RHO_0, R_EARTH


def estimate_ballistic_coefficient_from_bstar(b_star: float, cd: float = 2.2) -> Tuple[float, float]:
    """
    Inverse estimation of Ballistic Coefficient B = m / (Cd * A) and Area-to-Mass ratio (A/m)
    from TLE B* parameter.
    B* definition: B* = (rho_0 / 2) * (Cd * A / m) * (1 / R_Earth) in units of 1/Earth-radii.
    Returns: (B [kg/m^2], A/m [m^2/kg])
    """
    if abs(b_star) < 1e-12:
        # Default typical LEO values
        return 50.0, 0.009

    # Solve for (Cd * A / m):
    # b_star = 0.5 * rho_0 * (Cd * A / m) * R_earth
    # Note: In standard SGP4, B* is in 1/Earth_radii
    cd_a_over_m = abs(b_star) / (0.5 * RHO_0 * R_EARTH)
    a_over_m = cd_a_over_m / cd

    # Safety clamping
    a_over_m = np.clip(a_over_m, 0.0001, 10.0)
    ballistic_coeff = 1.0 / (cd * a_over_m)

    return float(ballistic_coeff), float(a_over_m)


def classify_object_by_name_and_orbit(name: str, intl_desig: str, mean_motion: float, apogee_km: float) -> ObjectType:
    """Classify space object into ObjectType based on standard catalog nomenclature."""
    name_upper = name.upper()
    if "DEB" in name_upper or "FRAGMENT" in name_upper or "FENGYUN 1C" in name_upper or "COSMOS 2251" in name_upper:
        return ObjectType.FRAGMENTATION_DEBRIS
    elif "R/B" in name_upper or "ROCKET" in name_upper or "STAGE" in name_upper or "SL-" in name_upper or "CENTAUR" in name_upper or "FALCON 9 R/B" in name_upper:
        return ObjectType.ROCKET_BODY
    elif "MISSION" in name_upper or "COVER" in name_upper or "SHROUD" in name_upper or "ADAPTER" in name_upper:
        return ObjectType.MISSION_RELATED_DEBRIS
    else:
        return ObjectType.PAYLOAD


def estimate_physical_properties(
    object_type: ObjectType,
    b_star: float,
    seed: int = 42
) -> Tuple[float, float, float, float, float, Dict[str, float]]:
    """
    Estimate characteristic size dc [m], cross-sectional area A [m^2], mass m [kg],
    RCS [m^2], ballistic coefficient B [kg/m^2], and material breakdown.
    Uses empirical spacecraft distributions and NASA Standard Breakup Model log-normal area-to-mass ratios.
    """
    np.random.seed((seed + 1000) % 2**32)

    if object_type == ObjectType.ROCKET_BODY:
        # Typical upper stages (SL-16, SL-08, Centaur, Delta, Long March)
        # dc between 3.0m and 11.0m, mass between 1200 kg and 9000 kg
        dc = float(np.random.uniform(3.5, 9.0))
        area = float(math.pi * (dc * 0.5) ** 2 * np.random.uniform(1.2, 2.5))  # Cylindrical projected area
        mass = float(180.0 * (dc ** 2.1) * np.random.uniform(0.9, 1.2))
        rcs = float(area * np.random.uniform(1.1, 1.8))
        cd = 2.2
        ballistic_coeff = mass / (cd * area)

        # Rocket bodies have heavy titanium propellant tanks and stainless steel engine bells
        materials = {
            "ALUMINUM_6061": 0.65,
            "TITANIUM_TI6AL4V": 0.20,
            "STAINLESS_STEEL_304": 0.12,
            "INCONEL_718": 0.03
        }

    elif object_type == ObjectType.PAYLOAD:
        # Defunct or intact spacecraft (e.g. Envisat, ADEOS, old communications satellites)
        dc = float(np.random.uniform(1.2, 4.5))
        area = float(dc ** 1.8 * np.random.uniform(0.8, 1.5))
        mass = float(120.0 * (dc ** 2.0) * np.random.uniform(0.85, 1.3))
        rcs = float(area * np.random.uniform(0.8, 1.4))
        cd = 2.2
        ballistic_coeff = mass / (cd * area)

        materials = {
            "ALUMINUM_6061": 0.70,
            "TITANIUM_TI6AL4V": 0.12,
            "CARBON_COMPOSITE_CFRP": 0.10,
            "STAINLESS_STEEL_304": 0.08
        }

    elif object_type == ObjectType.FRAGMENTATION_DEBRIS:
        # NASA Standard Breakup Model for fragments
        # Power-law size distribution
        dc = float(np.random.pareto(a=2.0) * 0.15 + 0.05)
        dc = float(np.clip(dc, 0.05, 1.5))
        area = float(math.pi * (dc * 0.5) ** 2)

        # NASA SBM mass-to-size: M = 1250 * dc^2.26 for dc >= 0.11m
        if dc >= 0.11:
            mass = float(1250.0 * (dc ** 2.26) * np.random.uniform(0.7, 1.3))
        else:
            mass = float(800.0 * (dc ** 2.5) * np.random.uniform(0.5, 1.5))

        mass = max(mass, 0.05)
        rcs = float(area * np.random.uniform(0.7, 1.2))
        cd = 2.2
        ballistic_coeff = mass / (cd * area)

        materials = {
            "ALUMINUM_6061": 0.85,
            "TITANIUM_TI6AL4V": 0.10,
            "STAINLESS_STEEL_304": 0.05
        }

    else:  # MISSION_RELATED_DEBRIS or UNKNOWN
        dc = float(np.random.uniform(0.3, 1.8))
        area = float(math.pi * (dc * 0.5) ** 2)
        mass = float(30.0 * (dc ** 2.2) * np.random.uniform(0.7, 1.3))
        rcs = float(area * np.random.uniform(0.8, 1.2))
        cd = 2.2
        ballistic_coeff = mass / (cd * area)

        materials = {
            "ALUMINUM_6061": 0.80,
            "TITANIUM_TI6AL4V": 0.15,
            "STAINLESS_STEEL_304": 0.05
        }

    return dc, area, mass, rcs, ballistic_coeff, materials
