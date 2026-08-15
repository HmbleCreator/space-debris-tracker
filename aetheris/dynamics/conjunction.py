"""
Conjunction Assessment & Collision Probability (Pc) Assessment Engine.
Implements 2D/3D Foster encounter plane projection and collision probability calculation.
"""

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple
import numpy as np

from aetheris.catalog.debris_object import DebrisObject


@dataclass
class ConjunctionEvent:
    primary_norad_id: int
    primary_name: str
    secondary_norad_id: int
    secondary_name: str
    miss_distance_m: float
    relative_velocity_kms: float
    hard_body_radius_m: float
    collision_probability: float
    time_of_closest_approach_sec: float
    risk_level: str  # "LOW", "MEDIUM", "HIGH", "CRITICAL"


def compute_2d_collision_probability(
    miss_distance_m: float,
    combined_radius_m: float,
    sigma_x_m: float = 100.0,
    sigma_y_m: float = 100.0
) -> float:
    """
    Compute 2D Foster collision probability on B-plane encounter cross-section:
    Pc = (R_HBR^2 / (2 * sigma_x * sigma_y)) * exp(-d_miss^2 / (2 * sigma_eff^2))
    """
    if combined_radius_m <= 0 or sigma_x_m <= 0 or sigma_y_m <= 0:
        return 0.0

    sigma_eff2 = 0.5 * (sigma_x_m ** 2 + sigma_y_m ** 2)
    exponent = -(miss_distance_m ** 2) / (2.0 * sigma_eff2)

    # Upper bound / small circle approximation
    p_c = (combined_radius_m ** 2 / (2.0 * sigma_x_m * sigma_y_m)) * math.exp(np.clip(exponent, -50.0, 0.0))
    p_c = float(np.clip(p_c, 0.0, 1.0))
    return p_c


def assess_conjunction(
    obj1: DebrisObject,
    r1_m: np.ndarray,
    v1_ms: np.ndarray,
    obj2: DebrisObject,
    r2_m: np.ndarray,
    v2_ms: np.ndarray,
    tca_sec: float = 0.0
) -> Optional[ConjunctionEvent]:
    """
    Assess close approach between two space objects.
    """
    r_rel = r1_m - r2_m
    miss_dist_m = float(np.linalg.norm(r_rel))

    # Fast filter: only evaluate if miss distance < 50 km
    if miss_dist_m > 50000.0:
        return None

    v_rel = v1_ms - v2_ms
    v_rel_kms = float(np.linalg.norm(v_rel) / 1000.0)

    # Combined Hard Body Radius (HBR)
    hbr_m = 0.5 * (obj1.characteristic_size_m + obj2.characteristic_size_m) + 2.0

    # Covariance scale based on tracking accuracy
    sigma_pos = 150.0  # 150m standard 1-sigma uncertainty

    p_c = compute_2d_collision_probability(
        miss_distance_m=miss_dist_m,
        combined_radius_m=hbr_m,
        sigma_x_m=sigma_pos,
        sigma_y_m=sigma_pos
    )

    if p_c > 1e-3:
        risk = "CRITICAL"
    elif p_c > 1e-4:
        risk = "HIGH"
    elif p_c > 1e-6:
        risk = "MEDIUM"
    else:
        risk = "LOW"

    return ConjunctionEvent(
        primary_norad_id=obj1.norad_id,
        primary_name=obj1.name,
        secondary_norad_id=obj2.norad_id,
        secondary_name=obj2.name,
        miss_distance_m=round(miss_dist_m, 2),
        relative_velocity_kms=round(v_rel_kms, 3),
        hard_body_radius_m=round(hbr_m, 2),
        collision_probability=p_c,
        time_of_closest_approach_sec=tca_sec,
        risk_level=risk
    )
