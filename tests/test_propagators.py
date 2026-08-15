"""
Unit tests for Fast Analytical SGP4/J2 Propagator and High-Precision Numerical Propagator (HPOP).
"""

import math
from datetime import datetime, timezone
import numpy as np
import pytest

from aetheris.catalog.debris_object import DebrisObject, ObjectType
from aetheris.core.constants import MU_EARTH, R_EARTH, J2
from aetheris.core.orbital_elements import KeplerianElements, keplerian_to_cartesian
from aetheris.dynamics.gravity_harmonics import compute_geopotential_acceleration
from aetheris.dynamics.atmospheric_models import get_atmospheric_density, compute_drag_acceleration
from aetheris.dynamics.numerical_propagator import NumericalPropagator, HPOPConfig
from aetheris.dynamics.sgp4_propagator import FastPropagator


def test_j2_geopotential_acceleration():
    """Verify J2 geopotential perturbation matches analytical formula."""
    r_equatorial = np.array([R_EARTH + 500000.0, 0.0, 0.0], dtype=np.float64)
    a_grav = compute_geopotential_acceleration(r_equatorial, max_zonal_degree=2)

    r_mag = np.linalg.norm(r_equatorial)
    # At equator (z=0), a_x = -mu/r^2 * (1 + 1.5 * J2 * (R_E/r)^2)
    expected_ax = -(MU_EARTH / (r_mag ** 2)) * (1.0 + 1.5 * J2 * ((R_EARTH / r_mag) ** 2))

    assert abs(a_grav[0] - expected_ax) / abs(expected_ax) < 1e-5
    assert abs(a_grav[1]) < 1e-10
    assert abs(a_grav[2]) < 1e-10


def test_fast_propagator_j2_raan_drift():
    """Verify analytical propagator matches theoretical J2 RAAN secular precession."""
    # Sun-synchronous orbit: altitude 800 km, inc = 98.6 deg
    alt_m = 800000.0
    sma = R_EARTH + alt_m
    inc = math.radians(98.6)
    ecc = 0.001
    p = sma * (1.0 - ecc ** 2)
    n = math.sqrt(MU_EARTH / (sma ** 3))

    expected_d_raan_dt = -1.5 * J2 * ((R_EARTH / p) ** 2) * n * math.cos(inc)

    kepler = KeplerianElements(
        semi_major_axis=sma,
        eccentricity=ecc,
        inclination=inc,
        raan=0.0,
        arg_of_perigee=0.0,
        true_anomaly=0.0
    )

    dt_sec = 86400.0  # 1 day
    _, _, _, updated_kepler = FastPropagator.propagate_keplerian_j2_secular(kepler, dt_sec)

    expected_raan_1day = (expected_d_raan_dt * dt_sec) % (2.0 * math.pi)
    assert abs(updated_kepler.raan - expected_raan_1day) < 1e-5


def test_numerical_hpop_energy_conservation_two_body():
    """Verify numerical Cowell RK45 propagator conserves specific orbital energy under two-body dynamics."""
    config = HPOPConfig(
        max_zonal_harmonics=0,  # Pure two-body
        include_drag=False,
        include_srp=False,
        include_third_body=False
    )
    propagator = NumericalPropagator(config)

    # Initial circular orbit at 800 km
    sma = R_EARTH + 800000.0
    kepler = KeplerianElements(
        semi_major_axis=sma,
        eccentricity=0.0,
        inclination=math.radians(45.0),
        raan=0.0,
        arg_of_perigee=0.0,
        true_anomaly=0.0
    )
    r0, v0 = keplerian_to_cartesian(kepler)

    start_epoch = datetime.now(timezone.utc)
    trajectory = propagator.propagate(
        r0_eci=r0,
        v0_eci=v0,
        start_epoch=start_epoch,
        duration_seconds=6000.0,  # ~1 full orbit
        step_seconds=30.0
    )

    init_energy = trajectory[0].specific_energy_j_kg
    final_energy = trajectory[-1].specific_energy_j_kg

    relative_energy_error = abs(final_energy - init_energy) / abs(init_energy)
    assert relative_energy_error < 1e-6, f"Energy error too large: {relative_energy_error}"


def test_space_weather_provider_scenarios():
    """Verify SpaceWeatherProvider returns valid F10.7 and Ap for standard NOAA space weather scenarios."""
    from aetheris.dynamics.space_weather import SpaceWeatherProvider, SpaceWeatherScenario

    provider = SpaceWeatherProvider(use_live_feed=False)

    quiet = provider.get_indices(scenario=SpaceWeatherScenario.QUIET_SUN)
    assert quiet.f107_flux == 70.0
    assert quiet.ap_geomagnetic_index == 4.0

    storm = provider.get_indices(scenario=SpaceWeatherScenario.GEOMAGNETIC_STORM)
    assert storm.f107_flux == 250.0
    assert storm.ap_geomagnetic_index == 140.0


def test_space_weather_historical_lookup():
    """Verify SpaceWeatherProvider accurately returns historical Solar Cycle 24/25 indices."""
    from aetheris.dynamics.space_weather import SpaceWeatherProvider

    provider = SpaceWeatherProvider(use_live_feed=False)

    # May 2024 Geomagnetic Storm peak
    dt_may2024 = datetime(2024, 5, 10, tzinfo=timezone.utc)
    indices = provider.get_indices(target_date=dt_may2024)

    assert indices.f107_flux == 210.0
    assert indices.ap_geomagnetic_index == 28.0
    assert "HISTORICAL_SOLAR_CYCLE_TABLE_2024_05" in indices.source
