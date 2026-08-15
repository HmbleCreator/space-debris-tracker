"""
Unit tests for Autonomous Disposal, Aerothermal Demise, and Point Nemo Targeting.
"""

import math
from datetime import datetime, timezone
import pytest

from aetheris.catalog.debris_object import DebrisObject, ObjectType
from aetheris.core.constants import POINT_NEMO_LAT_DEG, POINT_NEMO_LON_DEG, SPOUA_CORRIDOR_POLYGON
from aetheris.core.orbital_elements import KeplerianElements
from aetheris.disposal.aerothermal_demise import AerothermalDemiseSimulator
from aetheris.disposal.chaser_propulsion import ChaserPropulsionEngine
from aetheris.disposal.point_nemo_targeter import PointNemoTargeter, point_in_polygon


def test_impulsive_retro_burn_calculation():
    """Verify impulsive deorbit Delta-V brings perigee down to 40 km."""
    kepler = KeplerianElements(
        semi_major_axis=6378137.0 + 750000.0,
        eccentricity=0.001,
        inclination=math.radians(98.0),
        raan=0.0,
        arg_of_perigee=0.0,
        true_anomaly=0.0
    )

    res = ChaserPropulsionEngine.compute_impulsive_retro_burn(
        current_orbit=kepler,
        chaser_mass_kg=600.0,
        target_mass_kg=2000.0,
        target_perigee_alt_km=40.0
    )

    assert res.delta_v_required_ms > 0
    # For 750 km circular orbit, deorbit Delta-V is ~200-220 m/s
    assert 180.0 < res.delta_v_required_ms < 240.0
    assert res.propellant_mass_kg > 0
    assert res.entry_flight_path_angle_deg < 0  # negative flight path angle into atmosphere


def test_aerothermal_demise_small_aluminum_frag():
    """Verify small aluminum fragment fully demises in atmosphere (Safe High-Altitude Demise)."""
    kepler = KeplerianElements(
        semi_major_axis=6378137.0 + 500000.0,
        eccentricity=0.001,
        inclination=math.radians(53.0),
        raan=0.0,
        arg_of_perigee=0.0,
        true_anomaly=0.0
    )
    small_frag = DebrisObject(
        norad_id=99001,
        name="SMALL AL FRAGMENT",
        intl_designator="2020-01A",
        epoch=datetime.now(timezone.utc),
        keplerian=kepler,
        b_star=0.0001,
        mean_motion_rev_day=kepler.mean_motion_rev_per_day,
        object_type=ObjectType.FRAGMENTATION_DEBRIS,
        characteristic_size_m=0.15,
        cross_sectional_area_m2=0.04,
        estimated_mass_kg=0.5,
        drag_coefficient_cd=2.2,
        material_breakdown={"ALUMINUM_6061": 1.0}
    )

    sim = AerothermalDemiseSimulator()
    res = sim.simulate_entry_demise(small_frag)

    assert res.is_safe_demise is True
    assert res.disposal_recommendation == "SAFE_ATMOSPHERIC_INCINERATION"
    assert res.mass_demised_fraction_percent >= 80.0


def test_aerothermal_demise_heavy_titanium_tank():
    """Verify large rocket body with Titanium tanks mandates Point Nemo controlled targeting."""
    kepler = KeplerianElements(
        semi_major_axis=6378137.0 + 850000.0,
        eccentricity=0.001,
        inclination=math.radians(71.0),
        raan=0.0,
        arg_of_perigee=0.0,
        true_anomaly=0.0
    )
    sl16 = DebrisObject(
        norad_id=22285,
        name="SL-16 ROCKET BODY",
        intl_designator="1992-076B",
        epoch=datetime.now(timezone.utc),
        keplerian=kepler,
        b_star=0.00002,
        mean_motion_rev_day=kepler.mean_motion_rev_per_day,
        object_type=ObjectType.ROCKET_BODY,
        characteristic_size_m=10.4,
        cross_sectional_area_m2=31.0,
        estimated_mass_kg=9000.0,
        material_breakdown={
            "ALUMINUM_6061": 0.65,
            "TITANIUM_TI6AL4V": 0.20,
            "STAINLESS_STEEL_304": 0.15
        }
    )

    sim = AerothermalDemiseSimulator()
    res = sim.simulate_entry_demise(sl16)

    assert res.is_safe_demise is False
    assert res.disposal_recommendation == "MANDATORY_POINT_NEMO_TARGETING"
    assert res.total_surviving_mass_kg > 500.0


def test_point_nemo_corridor_containment():
    """Verify Point Nemo coordinates are inside the SPOUA safety corridor polygon."""
    inside = point_in_polygon(POINT_NEMO_LAT_DEG, POINT_NEMO_LON_DEG, SPOUA_CORRIDOR_POLYGON)
    assert inside is True
