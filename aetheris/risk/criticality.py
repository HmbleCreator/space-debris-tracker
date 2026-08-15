"""
Environmental Criticality Index (Ci) and Collision Risk Engine.
Ranks space objects by mass, cross-sectional area, spatial density, and catastrophic collision consequence.
"""

import math
from typing import Dict, List, Tuple
import numpy as np

from aetheris.catalog.debris_object import DebrisObject, ObjectType
from aetheris.core.constants import R_EARTH


def compute_spatial_density_leo(altitude_km: float, inclination_deg: float) -> float:
    """
    Estimate local spatial debris density [objects / km^3] in LEO based on NASA/ESA empirical models.
    Peaks around 750-900 km (Sun-Synchronous & Cosmos-Fengyun belts) and 1400 km.
    """
    # Baseline exponential distribution
    if altitude_km < 200.0 or altitude_km > 2000.0:
        return 1.0e-10

    # Gaussian peaks at 780 km (Cosmos/Iridium), 850 km (Fengyun), 1400 km
    peak_780 = 1.8e-8 * math.exp(-((altitude_km - 780.0) / 45.0) ** 2)
    peak_850 = 2.4e-8 * math.exp(-((altitude_km - 850.0) / 40.0) ** 2)
    peak_1400 = 8.5e-9 * math.exp(-((altitude_km - 1400.0) / 60.0) ** 2)
    peak_550 = 6.0e-9 * math.exp(-((altitude_km - 550.0) / 30.0) ** 2)

    # Inclination concentration factor (SSO 98° and Russian 71-82° have higher density)
    inc_factor = 1.0
    if 96.0 <= inclination_deg <= 100.0:
        inc_factor = 2.8
    elif 70.0 <= inclination_deg <= 84.0:
        inc_factor = 2.2
    elif 50.0 <= inclination_deg <= 55.0:
        inc_factor = 1.5

    density = (1.5e-9 + peak_780 + peak_850 + peak_1400 + peak_550) * inc_factor
    return density


def estimate_fragmentation_yield(mass_kg: float) -> int:
    """
    Estimate number of trackable fragments (> 10 cm) produced in catastrophic collision
    using NASA Standard Breakup Model: N(Lc >= 0.1m) = 0.1 * (M_target + M_impactor)^0.75
    Assuming catastrophic breakup kinetic energy threshold (E_k / M >= 40 kJ/kg).
    """
    if mass_kg <= 0:
        return 0
    # Average impactor mass in LEO ~ 5 kg with relative velocity ~ 10 km/s (500 MJ KE)
    total_mass = mass_kg + 5.0
    num_frags = int(0.1 * (total_mass ** 0.75) * 8.0)  # Calibrated for Lc >= 5-10cm
    return max(1, num_frags)


def compute_debris_criticality(
    obj: DebrisObject,
    catalog_objects: List[DebrisObject]
) -> float:
    """
    Compute Environmental Criticality Score C_i:
    C_i = M_i * A_i * rho_spatial(h, i) * P_collision * N_fragments(M_i) * (1 / (1 + decay_rate))
    Normalized to a 0.0 - 100.0 scale.
    """
    hp = obj.keplerian.perigee_altitude_km
    ha = obj.keplerian.apogee_altitude_km
    mean_alt = 0.5 * (hp + ha)
    inc_deg = math.degrees(obj.keplerian.inclination)

    # Spatial density at this orbital altitude and inclination
    rho = compute_spatial_density_leo(mean_alt, inc_deg)

    # Cross-sectional collision flux: Flux ~ rho * v_rel (v_rel ~ 10 km/s)
    v_rel_kms = 9.8  # average mutual encounter speed in LEO
    annual_seconds = 365.25 * 86400.0
    flux_per_m2_year = rho * (v_rel_kms * 1000.0) * annual_seconds

    # Annual collision probability
    area = max(0.01, obj.cross_sectional_area_m2)
    p_coll_annual = 1.0 - math.exp(-flux_per_m2_year * area)
    obj.collision_probability_annual = p_coll_annual

    # Number of fragments generated
    n_frags = estimate_fragmentation_yield(obj.estimated_mass_kg)

    # Orbital lifetime factor: Higher altitude = stays in orbit longer = higher risk
    if mean_alt < 500.0:
        lifetime_weight = 0.25  # decays naturally in 5-25 years
    elif mean_alt < 700.0:
        lifetime_weight = 0.65  # decays in 50-100 years
    elif mean_alt < 900.0:
        lifetime_weight = 1.00  # stays for centuries
    else:
        lifetime_weight = 1.20  # millennia

    # Raw criticality score
    mass_term = math.log10(max(1.0, obj.estimated_mass_kg))
    area_term = math.sqrt(area)
    raw_score = mass_term * area_term * (p_coll_annual * 1e4) * (n_frags ** 0.5) * lifetime_weight

    # Scale to 0.0 - 100.0
    scaled_score = float(np.clip(raw_score * 4.5, 0.01, 99.9))
    obj.criticality_score = scaled_score

    return scaled_score


def update_catalog_criticality_rankings(catalog_objects: List[DebrisObject]) -> List[DebrisObject]:
    """Calculate criticality scores for all objects and return sorted priority queue."""
    for obj in catalog_objects:
        compute_debris_criticality(obj, catalog_objects)

    # Sort descending by criticality score
    sorted_catalog = sorted(catalog_objects, key=lambda x: x.criticality_score, reverse=True)
    return sorted_catalog
