"""
Catalog Manager for Space Debris and Orbital Objects.
Handles ingestion, realistic high-density population synthesis, filtering, and indexing.
"""

import math
from datetime import datetime, timezone
from typing import Dict, List, Optional
import numpy as np

from aetheris.catalog.debris_object import DebrisObject, ObjectType, OrbitRegime
from aetheris.catalog.characterization import (
    classify_object_by_name_and_orbit,
    estimate_physical_properties
)
from aetheris.core.constants import R_EARTH, MU_EARTH
from aetheris.core.orbital_elements import KeplerianElements


# Well-known high-profile real space debris targets for benchmark scenarios
KNOWN_BENCHMARK_DEBRIS = [
    {
        "norad_id": 27386,
        "name": "ENVISAT",
        "intl_designator": "2002-009A",
        "alt_km": 768.0,
        "ecc": 0.0001,
        "inc_deg": 98.54,
        "raan_deg": 45.0,
        "arg_p_deg": 90.0,
        "true_anom_deg": 120.0,
        "b_star": 0.000035,
        "object_type": ObjectType.PAYLOAD,
        "size_m": 10.0,
        "mass_kg": 8211.0,
        "area_m2": 26.0
    },
    {
        "norad_id": 22285,
        "name": "SL-16 R/B (COSMOS 2219)",
        "intl_designator": "1992-076B",
        "alt_km": 845.0,
        "ecc": 0.0012,
        "inc_deg": 71.01,
        "raan_deg": 110.0,
        "arg_p_deg": 45.0,
        "true_anom_deg": 15.0,
        "b_star": 0.000021,
        "object_type": ObjectType.ROCKET_BODY,
        "size_m": 10.4,
        "mass_kg": 9000.0,
        "area_m2": 31.0
    },
    {
        "norad_id": 26967,
        "name": "SL-16 R/B (COSMOS 2383)",
        "intl_designator": "2001-057B",
        "alt_km": 848.0,
        "ecc": 0.0015,
        "inc_deg": 71.02,
        "raan_deg": 125.0,
        "arg_p_deg": 60.0,
        "true_anom_deg": 210.0,
        "b_star": 0.000019,
        "object_type": ObjectType.ROCKET_BODY,
        "size_m": 10.4,
        "mass_kg": 9000.0,
        "area_m2": 31.0
    },
    {
        "norad_id": 25861,
        "name": "SL-16 R/B (COSMOS 2367)",
        "intl_designator": "1999-044B",
        "alt_km": 846.0,
        "ecc": 0.0011,
        "inc_deg": 71.00,
        "raan_deg": 138.0,
        "arg_p_deg": 120.0,
        "true_anom_deg": 300.0,
        "b_star": 0.000022,
        "object_type": ObjectType.ROCKET_BODY,
        "size_m": 10.4,
        "mass_kg": 9000.0,
        "area_m2": 31.0
    },
    {
        "norad_id": 29402,
        "name": "FENGYUN 1C DEB (ASAT FRAGMENT A)",
        "intl_designator": "1999-025DV",
        "alt_km": 865.0,
        "ecc": 0.015,
        "inc_deg": 98.8,
        "raan_deg": 88.0,
        "arg_p_deg": 210.0,
        "true_anom_deg": 45.0,
        "b_star": 0.00015,
        "object_type": ObjectType.FRAGMENTATION_DEBRIS,
        "size_m": 0.45,
        "mass_kg": 18.5,
        "area_m2": 0.16
    },
    {
        "norad_id": 33750,
        "name": "COSMOS 2251 DEB (COLLISION FRAGMENT B)",
        "intl_designator": "1993-036KW",
        "alt_km": 792.0,
        "ecc": 0.022,
        "inc_deg": 74.04,
        "raan_deg": 14.0,
        "arg_p_deg": 115.0,
        "true_anom_deg": 180.0,
        "b_star": 0.00018,
        "object_type": ObjectType.FRAGMENTATION_DEBRIS,
        "size_m": 0.38,
        "mass_kg": 12.0,
        "area_m2": 0.11
    },
    {
        "norad_id": 34440,
        "name": "IRIDIUM 33 DEB (COLLISION FRAGMENT C)",
        "intl_designator": "1997-051BM",
        "alt_km": 776.0,
        "ecc": 0.018,
        "inc_deg": 86.4,
        "raan_deg": 230.0,
        "arg_p_deg": 310.0,
        "true_anom_deg": 90.0,
        "b_star": 0.00012,
        "object_type": ObjectType.FRAGMENTATION_DEBRIS,
        "size_m": 0.28,
        "mass_kg": 7.5,
        "area_m2": 0.07
    },
    {
        "norad_id": 13778,
        "name": "SL-08 R/B (COSMOS 1445)",
        "intl_designator": "1983-021B",
        "alt_km": 940.0,
        "ecc": 0.003,
        "inc_deg": 82.9,
        "raan_deg": 310.0,
        "arg_p_deg": 180.0,
        "true_anom_deg": 25.0,
        "b_star": 0.000045,
        "object_type": ObjectType.ROCKET_BODY,
        "size_m": 6.5,
        "mass_kg": 1400.0,
        "area_m2": 15.0
    }
]


