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

    # At 20m standoff distance
    r_beam = engine.compute_beam_footprint_radius(standoff_distance_m=20.0)
    # Target with 15 m^2 cross section -> s = 4.37 m -> d_max = 10.28 m
    eta_20m = engine.compute_flux_interception_efficiency(
        standoff_distance_m=20.0,
        target_cross_section_m2=15.0
    )
    eta_5m = engine.compute_flux_interception_efficiency(
        standoff_distance_m=5.0,
        target_cross_section_m2=15.0
    )

    assert 3.0 < r_beam < 6.0  # r_beam ~ 20 * tan(12°) ~ 4.25 m
    assert 0.20 < eta_20m < 0.35 # (10.28 / 20)^2 ~ 26.4%
    assert eta_5m == 1.0         # 100% inside d_max


def test_benchmark_bombardelli_pelaez_ibs_validation():
    """
    Independent validation against Bombardelli & Peláez (2011) Section V / Figure 2 published worked example.
    Deorbit of 5-ton (5,000 kg) debris from 1000 km to 300 km circular orbit using a 100 mN beam with 70% effective force (70 mN).
    - Verifies continuous tangential Delta-V = 375.62 m/s.
    - Verifies transfer duration T = 310.5 days (< 1 year), matching published Figure 2.
    - Verifies secondary thruster force F_p2 = 104.2 mN from Eq. 5 (F_p2 = F_p1 * (1 + eta_t * m_IBS / m_d)).
    """
    from aetheris.core.constants import MU_EARTH, R_EARTH
    from aetheris.fleet_planner.benchmark_cases import BENCHMARK_BOMBARDELLI_PELEAZ_IBS

    bm = BENCHMARK_BOMBARDELLI_PELEAZ_IBS

    # 1. Theoretical circular velocity Delta-V from 1000 km to 300 km
    r1 = R_EARTH + bm.initial_altitude_km * 1000.0
    r2 = R_EARTH + bm.final_altitude_km * 1000.0
    v1 = math.sqrt(MU_EARTH / r1)
    v2 = math.sqrt(MU_EARTH / r2)
    delta_v_calc = abs(v2 - v1)

    assert abs(delta_v_calc - bm.published_transfer_delta_v_ms) < 0.1

    # 2. Transfer duration under 70 mN effective thrust
    f_target_n = bm.effective_target_thrust_mn / 1000.0
    t_transfer_sec = (bm.target_mass_kg * delta_v_calc) / f_target_n
    t_transfer_days = t_transfer_sec / 86400.0

    assert abs(t_transfer_days - bm.published_transfer_duration_days) < 0.5
    assert t_transfer_days < 365.25  # Published claim: deorbits in under 1 year

    # 3. Secondary thruster equilibrium force from Eq. 5
    engine = IonBeamShepherdEngine(
        beam_thrust_n=bm.beam_thrust_mn / 1000.0,
        nominal_chaser_mass_kg=bm.shepherd_mass_kg
    )
    eta_t = bm.effective_target_thrust_mn / bm.beam_thrust_mn  # 0.70
    f_p2_n = engine.compute_secondary_thruster_thrust(
        primary_thrust_n=bm.beam_thrust_mn / 1000.0,
        interception_efficiency=eta_t,
        chaser_mass_kg=bm.shepherd_mass_kg,
        target_mass_kg=bm.target_mass_kg
    )
    f_p2_mn = f_p2_n * 1000.0
    assert abs(f_p2_mn - bm.published_secondary_thruster_mn) < 0.1


def test_ibs_secondary_thruster_formation_acceleration_equilibrium():
    """
    Physics Verification of Bombardelli & Peláez (2011) Eq. 5 formation acceleration matching:
    a_IBS = (F_p2 - F_p1) / m_IBS == F_target / m_d == a_target.
    Tests significant non-negligible shepherd mass (e.g. m_IBS = 500 kg next to m_d = 1,000 kg).
    """
    engine = IonBeamShepherdEngine(
        beam_thrust_n=0.20,              # 200 mN
        nominal_chaser_mass_kg=500.0
    )

    kepler = KeplerianElements(
        semi_major_axis=6378137.0 + 800000.0,
        eccentricity=0.001,
        inclination=math.radians(71.0),
        raan=0.0,
        arg_of_perigee=0.0,
        true_anomaly=0.0
    )

    # 500 kg shepherd next to a 1,000 kg target (m_IBS / m_d = 0.50) at 5m standoff (d <= d_max = 7.06m)
    res = engine.compute_standoff_deorbit(
        target_name="Cosmos-3M Payload",
        target_mass_kg=1000.0,
        target_characteristic_size_m=3.0,
        current_orbit=kepler,
        standoff_distance_m=5.0,
        chaser_mass_kg=500.0,
        target_perigee_alt_km=40.0
    )

    # For m_IBS = 500 kg and m_d = 1000 kg with eta = 1.0:
    # F_p2 = 200 mN * (1 + 1.0 * 500/1000) = 300 mN!
    assert res.secondary_formation_thruster_mn > res.primary_beam_thrust_mn
    assert abs(res.secondary_formation_thruster_mn - 300.0) < 1.0

    # Verify that shepherd acceleration exactly matches target acceleration (0 formation drift)
    assert abs(res.shepherd_formation_acceleration_ms2 - res.target_deorbit_acceleration_ms2) < 1e-9
    assert res.shepherd_formation_acceleration_ms2 > 0.0


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
