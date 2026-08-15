"""
Unit tests for Risk, Criticality Index, and Kessler Cascade Simulator.
"""

import math
from datetime import datetime, timezone
import pytest

from aetheris.catalog.debris_object import DebrisObject, ObjectType
from aetheris.core.orbital_elements import KeplerianElements
from aetheris.risk.criticality import (
    compute_spatial_density_leo,
    estimate_fragmentation_yield,
    compute_debris_criticality
)
from aetheris.risk.kessler_simulator import KesslerCascadeSimulator


def test_spatial_density_distribution():
    """Verify spatial density peaks around historical congestion altitudes (780-850 km)."""
    dens_500 = compute_spatial_density_leo(500.0, 53.0)
    dens_800 = compute_spatial_density_leo(800.0, 71.0)
    dens_850 = compute_spatial_density_leo(850.0, 98.2)

    # 850 km SSO should have higher spatial density than 500 km
    assert dens_850 > dens_500
    assert dens_800 > dens_500


def test_fragmentation_yield():
    """Verify NASA Standard Breakup model fragment yield scaling with mass."""
    frags_10kg = estimate_fragmentation_yield(10.0)
    frags_1000kg = estimate_fragmentation_yield(1000.0)
    frags_9000kg = estimate_fragmentation_yield(9000.0)

    assert frags_10kg > 0
    assert frags_1000kg > frags_10kg
    assert frags_9000kg > frags_1000kg


def test_debris_criticality_calculation():
    """Verify high-mass upper stage in congested orbit receives high criticality score."""
    kepler = KeplerianElements(
        semi_major_axis=6378137.0 + 850000.0,
        eccentricity=0.001,
        inclination=math.radians(71.0),
        raan=0.0,
        arg_of_perigee=0.0,
        true_anomaly=0.0
    )
    sl16_obj = DebrisObject(
        norad_id=22285,
        name="SL-16 R/B",
        intl_designator="1992-076B",
        epoch=datetime.now(timezone.utc),
        keplerian=kepler,
        b_star=0.00002,
        mean_motion_rev_day=kepler.mean_motion_rev_per_day,
        object_type=ObjectType.ROCKET_BODY,
        characteristic_size_m=10.4,
        cross_sectional_area_m2=31.0,
        estimated_mass_kg=9000.0
    )

    score = compute_debris_criticality(sl16_obj, [sl16_obj])
    assert score >= 50.0, f"High-mass rocket body should have high criticality score, got {score}"


def test_kessler_simulator_adr_mitigation():
    """Verify Active Debris Removal produces positive risk reduction over 30 years."""
    sim = KesslerCascadeSimulator(
        initial_intact=5000,
        initial_large_debris=3000,
        initial_small_fragments=20000,
        annual_new_launches=800
    )
    result_adr = sim.simulate_scenario(adr_removal_rate_per_year=10, sim_years=30)
    result_baseline = sim.simulate_scenario(adr_removal_rate_per_year=0, sim_years=30)

    final_adr_pop = result_adr.total_population_trajectory[-1]
    final_base_pop = result_baseline.total_population_trajectory[-1]

    assert final_adr_pop < final_base_pop
    assert result_adr.risk_reduction_percent > 0.0
