"""
Data Structures for Space Debris and Orbital Objects.
Distinguishes deterministically measured orbital elements from statistically estimated physical parameters.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
import numpy as np

from aetheris.core.orbital_elements import KeplerianElements


class ObjectType(str, Enum):
    ROCKET_BODY = "ROCKET_BODY"
    PAYLOAD = "PAYLOAD"
    FRAGMENTATION_DEBRIS = "FRAGMENTATION_DEBRIS"
    MISSION_RELATED_DEBRIS = "MISSION_RELATED_DEBRIS"
    UNKNOWN = "UNKNOWN"


class OrbitRegime(str, Enum):
    LEO = "LEO"      # Low Earth Orbit (alt < 2000 km)
    MEO = "MEO"      # Medium Earth Orbit (2000 km <= alt < 35786 km)
    GEO = "GEO"      # Geostationary Orbit (~35786 km, e ~ 0, i ~ 0)
    HEO = "HEO"      # Highly Elliptical Orbit (e > 0.25)


@dataclass
class MaterialFraction:
    material_key: str
    mass_fraction: float  # 0.0 to 1.0


@dataclass
class DebrisObject:
    # -----------------------------------------------------------------------
    # Deterministic / Measured Data (from TLE / Ephemeris catalog)
    # -----------------------------------------------------------------------
    norad_id: int
    name: str
    intl_designator: str
    epoch: datetime
    keplerian: KeplerianElements
    b_star: float  # Drag parameter from TLE [1/Earth radii]
    mean_motion_rev_day: float
    tle_line1: Optional[str] = None
    tle_line2: Optional[str] = None

    # -----------------------------------------------------------------------
    # Statistically Estimated Properties (NASA Standard Breakup / Empirical)
    # -----------------------------------------------------------------------
    object_type: ObjectType = ObjectType.UNKNOWN
    characteristic_size_m: float = 1.0     # dc [m]
    cross_sectional_area_m2: float = 1.0   # A [m^2]
    estimated_mass_kg: float = 100.0       # m [kg]
    radar_cross_section_m2: float = 1.0    # RCS [m^2]
    drag_coefficient_cd: float = 2.2       # Standard hyperthermal drag coeff
    ballistic_coefficient_kg_m2: float = 50.0  # B = m / (Cd * A)

    # Material composition breakdown (e.g. Al, Ti, Stainless Steel)
    material_breakdown: Dict[str, float] = field(default_factory=lambda: {
        "ALUMINUM_6061": 0.85,
        "TITANIUM_TI6AL4V": 0.10,
        "STAINLESS_STEEL_304": 0.05
    })

    # Computed Risk & Operational Metrics
    criticality_score: float = 0.0
    collision_probability_annual: float = 0.0
    orbit_regime: OrbitRegime = OrbitRegime.LEO
    is_statistically_estimated: bool = True

    def __post_init__(self):
        # Determine orbit regime
        hp = self.keplerian.perigee_altitude_km
        ha = self.keplerian.apogee_altitude_km
        e = self.keplerian.eccentricity

        if e > 0.25:
            self.orbit_regime = OrbitRegime.HEO
        elif ha < 2000.0:
            self.orbit_regime = OrbitRegime.LEO
        elif 35000.0 <= hp <= 36500.0 and 35000.0 <= ha <= 36500.0 and self.keplerian.inclination < 0.2:
            self.orbit_regime = OrbitRegime.GEO
        else:
            self.orbit_regime = OrbitRegime.MEO

    @property
    def area_to_mass_ratio(self) -> float:
        """Area to mass ratio A/m [m^2 / kg]."""
        if self.estimated_mass_kg <= 0:
            return 0.01
        return self.cross_sectional_area_m2 / self.estimated_mass_kg

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dictionary."""
        return {
            "norad_id": self.norad_id,
            "name": self.name,
            "intl_designator": self.intl_designator,
            "epoch": self.epoch.isoformat(),
            "orbit_regime": self.orbit_regime.value,
            "object_type": self.object_type.value,
            "semi_major_axis_km": self.keplerian.semi_major_axis / 1000.0,
            "eccentricity": round(self.keplerian.eccentricity, 6),
            "inclination_deg": round(np.degrees(self.keplerian.inclination), 4),
            "raan_deg": round(np.degrees(self.keplerian.raan), 4),
            "arg_of_perigee_deg": round(np.degrees(self.keplerian.arg_of_perigee), 4),
            "true_anomaly_deg": round(np.degrees(self.keplerian.true_anomaly), 4),
            "perigee_alt_km": round(self.keplerian.perigee_altitude_km, 2),
            "apogee_alt_km": round(self.keplerian.apogee_altitude_km, 2),
            "period_minutes": round(self.keplerian.period / 60.0, 2),
            "j2_raan_drift_deg_per_day": round(self.keplerian.j2_raan_drift_deg_per_day, 4),
            "b_star": self.b_star,
            "characteristic_size_m": round(self.characteristic_size_m, 3),
            "cross_sectional_area_m2": round(self.cross_sectional_area_m2, 3),
            "estimated_mass_kg": round(self.estimated_mass_kg, 2),
            "radar_cross_section_m2": round(self.radar_cross_section_m2, 3),
            "ballistic_coefficient_kg_m2": round(self.ballistic_coefficient_kg_m2, 2),
            "material_breakdown": self.material_breakdown,
            "criticality_score": round(self.criticality_score, 4),
            "collision_probability_annual": self.collision_probability_annual,
            "is_statistically_estimated": self.is_statistically_estimated
        }
