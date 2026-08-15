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


def test_esa_e_deorbit_literature_comparison():
    """
    Comparison with ESA e.Deorbit Study (Biesbroek et al. 2013).
    - Computes theoretical two-body unmargined Hohmann retro-burn (201.45 m/s) from 768 km to 45 km perigee.
    - Compares with Biesbroek et al. (2013) published 8-tonne SSO servicer sizing (709-784 kg dry, 810-878 kg propellant).
    """
    from aetheris.disposal.chaser_propulsion import ChaserPropulsionEngine
    from aetheris.fleet_planner.benchmark_cases import LITERATURE_ESA_E_DEORBIT

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
        chaser_mass_kg=LITERATURE_ESA_E_DEORBIT.published_servicer_dry_mass_net_kg,
        target_mass_kg=LITERATURE_ESA_E_DEORBIT.target_mass_kg,
        target_perigee_alt_km=45.0,
        isp_seconds=320.0
    )

    # 1. Theoretical unmargined calculation
    theo_dv = deorbit_res.delta_v_required_ms
    assert abs(theo_dv - LITERATURE_ESA_E_DEORBIT.theoretical_unmargined_hohmann_dv_ms) < 0.5

    # 2. Check that propellant required for disposal alone is well within published total tank sizing (810-878 kg)
    assert deorbit_res.propellant_required_kg < LITERATURE_ESA_E_DEORBIT.published_servicer_propellant_net_kg
    assert deorbit_res.propellant_required_kg > 0


def test_castronuovo_literature_drift_window_consistency():
    """
    Consistency check against Castronuovo (2011) Acta Astronautica multi-target ADR analysis.
    Evaluates representative Russian SL-16 Upper Stage cluster (840 km / 71.0°, delta_RAAN = 12.5°).
    - Verifies that optimized J2 drift duration falls within Castronuovo's published
      20-65 day per-target operational transfer window.
    - Demonstrates 81.5% propellant savings for this specific orbit pair over direct impulsive plane change.
    """
    from aetheris.core.constants import R_EARTH
    from aetheris.fleet_planner.benchmark_cases import LITERATURE_CASTRONUOVO_ADR

    r_target = R_EARTH + LITERATURE_CASTRONUOVO_ADR.target_altitude_km * 1000.0
    inc_rad = math.radians(LITERATURE_CASTRONUOVO_ADR.target_inclination_deg)
    d_raan_deg = LITERATURE_CASTRONUOVO_ADR.raan_separation_deg

    orbit_1 = KeplerianElements(r_target, 0.001, inc_rad, 0.0, 0.0, 0.0)
    orbit_2 = KeplerianElements(r_target, 0.001, inc_rad, math.radians(d_raan_deg), 0.0, 0.0)
    plan = optimize_j2_drift_transfer(orbit_1, orbit_2, max_drift_days=65.0)

    # Verify drift duration is consistent with Castronuovo's multi-week window (20-65 days)
    w_min = LITERATURE_CASTRONUOVO_ADR.published_mission_transfer_window_days_min
    w_max = LITERATURE_CASTRONUOVO_ADR.published_mission_transfer_window_days_max
    assert w_min <= plan.drift_duration_days <= w_max, (
        f"Drift duration {plan.drift_duration_days:.1f} days outside literature window ({w_min}-{w_max} days)"
    )

    # Note case-specific propellant savings for this high-inclination pair
    assert plan.propellant_savings_percent >= 80.0
