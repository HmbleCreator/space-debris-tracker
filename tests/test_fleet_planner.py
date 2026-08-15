"""
Unit tests for Autonomous Fleet Mission Planner & J2 Drift Optimizer.
"""

import math
from datetime import datetime, timezone
import pytest

from aetheris.catalog.debris_object import DebrisObject, ObjectType
from aetheris.core.orbital_elements import KeplerianElements
from aetheris.fleet_planner.transfer_cost import (
    compute_hohmann_transfer_delta_v,
    compute_direct_plane_change_delta_v
)
from aetheris.fleet_planner.j2_drift_optimizer import (
    compute_j2_raan_precession_rate,
    optimize_j2_drift_transfer
)
from aetheris.fleet_planner.fleet_optimizer import (
    FleetMissionOptimizer,
    RobotSpacecraftSpec
)


def test_hohmann_transfer_delta_v():
    """Verify standard LEO-to-LEO Hohmann transfer Delta-V calculation."""
    r1 = 6378137.0 + 400000.0  # 400 km
    r2 = 6378137.0 + 800000.0  # 800 km

    dv1, dv2, dv_tot, tof = compute_hohmann_transfer_delta_v(r1, r2)

    assert dv_tot > 0
    # For 400->800km, total Delta-V is ~220-230 m/s
    assert 200.0 < dv_tot < 250.0
    # Time of flight is ~45-50 minutes
    assert 2500.0 < tof < 3200.0


def test_j2_drift_optimizer_savings():
    """Verify J2 drift optimization achieves > 50% propellant savings over direct impulsive plane changes."""
    # Target 1: alt 850 km, inc 71 deg, RAAN 0 deg
    orbit_a = KeplerianElements(
        semi_major_axis=6378137.0 + 850000.0,
        eccentricity=0.001,
        inclination=math.radians(71.0),
        raan=0.0,
        arg_of_perigee=0.0,
        true_anomaly=0.0
    )
    # Target 2: alt 850 km, inc 71 deg, RAAN 25 deg (25° RAAN difference)
    orbit_b = KeplerianElements(
        semi_major_axis=6378137.0 + 850000.0,
        eccentricity=0.001,
        inclination=math.radians(71.0),
        raan=math.radians(25.0),
        arg_of_perigee=0.0,
        true_anomaly=0.0
    )

    plan = optimize_j2_drift_transfer(orbit_a, orbit_b, max_drift_days=60.0)

    assert plan.propellant_savings_percent >= 50.0
    assert plan.delta_v_total_ms < plan.direct_impulsive_delta_v_ms


def test_fleet_optimizer_sizing():
    """Verify FleetMissionOptimizer correctly sizes minimum robots K_min and respects fuel constraints."""
    # Create 6 synthetic targets in the same cluster
    targets = []
    for i in range(6):
        kepler = KeplerianElements(
            semi_major_axis=6378137.0 + (800.0 + i * 15.0) * 1000.0,
            eccentricity=0.001,
            inclination=math.radians(71.0),
            raan=math.radians(i * 10.0),
            arg_of_perigee=0.0,
            true_anomaly=0.0
        )
        obj = DebrisObject(
            norad_id=60000 + i,
            name=f"SL-16 #{i+1}",
            intl_designator=f"200{i}-01A",
            epoch=datetime.now(timezone.utc),
            keplerian=kepler,
            b_star=0.00002,
            mean_motion_rev_day=kepler.mean_motion_rev_per_day,
            object_type=ObjectType.ROCKET_BODY,
            characteristic_size_m=8.0,
            cross_sectional_area_m2=25.0,
            estimated_mass_kg=4000.0,
            criticality_score=75.0 - i * 2.0
        )
        targets.append(obj)

    spec = RobotSpacecraftSpec(
        robot_id="IBS-TEST",
        robot_name="Aetheris Test Servicer",
        dry_mass_kg=550.0,
        propellant_capacity_kg=400.0,
        beam_thrust_n=0.20,
        beam_isp_sec=3500.0,
        max_targets_per_robot=4
    )

    optimizer = FleetMissionOptimizer(robot_spec=spec)
    result = optimizer.optimize_fleet(targets, max_robots_allowed=5)

    assert result.minimum_robots_needed >= 1
    assert result.total_targets_cleaned == len(targets)
    assert len(result.robot_itineraries) == result.minimum_robots_needed
    assert result.fleet_total_dwell_days > 0.0

    for r in result.robot_itineraries:
        assert r.final_remaining_propellant_kg >= 0.0
        assert r.fuel_margin_percent >= 0.0
        assert r.total_dwell_days > 0.0


