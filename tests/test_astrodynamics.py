"""
Unit tests for Astrodynamics Core: Coordinates, Keplerian elements, and Lambert solver.
"""

import math
import numpy as np
import pytest

from aetheris.core.constants import MU_EARTH, R_EARTH, J2, G0
from aetheris.core.coordinates import (
    ecef_to_geodetic,
    geodetic_to_ecef,
    datetime_to_julian_date,
    julian_date_to_gmst,
    eci_to_ecef,
    ecef_to_eci
)
from aetheris.core.orbital_elements import (
    KeplerianElements,
    cartesian_to_keplerian,
    keplerian_to_cartesian,
    solve_kepler_eccentric_anomaly,
    eccentric_anomaly_to_true_anomaly,
    true_anomaly_to_mean_anomaly
)
from aetheris.core.lambert import solve_lambert


def test_geodetic_ecef_roundtrip():
    """Verify Bowring algorithm accuracy in geodetic <-> ECEF transformation."""
    lat_orig = 37.7749  # San Francisco
    lon_orig = -122.4194
    alt_orig = 500.0  # 500 meters

    r_ecef = geodetic_to_ecef(lat_orig, lon_orig, alt_orig)
    lat_calc, lon_calc, alt_calc = ecef_to_geodetic(r_ecef)

    assert abs(lat_calc - lat_orig) < 1e-6
    assert abs(lon_calc - lon_orig) < 1e-6
    assert abs(alt_calc - alt_orig) < 0.01  # sub-centimeter accuracy


def test_eci_ecef_roundtrip():
    """Verify ECI <-> ECEF coordinate transformation with GMST."""
    r_eci = np.array([5000000.0, 3000000.0, 4000000.0], dtype=np.float64)
    v_eci = np.array([-2000.0, 6500.0, 1500.0], dtype=np.float64)
    gmst = 1.234567

    r_ecef, v_ecef = eci_to_ecef(r_eci, v_eci, gmst)
    r_eci_back, v_eci_back = ecef_to_eci(r_ecef, v_ecef, gmst)

    np.testing.assert_allclose(r_eci_back, r_eci, rtol=1e-10)
    np.testing.assert_allclose(v_eci_back, v_eci, rtol=1e-10)


def test_cartesian_keplerian_roundtrip():
    """Verify Keplerian <-> Cartesian state vector transformation consistency."""
    # Test orbit: a = 7000 km, e = 0.02, i = 51.6 deg (ISS-like)
    sma = 7000000.0
    ecc = 0.02
    inc = math.radians(51.6)
    raan = math.radians(45.0)
    arg_p = math.radians(30.0)
    nu = math.radians(60.0)

    kepler_in = KeplerianElements(
        semi_major_axis=sma,
        eccentricity=ecc,
        inclination=inc,
        raan=raan,
        arg_of_perigee=arg_p,
        true_anomaly=nu
    )

    r_vec, v_vec = keplerian_to_cartesian(kepler_in)
    kepler_out = cartesian_to_keplerian(r_vec, v_vec)

    assert abs(kepler_out.semi_major_axis - sma) < 0.01
    assert abs(kepler_out.eccentricity - ecc) < 1e-6
    assert abs(kepler_out.inclination - inc) < 1e-6
    assert abs(kepler_out.raan - raan) < 1e-6
    assert abs(kepler_out.arg_of_perigee - arg_p) < 1e-6
    assert abs(kepler_out.true_anomaly - nu) < 1e-6


def test_kepler_equation_solver():
    """Verify Newton-Raphson Kepler equation solver."""
    m_val = math.radians(45.0)
    ecc = 0.25

    e_anom = solve_kepler_eccentric_anomaly(m_val, ecc)
    # Check Kepler's equation M = E - e*sin(E)
    m_check = e_anom - ecc * math.sin(e_anom)

    assert abs(m_check - m_val) < 1e-10


def test_lambert_solver_transfer():
    """Verify Universal Variable Lambert solver on a standard 180-deg transfer."""
    # Circular LEO orbit to LEO orbit
    r1 = np.array([7000000.0, 0.0, 0.0], dtype=np.float64)
    r2 = np.array([0.0, 7500000.0, 0.0], dtype=np.float64)
    tof = 1800.0  # 30 minutes

    sol = solve_lambert(r1, r2, tof)

    assert sol.converged
    assert len(sol.v1) == 3
    assert len(sol.v2) == 3
    # Check that initial velocity has appropriate speed ~ 7-8 km/s
    speed1 = np.linalg.norm(sol.v1)
    assert 5000.0 < speed1 < 10000.0
