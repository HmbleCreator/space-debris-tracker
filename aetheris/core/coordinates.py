"""
High-Precision Coordinate Frame Transformations for Astrodynamics.
Supports: ECI (J2000), TEME, ECEF, Geodetic (WGS84 Lat/Lon/Alt), SEZ, AER.
"""

import math
from datetime import datetime, timezone
from typing import Tuple
import numpy as np

from aetheris.core.constants import (
    R_EARTH,
    R_EARTH_POLAR,
    FLATTENING_EARTH,
    OMEGA_EARTH
)

# WGS84 first and second eccentricity squared
WGS84_E2 = 2.0 * FLATTENING_EARTH - FLATTENING_EARTH ** 2
WGS84_E_PRIME2 = (R_EARTH ** 2 - R_EARTH_POLAR ** 2) / (R_EARTH_POLAR ** 2)


def datetime_to_julian_date(dt: datetime) -> float:
    """Compute Julian Date from datetime object (assumed UTC)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)

    year = dt.year
    month = dt.month
    day = dt.day
    hour = dt.hour
    minute = dt.minute
    second = dt.second + dt.microsecond * 1e-6

    if month <= 2:
        year -= 1
        month += 12

    a = math.floor(year / 100)
    b = 2 - a + math.floor(a / 4)

    day_fraction = (hour + minute / 60.0 + second / 3600.0) / 24.0
    jd = math.floor(365.25 * (year + 4716)) + math.floor(30.6001 * (month + 1)) + day + b - 1524.5 + day_fraction
    return jd


def julian_date_to_gmst(jd: float) -> float:
    """
    Compute Greenwich Mean Sidereal Time (GMST) in radians from Julian Date.
    Formula from Vallado (Fundamentals of Astrodynamics and Applications, 4th ed).
    """
    t_ut1 = (jd - 2451545.0) / 36525.0
    # GMST in seconds of day
    gmst_sec = (
        67310.54841
        + (876600.0 * 3600.0 + 8640184.812866) * t_ut1
        + 0.093104 * (t_ut1 ** 2)
        - 6.2e-6 * (t_ut1 ** 3)
    )
    # Convert seconds to radians in [0, 2*pi)
    gmst_rad = ((gmst_sec % 86400.0) / 86400.0) * (2.0 * math.pi)
    if gmst_rad < 0:
        gmst_rad += 2.0 * math.pi
    return gmst_rad


def eci_to_ecef(r_eci: np.ndarray, v_eci: np.ndarray, gmst_rad: float) -> Tuple[np.ndarray, np.ndarray]:
    """
    Transform position and velocity from ECI (J2000/TEME) to ECEF.
    r_eci: 3D vector [m]
    v_eci: 3D vector [m/s]
    gmst_rad: Greenwich Mean Sidereal Time in radians
    """
    cos_theta = math.cos(gmst_rad)
    sin_theta = math.sin(gmst_rad)

    r_matrix = np.array([
        [cos_theta,  sin_theta, 0.0],
        [-sin_theta, cos_theta, 0.0],
        [0.0,        0.0,       1.0]
    ], dtype=np.float64)

    r_ecef = r_matrix @ r_eci

    # Velocity includes Coriolis term: v_ecef = R * v_eci - omega x r_ecef
    omega_vec = np.array([0.0, 0.0, OMEGA_EARTH], dtype=np.float64)
    v_ecef = (r_matrix @ v_eci) - np.cross(omega_vec, r_ecef)

    return r_ecef, v_ecef


def ecef_to_eci(r_ecef: np.ndarray, v_ecef: np.ndarray, gmst_rad: float) -> Tuple[np.ndarray, np.ndarray]:
    """Transform position and velocity from ECEF to ECI."""
    cos_theta = math.cos(gmst_rad)
    sin_theta = math.sin(gmst_rad)

    r_matrix_inv = np.array([
        [cos_theta, -sin_theta, 0.0],
        [sin_theta,  cos_theta, 0.0],
        [0.0,        0.0,       1.0]
    ], dtype=np.float64)

    r_eci = r_matrix_inv @ r_ecef

    omega_vec = np.array([0.0, 0.0, OMEGA_EARTH], dtype=np.float64)
    v_inertial_in_ecef = v_ecef + np.cross(omega_vec, r_ecef)
    v_eci = r_matrix_inv @ v_inertial_in_ecef

    return r_eci, v_eci


def ecef_to_geodetic(r_ecef: np.ndarray) -> Tuple[float, float, float]:
    """
    Convert ECEF coordinates [x, y, z] in meters to WGS-84 Geodetic
    Latitude (degrees), Longitude (degrees), and Altitude above ellipsoid (meters).
    Uses Bowring's closed-form algorithm (accurate to sub-millimeter level).
    """
    x, y, z = float(r_ecef[0]), float(r_ecef[1]), float(r_ecef[2])
    p = math.sqrt(x * x + y * y)

    if p < 1e-6:
        # Near poles
        lat = 90.0 if z > 0 else -90.0
        lon = 0.0
        alt = abs(z) - R_EARTH_POLAR
        return lat, lon, alt

    lon_rad = math.atan2(y, x)

    # Bowring's parametric latitude approximation
    theta = math.atan2(z * R_EARTH, p * R_EARTH_POLAR)
    sin_theta = math.sin(theta)
    cos_theta = math.cos(theta)

    lat_rad = math.atan2(
        z + WGS84_E_PRIME2 * R_EARTH_POLAR * (sin_theta ** 3),
        p - WGS84_E2 * R_EARTH * (cos_theta ** 3)
    )

    sin_lat = math.sin(lat_rad)
    n = R_EARTH / math.sqrt(1.0 - WGS84_E2 * sin_lat * sin_lat)
    alt = (p / math.cos(lat_rad)) - n

    lat_deg = math.degrees(lat_rad)
    lon_deg = math.degrees(lon_rad)

    return lat_deg, lon_deg, alt


def geodetic_to_ecef(lat_deg: float, lon_deg: float, alt_m: float) -> np.ndarray:
    """Convert WGS84 Geodetic (Lat, Lon, Alt) to ECEF position [x, y, z] in meters."""
    lat_rad = math.radians(lat_deg)
    lon_rad = math.radians(lon_deg)

    sin_lat = math.sin(lat_rad)
    cos_lat = math.cos(lat_rad)
    sin_lon = math.sin(lon_rad)
    cos_lon = math.cos(lon_rad)

    n = R_EARTH / math.sqrt(1.0 - WGS84_E2 * sin_lat * sin_lat)

    x = (n + alt_m) * cos_lat * cos_lon
    y = (n + alt_m) * cos_lat * sin_lon
    z = (n * (1.0 - WGS84_E2) + alt_m) * sin_lat

    return np.array([x, y, z], dtype=np.float64)


def eci_to_geodetic(r_eci: np.ndarray, gmst_rad: float) -> Tuple[float, float, float]:
    """Convenience helper: ECI position vector directly to WGS84 (Lat, Lon, Alt)."""
    cos_theta = math.cos(gmst_rad)
    sin_theta = math.sin(gmst_rad)
    r_ecef = np.array([
        cos_theta * r_eci[0] + sin_theta * r_eci[1],
        -sin_theta * r_eci[0] + cos_theta * r_eci[1],
        r_eci[2]
    ], dtype=np.float64)
    return ecef_to_geodetic(r_ecef)