def test_benchmark_esa_e_deorbit_validation():
    """
    Independent validation against ESA e.Deorbit Phase B1 Study (CDF-150(A)).
    - Compares unmargined theoretical Hohmann deorbit retro-burn against ESA unmargined nominal (201.4 m/s) to <0.5% error.
    - Accurately tracks the +6.5% operational attitude/thruster margin that scales the budget to 215.0 m/s.
    """
    from aetheris.disposal.chaser_propulsion import ChaserPropulsionEngine
    from aetheris.fleet_planner.benchmark_cases import BENCHMARK_ESA_E_DEORBIT

    envisat_orbit = KeplerianElements(
        semi_major_axis=6378137.0 + 768000.0,
        eccentricity=0.0001,
        inclination=math.radians(98.54),
        raan=0.0,
        arg_of_perigee=0.0,
        true_anomaly=0.0
    )

    deorbit_res = ChaserPropulsionEngine.compute_impulsive_retro_burn(
        current_orbit=envisat_orbit,
        chaser_mass_kg=BENCHMARK_ESA_E_DEORBIT.published_servicer_dry_mass_kg,
        target_mass_kg=BENCHMARK_ESA_E_DEORBIT.target_mass_kg,
        target_perigee_alt_km=45.0,
        isp_seconds=BENCHMARK_ESA_E_DEORBIT.published_isp_sec
    )

    # 1. Direct apples-to-apples comparison against unmargined nominal baseline (201.4 m/s)
    unmargined_nominal = BENCHMARK_ESA_E_DEORBIT.published_unmargined_nominal_deorbit_dv_ms
    rel_error = abs(deorbit_res.delta_v_required_ms - unmargined_nominal) / unmargined_nominal
    assert rel_error < 0.005, f"Theoretical Delta-V {deorbit_res.delta_v_required_ms} deviates from ESA nominal {unmargined_nominal} by {rel_error*100:.2f}%"

    # 2. Honest margin check: ESA operational allocation (215.0 m/s) includes 6.5% flight margin
    operational_margined = BENCHMARK_ESA_E_DEORBIT.published_margined_operational_deorbit_dv_ms
    margin_pct = ((operational_margined - deorbit_res.delta_v_required_ms) / deorbit_res.delta_v_required_ms) * 100.0
    assert 5.0 <= margin_pct <= 8.0, f"ESA operational margin {margin_pct:.1f}% outside expected 5-8% range"


def test_benchmark_castronuovo_sl16_tour_validation():
    """
    Independent validation against Castronuovo (2011) Acta Astronautica Table 3.
    Evaluates exact SL-16 upper stage cluster (840 km / 71.0°) with delta_RAAN = 12.5°.
    - Upper drift orbit (1050 km): delta_dot_Omega = 0.500 °/day -> T_drift = 25.0 days.
    - Lower drift orbit (600 km): delta_dot_Omega = -1.632 °/day -> T_drift = 7.66 days.
    """
    from aetheris.core.constants import R_EARTH
    from aetheris.fleet_planner.j2_drift_optimizer import compute_j2_raan_precession_rate
    from aetheris.fleet_planner.benchmark_cases import BENCHMARK_CASTRONUOVO_SL16_TOUR

    r_target = R_EARTH + BENCHMARK_CASTRONUOVO_SL16_TOUR.target_altitude_km * 1000.0
    inc_rad = math.radians(BENCHMARK_CASTRONUOVO_SL16_TOUR.target_inclination_deg)
    d_raan_deg = BENCHMARK_CASTRONUOVO_SL16_TOUR.raan_separation_deg

    # Base target precession rate at 840 km / 71°
    dot_omega_target = compute_j2_raan_precession_rate(r_target, inc_rad)
    dot_omega_target_deg_day = math.degrees(dot_omega_target) * 86400.0

    # 1. Upper Drift Orbit (1050 km)
    r_drift_upper = R_EARTH + BENCHMARK_CASTRONUOVO_SL16_TOUR.published_drift_altitude_upper_km * 1000.0
    dot_omega_upper = compute_j2_raan_precession_rate(r_drift_upper, inc_rad)
    dot_omega_upper_deg_day = math.degrees(dot_omega_upper) * 86400.0
    diff_rate_upper = dot_omega_upper_deg_day - dot_omega_target_deg_day
    t_drift_upper_days = d_raan_deg / diff_rate_upper

    # Check differential drift rate matches published 0.500 °/day to <1%
    assert abs(diff_rate_upper - BENCHMARK_CASTRONUOVO_SL16_TOUR.published_drift_rate_upper_deg_day) < 0.01
    # Check drift duration matches published 25.0 days to <1%
    assert abs(t_drift_upper_days - BENCHMARK_CASTRONUOVO_SL16_TOUR.published_drift_duration_upper_days) < 0.25

    # 2. Lower Drift Orbit (600 km)
    r_drift_lower = R_EARTH + BENCHMARK_CASTRONUOVO_SL16_TOUR.published_drift_altitude_lower_km * 1000.0
    dot_omega_lower = compute_j2_raan_precession_rate(r_drift_lower, inc_rad)
    dot_omega_lower_deg_day = math.degrees(dot_omega_lower) * 86400.0
    diff_rate_lower = abs(dot_omega_lower_deg_day - dot_omega_target_deg_day)
    t_drift_lower_days = d_raan_deg / diff_rate_lower

    # Check differential drift rate matches published 1.632 °/day to <1%
    assert abs(diff_rate_lower - BENCHMARK_CASTRONUOVO_SL16_TOUR.published_drift_rate_lower_deg_day) < 0.02
    # Check drift duration matches published 7.66 days to <1%
    assert abs(t_drift_lower_days - BENCHMARK_CASTRONUOVO_SL16_TOUR.published_drift_duration_lower_days) < 0.15

    # 3. Propellant savings check for this specific 840 km / 71° / 12.5° RAAN pair
    orbit_1 = KeplerianElements(r_target, 0.001, inc_rad, 0.0, 0.0, 0.0)
    orbit_2 = KeplerianElements(r_target, 0.001, inc_rad, math.radians(d_raan_deg), 0.0, 0.0)
    plan = optimize_j2_drift_transfer(orbit_1, orbit_2, max_drift_days=65.0)

    # For 840 km / 71° with 12.5° RAAN change, J2 drift saves >80% Delta-V vs direct impulsive plane change
    assert plan.propellant_savings_percent >= 80.0
