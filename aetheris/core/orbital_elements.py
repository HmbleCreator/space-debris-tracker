"""
Keplerian and Cartesian Orbital Elements Representation and Conversions.
"""

import math
from dataclasses import dataclass
from typing import Optional, Tuple
import numpy as np

from aetheris.core.constants import MU_EARTH, R_EARTH, J2


@dataclass
class KeplerianElements:
    semi_major_axis: float       # a in meters
    eccentricity: float          # e [0, 1) for elliptic
    inclination: float           # i in radians
    raan: float                  # Omega in radians [0, 2*pi)
    arg_of_perigee: float        # omega in radians [0, 2*pi)
    true_anomaly: float          # nu in radians [0, 2*pi)

    @property
    def period(self) -> float:
        """Orbital period in seconds: T = 2*pi * sqrt(a^3 / mu)."""
        if self.semi_major_axis <= 0:
            return float("inf")
        return 2.0 * math.pi * math.sqrt((self.semi_major_axis ** 3) / MU_EARTH)

    @property
    def mean_motion(self) -> float:
        """Mean motion n in rad/s: n = sqrt(mu / a^3)."""
        if self.semi_major_axis <= 0:
            return 0.0
        return math.sqrt(MU_EARTH / (self.semi_major_axis ** 3))

    @property
    def mean_motion_rev_per_day(self) -> float:
        """Mean motion in revolutions per day (standard TLE format)."""
        return self.mean_motion * 86400.0 / (2.0 * math.pi)

    @property
    def perigee_radius(self) -> float:
        """Perigee radius r_p in meters: r_p = a * (1 - e)."""
        return self.semi_major_axis * (1.0 - self.eccentricity)

    @property
    def apogee_radius(self) -> float:
        """Apogee radius r_a in meters: r_a = a * (1 + e)."""
        return self.semi_major_axis * (1.0 + self.eccentricity)

    @property
    def perigee_altitude_km(self) -> float:
        """Perigee altitude above Earth surface in km."""
        return (self.perigee_radius - R_EARTH) / 1000.0

    @property
    def apogee_altitude_km(self) -> float:
        """Apogee altitude above Earth surface in km."""
        return (self.apogee_radius - R_EARTH) / 1000.0

    @property
    def semi_parameter(self) -> float:
        """Semi-latus rectum p = a * (1 - e^2)."""
        return self.semi_major_axis * (1.0 - self.eccentricity ** 2)

    @property
    def j2_raan_drift_rate(self) -> float:
        """
        Nodal precession rate (dOmega/dt) due to J2 in rad/s.
        dOmega/dt = -1.5 * J2 * (R_E / p)^2 * n * cos(i)
        """
        p = self.semi_parameter
        if p <= 0:
            return 0.0
        n = self.mean_motion
        return -1.5 * J2 * ((R_EARTH / p) ** 2) * n * math.cos(self.inclination)

    @property
    def j2_raan_drift_deg_per_day(self) -> float:
        """Nodal precession rate in degrees per day."""
        return math.degrees(self.j2_raan_drift_rate) * 86400.0

    @property
    def j2_arg_perigee_drift_rate(self) -> float:
        """
        Apsidal precession rate (domega/dt) due to J2 in rad/s.
        domega/dt = 0.75 * J2 * (R_E / p)^2 * n * (5*cos(i)^2 - 1)
        """
        p = self.semi_parameter
        if p <= 0:
            return 0.0
        n = self.mean_motion
        cos_i = math.cos(self.inclination)
        return 0.75 * J2 * ((R_EARTH / p) ** 2) * n * (5.0 * cos_i * cos_i - 1.0)


def solve_kepler_eccentric_anomaly(mean_anomaly: float, eccentricity: float, tolerance: float = 1e-12, max_iter: int = 100) -> float:
    """
    Solve Kepler's equation M = E - e*sin(E) for Eccentric Anomaly E using Newton-Raphson.
    M: Mean anomaly in radians
    eccentricity: Orbital eccentricity [0, 1)
    """
    # Normalize M to [0, 2*pi)
    m_norm = mean_anomaly % (2.0 * math.pi)

    # Initial guess (Danby's method)
    if eccentricity < 0.8:
        e_curr = m_norm
    else:
        e_curr = math.pi

    for _ in range(max_iter):
        f = e_curr - eccentricity * math.sin(e_curr) - m_norm
        f_prime = 1.0 - eccentricity * math.cos(e_curr)
        delta = f / f_prime
        e_curr -= delta
        if abs(delta) < tolerance:
            break

    return e_curr % (2.0 * math.pi)


def eccentric_anomaly_to_true_anomaly(eccentric_anomaly: float, eccentricity: float) -> float:
    """Convert Eccentric Anomaly E to True Anomaly nu in radians."""
    cos_e = math.cos(eccentric_anomaly)
    sin_e = math.sin(eccentric_anomaly)

    beta = eccentricity / (1.0 + math.sqrt(1.0 - eccentricity ** 2))
    nu = eccentric_anomaly + 2.0 * math.atan((beta * sin_e) / (1.0 - beta * cos_e))
    return nu % (2.0 * math.pi)


def true_anomaly_to_mean_anomaly(true_anomaly: float, eccentricity: float) -> float:
    """Convert True Anomaly nu to Mean Anomaly M in radians."""
    cos_nu = math.cos(true_anomaly)
    sin_nu = math.sin(true_anomaly)

    # Eccentric anomaly
    cos_e = (eccentricity + cos_nu) / (1.0 + eccentricity * cos_nu)
    sin_e = (math.sqrt(1.0 - eccentricity ** 2) * sin_nu) / (1.0 + eccentricity * cos_nu)
    e_anom = math.atan2(sin_e, cos_e)

    # Kepler equation: M = E - e*sin(E)
    m = e_anom - eccentricity * math.sin(e_anom)
    return m % (2.0 * math.pi)