class CatalogManager:
    """Manages full orbital debris population, filtering, state extraction, and synthetic generation."""

    def __init__(self):
        self.objects: Dict[int, DebrisObject] = {}
        self._initialize_benchmark_catalog()

    def _initialize_benchmark_catalog(self):
        """Seed catalog with realistic space debris objects across high-density orbital regimes."""
        epoch_now = datetime.now(timezone.utc)

        # 1. Add real benchmark high-profile objects
        for item in KNOWN_BENCHMARK_DEBRIS:
            sma = R_EARTH + item["alt_km"] * 1000.0
            inc = math.radians(item["inc_deg"])
            raan = math.radians(item["raan_deg"])
            arg_p = math.radians(item["arg_p_deg"])
            nu = math.radians(item["true_anom_deg"])
            ecc = item["ecc"]

            kepler = KeplerianElements(
                semi_major_axis=sma,
                eccentricity=ecc,
                inclination=inc,
                raan=raan,
                arg_of_perigee=arg_p,
                true_anomaly=nu
            )

            debris = DebrisObject(
                norad_id=item["norad_id"],
                name=item["name"],
                intl_designator=item["intl_designator"],
                epoch=epoch_now,
                keplerian=kepler,
                b_star=item["b_star"],
                mean_motion_rev_day=kepler.mean_motion_rev_per_day,
                object_type=item["object_type"],
                characteristic_size_m=item["size_m"],
                cross_sectional_area_m2=item["area_m2"],
                estimated_mass_kg=item["mass_kg"],
                radar_cross_section_m2=item["area_m2"] * 1.2,
                drag_coefficient_cd=2.2,
                ballistic_coefficient_kg_m2=item["mass_kg"] / (2.2 * item["area_m2"]),
                is_statistically_estimated=False
            )
            self.objects[debris.norad_id] = debris

        # 2. Synthesize a realistic population of 500+ objects matching real LEO/MEO/GEO congestion belts
        self.generate_synthetic_population(count=450, base_seed=1337)

    def generate_synthetic_population(self, count: int = 500, base_seed: int = 42):
        """
        Generate realistic orbital debris objects following empirical altitude and inclination distributions:
        - LEO Sun-Synchronous Belt (alt 700-900 km, inc ~98 deg)
        - LEO Russian / SL-16 Upper Stage Belt (alt 800-900 km, inc ~71-74 deg)
        - LEO High-inclination Polar Belt (alt 600-1000 km, inc ~82-86 deg)
        - Mega-Constellation Shells (alt 550 km, inc ~53 deg)
        - MEO Navigation Belt (alt 20000 km, inc ~55-64 deg)
        - GEO Graveyard Belt (alt 35900-36200 km, inc ~0-5 deg)
        """
        np.random.seed(base_seed)
        epoch_now = datetime.now(timezone.utc)

        start_id = 50000

        # Cluster distributions: (prob, alt_min, alt_max, inc_mean, inc_std, primary_type)
        clusters = [
            (0.35, 750.0, 950.0, 98.2, 1.5, ObjectType.FRAGMENTATION_DEBRIS),  # Sun-sync SSO debris
            (0.25, 780.0, 880.0, 71.5, 2.0, ObjectType.ROCKET_BODY),            # SL-16 / Cosmos belt
            (0.15, 600.0, 1000.0, 82.5, 3.0, ObjectType.PAYLOAD),              # Polar payloads
            (0.10, 520.0, 580.0, 53.0, 1.0, ObjectType.FRAGMENTATION_DEBRIS),  # LEO Mega-constellation
            (0.08, 19000.0, 23000.0, 56.0, 5.0, ObjectType.ROCKET_BODY),        # MEO Navigation
            (0.07, 35900.0, 36200.0, 2.0, 3.0, ObjectType.PAYLOAD)             # GEO Graveyard
        ]

        cluster_probs = [c[0] for c in clusters]

        for i in range(count):
            norad_id = start_id + i
            # Choose cluster
            cluster_idx = np.random.choice(len(clusters), p=cluster_probs)
            _, alt_min, alt_max, inc_mean, inc_std, primary_type = clusters[cluster_idx]

            alt_km = float(np.random.uniform(alt_min, alt_max))
            ecc = float(np.random.exponential(0.005))
            ecc = float(np.clip(ecc, 0.00005, 0.05))

            inc_deg = float(np.random.normal(inc_mean, inc_std))
            inc_deg = float(np.clip(inc_deg, 0.0, 180.0))

            raan_deg = float(np.random.uniform(0.0, 360.0))
            arg_p_deg = float(np.random.uniform(0.0, 360.0))
            nu_deg = float(np.random.uniform(0.0, 360.0))

            sma_m = R_EARTH + alt_km * 1000.0
            inc_rad = math.radians(inc_deg)
            raan_rad = math.radians(raan_deg)
            arg_p_rad = math.radians(arg_p_deg)
            nu_rad = math.radians(nu_deg)

            kepler = KeplerianElements(
                semi_major_axis=sma_m,
                eccentricity=ecc,
                inclination=inc_rad,
                raan=raan_rad,
                arg_of_perigee=arg_p_rad,
                true_anomaly=nu_rad
            )

            b_star = float(np.random.exponential(0.00005))

            # Determine type
            type_roll = np.random.rand()
            if type_roll < 0.6:
                obj_type = primary_type
            elif type_roll < 0.8:
                obj_type = ObjectType.FRAGMENTATION_DEBRIS
            elif type_roll < 0.95:
                obj_type = ObjectType.ROCKET_BODY
            else:
                obj_type = ObjectType.PAYLOAD

            dc, area, mass, rcs, b_coeff, materials = estimate_physical_properties(
                object_type=obj_type,
                b_star=b_star,
                seed=norad_id
            )

            # Name prefix
            if obj_type == ObjectType.ROCKET_BODY:
                name = f"SL-STAGE R/B #{norad_id}"
            elif obj_type == ObjectType.FRAGMENTATION_DEBRIS:
                name = f"DEB #{norad_id} (FRAG)"
            elif obj_type == ObjectType.PAYLOAD:
                name = f"DEFUNCT-SAT #{norad_id}"
            else:
                name = f"MISSION-DEB #{norad_id}"

            intl_desig = f"{2000 + (norad_id % 24)}-{norad_id % 90:02d}A"

            debris = DebrisObject(
                norad_id=norad_id,
                name=name,
                intl_designator=intl_desig,
                epoch=epoch_now,
                keplerian=kepler,
                b_star=b_star,
                mean_motion_rev_day=kepler.mean_motion_rev_per_day,
                object_type=obj_type,
                characteristic_size_m=dc,
                cross_sectional_area_m2=area,
                estimated_mass_kg=mass,
                radar_cross_section_m2=rcs,
                drag_coefficient_cd=2.2,
                ballistic_coefficient_kg_m2=b_coeff,
                material_breakdown=materials,
                is_statistically_estimated=True
            )

            self.objects[norad_id] = debris

    def get_object(self, norad_id: int) -> Optional[DebrisObject]:
        """Retrieve object by NORAD ID."""
        return self.objects.get(norad_id)

    def list_objects(
        self,
        regime: Optional[OrbitRegime] = None,
        obj_type: Optional[ObjectType] = None,
        min_mass_kg: Optional[float] = None,
        search_query: Optional[str] = None,
        limit: int = 1000
    ) -> List[DebrisObject]:
        """Query and filter catalog objects."""
        results = []
        for obj in self.objects.values():
            if regime and obj.orbit_regime != regime:
                continue
            if obj_type and obj.object_type != obj_type:
                continue
            if min_mass_kg and obj.estimated_mass_kg < min_mass_kg:
                continue
            if search_query:
                q = search_query.lower()
                if q not in obj.name.lower() and str(obj.norad_id) != q and q not in obj.intl_designator.lower():
                    continue
            results.append(obj)
            if len(results) >= limit:
                break
        return results

    @property
    def total_count(self) -> int:
        return len(self.objects)
