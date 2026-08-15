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
from aetheris.disposal.ion_beam_shepherd import IonBeamShepherdEngine
from aetheris.disposal.point_nemo_targeter import PointNemoTargeter, point_in_polygon


def test_ion_beam_shepherd_divergence_efficiency():
    """Verify Ion Beam Shepherd plume divergence footprint and flux interception efficiency."""
    engine = IonBeamShepherdEngine(
        beam_thrust_n=0.20,
        beam_isp_sec=3500.0,
        beam_divergence_half_angle_deg=12.0
    )

    # At 20m standoff distance for a 15 m^2 cross section target
    r_beam = engine.compute_beam_footprint_radius(standoff_distance_m=20.0)
    eta = engine.compute_flux_interception_efficiency(
        standoff_distance_m=20.0,
        target_cross_section_m2=15.0
    )

    assert 3.0 < r_beam < 6.0  # r_beam ~ 0.15 + 20 * tan(12°) ~ 4.40 m
    assert 0.60 < eta < 0.95   # >60% flux intercepted


def test_ion_beam_shepherd_recoil_and_dwell_budget():
    """Verify IBS dual-thruster recoil cancellation and dwell time integration."""
    engine = IonBeamShepherdEngine(
        beam_thrust_n=0.20,
        beam_isp_sec=3500.0,
        station_keeping_isp_sec=3500.0
    )

    kepler = KeplerianElements(
        semi_major_axis=6378137.0 + 800000.0,
        eccentricity=0.001,
        inclination=math.radians(71.0),
        raan=0.0,
        arg_of_perigee=0.0,
        true_anomaly=0.0
    )

    res = engine.compute_standoff_deorbit(
        target_name="SL-16 R/B",
        target_mass_kg=4000.0,
        target_cross_section_m2=25.0,
        current_orbit=kepler,
        standoff_distance_m=20.0,
        target_perigee_alt_km=40.0
    )

    # 1. Verification of recoil cancellation
    assert res.station_keeping_compensation_force_mn == res.chaser_recoil_force_mn == 200.0
    assert res.net_target_push_force_mn > 0

    # 2. Verification of realistic dwell duration (30-70 days for 4000 kg R/B at 200 mN)
    assert 30.0 <= res.deorbit_dwell_duration_days <= 75.0

    # 3. Propellant efficiency of high-Isp electric propulsion
    assert res.daily_propellant_consumption_kg_day < 1.5
    assert res.total_chaser_propellant_used_kg > 0
    assert res.tumbling_immunity_flag is True


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