def cartesian_to_keplerian(r_vec: np.ndarray, v_vec: np.ndarray, mu: float = MU_EARTH) -> KeplerianElements:
    """
    Convert ECI Cartesian state vector (r, v) in meters and m/s to classical Keplerian elements.
    """
    r_mag = np.linalg.norm(r_vec)
    v_mag = np.linalg.norm(v_vec)

    if r_mag == 0:
        raise ValueError("Position vector norm is zero.")

    # Angular momentum vector h = r x v
    h_vec = np.cross(r_vec, v_vec)
    h_mag = np.linalg.norm(h_vec)

    # Node vector n = k x h
    k_unit = np.array([0.0, 0.0, 1.0], dtype=np.float64)
    n_vec = np.cross(k_unit, h_vec)
    n_mag = np.linalg.norm(n_vec)

    # Eccentricity vector e = (1/mu) * ((v^2 - mu/r)*r - (r.v)*v)
    e_vec = (1.0 / mu) * ((v_mag ** 2 - (mu / r_mag)) * r_vec - np.dot(r_vec, v_vec) * v_vec)
    e_mag = float(np.linalg.norm(e_vec))

    # Specific mechanical energy: epsilon = v^2 / 2 - mu / r
    energy = (v_mag ** 2) / 2.0 - (mu / r_mag)

    # Semi-major axis: a = -mu / (2 * epsilon)
    if abs(energy) > 1e-12:
        a = -mu / (2.0 * energy)
    else:
        a = float("inf")

    # Inclination: cos(i) = h_z / h
    inc = math.acos(np.clip(h_vec[2] / h_mag, -1.0, 1.0))

    # Right Ascension of Ascending Node (RAAN): Omega
    if n_mag > 1e-8:
        raan = math.acos(np.clip(n_vec[0] / n_mag, -1.0, 1.0))
        if n_vec[1] < 0:
            raan = 2.0 * math.pi - raan
    else:
        raan = 0.0

    # Argument of Perigee: omega
    if n_mag > 1e-8 and e_mag > 1e-8:
        arg_p = math.acos(np.clip(np.dot(n_vec, e_vec) / (n_mag * e_mag), -1.0, 1.0))
        if e_vec[2] < 0:
            arg_p = 2.0 * math.pi - arg_p
    else:
        arg_p = 0.0

    # True Anomaly: nu
    if e_mag > 1e-8:
        cos_nu = np.clip(np.dot(e_vec, r_vec) / (e_mag * r_mag), -1.0, 1.0)
        nu = math.acos(cos_nu)
        if np.dot(r_vec, v_vec) < 0:
            nu = 2.0 * math.pi - nu
    else:
        # Circular orbit: use argument of latitude
        if n_mag > 1e-8:
            cos_u = np.clip(np.dot(n_vec, r_vec) / (n_mag * r_mag), -1.0, 1.0)
            nu = math.acos(cos_u)
            if r_vec[2] < 0:
                nu = 2.0 * math.pi - nu
        else:
            nu = math.atan2(r_vec[1], r_vec[0])
            if nu < 0:
                nu += 2.0 * math.pi

    return KeplerianElements(
        semi_major_axis=float(a),
        eccentricity=float(e_mag),
        inclination=float(inc),
        raan=float(raan),
        arg_of_perigee=float(arg_p),
        true_anomaly=float(nu)
    )


def keplerian_to_cartesian(elements: KeplerianElements, mu: float = MU_EARTH) -> Tuple[np.ndarray, np.ndarray]:
    """
    Convert classical Keplerian elements to ECI Cartesian position and velocity vectors.
    Returns: (r_vec [m], v_vec [m/s])
    """
    a = elements.semi_major_axis
    e = elements.eccentricity
    i = elements.inclination
    raan = elements.raan
    omega = elements.arg_of_perigee
    nu = elements.true_anomaly

    # Semi-latus rectum p
    p = a * (1.0 - e * e)
    if p <= 0:
        raise ValueError(f"Invalid semi-latus rectum p={p} for a={a}, e={e}")

    # Radius magnitude in orbital plane
    r_orbit_mag = p / (1.0 + e * math.cos(nu))

    # Position and velocity in perifocal frame (PQW)
    r_pqw = np.array([
        r_orbit_mag * math.cos(nu),
        r_orbit_mag * math.sin(nu),
        0.0
    ], dtype=np.float64)

    sqrt_mu_p = math.sqrt(mu / p)
    v_pqw = np.array([
        -sqrt_mu_p * math.sin(nu),
        sqrt_mu_p * (e + math.cos(nu)),
        0.0
    ], dtype=np.float64)

    # Rotation matrix from Perifocal (PQW) to ECI
    cos_o = math.cos(raan)
    sin_o = math.sin(raan)
    cos_w = math.cos(omega)
    sin_w = math.sin(omega)
    cos_i = math.cos(i)
    sin_i = math.sin(i)

    r_matrix = np.array([
        [
            cos_o * cos_w - sin_o * sin_w * cos_i,
            -cos_o * sin_w - sin_o * cos_w * cos_i,
            sin_o * sin_i
        ],
        [
            sin_o * cos_w + cos_o * sin_w * cos_i,
            -sin_o * sin_w + cos_o * cos_w * cos_i,
            -cos_o * sin_i
        ],
        [
            sin_w * sin_i,
            cos_w * sin_i,
            cos_i
        ]
    ], dtype=np.float64)

    r_eci = r_matrix @ r_pqw
    v_eci = r_matrix @ v_pqw

    return r_eci, v_eci
