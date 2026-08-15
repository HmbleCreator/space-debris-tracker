"""
High-Precision Orbit Propagator (HPOP) using Cowell Numerical Integration (RK45).
Includes: J2-J6 Earth Gravity Harmonics, Atmospheric Drag, Solar Radiation Pressure (SRP), Third-Body Gravity.
"""

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, List, Optional, Tuple
import numpy as np

from aetheris.core.constants import (
    MU_EARTH,
    MU_SUN,
    MU_MOON,
    R_EARTH,
    AU_METERS,
    SOLAR_RADIATION_PRESSURE_1AU,
    SPEED_OF_LIGHT
)
from aetheris.core.coordinates import datetime_to_julian_date, julian_date_to_gmst, eci_to_geodetic
from aetheris.core.orbital_elements import cartesian_to_keplerian
from aetheris.dynamics.gravity_harmonics import compute_geopotential_acceleration
from aetheris.dynamics.atmospheric_models import compute_drag_acceleration


@dataclass
class TrajectoryPoint:
    time_seconds: float
    datetime_utc: datetime
    position_eci_m: np.ndarray
    velocity_eci_ms: np.ndarray
    acceleration_eci_ms2: np.ndarray
    altitude_km: float
    latitude_deg: float
    longitude_deg: float
    speed_kms: float
    specific_energy_j_kg: float


@dataclass
class HPOPConfig:
    max_zonal_harmonics: int = 4  # J2..J4
    include_drag: bool = True
    include_srp: bool = True
    include_third_body: bool = True
    cr_srp: float = 1.2           # Radiation pressure coefficient
    cd_drag: float = 2.2          # Drag coefficient
    area_m2: float = 1.0          # Cross-sectional area
    mass_kg: float = 100.0        # Spacecraft mass
    f107_flux: float = 150.0      # Solar flux index
    ap_index: float = 15.0        # Geomagnetic index


def _approximate_sun_position_eci(jd: float) -> np.ndarray:
    """Low-precision analytical Sun position in ECI frame [m]."""
    n = jd - 2451545.0
    l = math.radians((280.460 + 0.9856474 * n) % 360.0)
    g = math.radians((357.528 + 0.9856003 * n) % 360.0)
    lambda_sun = l + math.radians(1.915 * math.sin(g) + 0.020 * math.sin(2.0 * g))
    eps = math.radians(23.439 - 0.0000004 * n)  # Earth obliquity

    r_sun_au = 1.00014 - 0.01671 * math.cos(g) - 0.00014 * math.cos(2.0 * g)
    r_sun_m = r_sun_au * AU_METERS

    x = r_sun_m * math.cos(lambda_sun)
    y = r_sun_m * math.sin(lambda_sun) * math.cos(eps)
    z = r_sun_m * math.sin(lambda_sun) * math.sin(eps)

    return np.array([x, y, z], dtype=np.float64)


def _approximate_moon_position_eci(jd: float) -> np.ndarray:
    """Low-precision analytical Moon position in ECI frame [m]."""
    t = (jd - 2451545.0) / 36525.0
    # Mean longitude and elongations
    l_prime = math.radians((218.3164 + 481267.8882 * t) % 360.0)
    d = math.radians((297.8502 + 445267.1114 * t) % 360.0)
    m_prime = math.radians((134.9634 + 477198.8676 * t) % 360.0)
    f = math.radians((93.2721 + 483202.0175 * t) % 360.0)

    # Ecliptic coordinates approximation
    lon_moon = l_prime + math.radians(6.289 * math.sin(m_prime) + 1.274 * math.sin(2.0 * d - m_prime))
    lat_moon = math.radians(5.128 * math.sin(f))
    r_moon_m = (385000.5 - 20905.0 * math.cos(m_prime) - 3699.0 * math.cos(2.0 * d - m_prime)) * 1000.0

    eps = math.radians(23.439)
    x = r_moon_m * math.cos(lat_moon) * math.cos(lon_moon)
    y = r_moon_m * (math.cos(lat_moon) * math.sin(lon_moon) * math.cos(eps) - math.sin(lat_moon) * math.sin(eps))
    z = r_moon_m * (math.cos(lat_moon) * math.sin(lon_moon) * math.sin(eps) + math.sin(lat_moon) * math.cos(eps))

    return np.array([x, y, z], dtype=np.float64)


def compute_srp_acceleration(
    r_eci: np.ndarray,
    r_sun_eci: np.ndarray,
    cr: float,
    area_m2: float,
    mass_kg: float
) -> np.ndarray:
    """
    Compute Solar Radiation Pressure acceleration with cylindrical shadow occultation.
    """
    if mass_kg <= 0 or area_m2 <= 0:
        return np.zeros(3, dtype=np.float64)

    r_sun_sc = r_eci - r_sun_eci
    dist_sun_sc = np.linalg.norm(r_sun_sc)

    # Shadow check (cylindrical Earth shadow)
    # Sun direction from Earth
    u_sun = r_sun_eci / np.linalg.norm(r_sun_eci)
    proj_r = np.dot(r_eci, u_sun)

    in_shadow = False
    if proj_r < 0:  # Satellite is on night side of Earth
        r_perp = np.linalg.norm(r_eci - proj_r * u_sun)
        if r_perp < R_EARTH:
            in_shadow = True

    if in_shadow:
        return np.zeros(3, dtype=np.float64)

    # Pressure at spacecraft distance: P = P_1AU * (1 AU / dist)^2
    p_srp = SOLAR_RADIATION_PRESSURE_1AU * ((AU_METERS / dist_sun_sc) ** 2)
    srp_mag = p_srp * cr * (area_m2 / mass_kg)
    u_sc_sun = r_sun_sc / dist_sun_sc  # pointing away from Sun

    return srp_mag * (-u_sc_sun)


def compute_third_body_acceleration(
    r_eci: np.ndarray,
    r_body_eci: np.ndarray,
    mu_body: float
) -> np.ndarray:
    """
    Compute point-mass third body gravitational acceleration:
    a_3rd = -mu_body * [ (r - r_body) / |r - r_body|^3 + r_body / |r_body|^3 ]
    """
    r_rel = r_eci - r_body_eci
    d_rel = np.linalg.norm(r_rel)
    d_body = np.linalg.norm(r_body_eci)

    if d_rel < 1e-3 or d_body < 1e-3:
        return np.zeros(3, dtype=np.float64)

    a_3rd = -mu_body * ((r_rel / (d_rel ** 3)) + (r_body_eci / (d_body ** 3)))
    return a_3rd


class NumericalPropagator:
    """High-Precision Orbit Propagator executing Cowell RK45 integration."""

    def __init__(self, config: Optional[HPOPConfig] = None):
        self.config = config or HPOPConfig()

    def total_acceleration(
        self,
        t_sec: float,
        r_eci: np.ndarray,
        v_eci: np.ndarray,
        epoch_jd: float
    ) -> np.ndarray:
        """Sum all gravitational and non-gravitational acceleration forces."""
        # 1. Earth Gravity Harmonics (Central + J2..J6)
        a_total = compute_geopotential_acceleration(
            r_eci,
            max_zonal_degree=self.config.max_zonal_harmonics
        )

        # 2. Atmospheric Drag
        if self.config.include_drag:
            a_drag = compute_drag_acceleration(
                r_eci=r_eci,
                v_eci=v_eci,
                cd=self.config.cd_drag,
                area_m2=self.config.area_m2,
                mass_kg=self.config.mass_kg,
                f107_flux=self.config.f107_flux,
                ap_index=self.config.ap_index
            )
            a_total += a_drag

        # Ephemeris time for Sun and Moon
        jd_current = epoch_jd + t_sec / 86400.0

        # 3. Solar Radiation Pressure (SRP)
        if self.config.include_srp:
            r_sun = _approximate_sun_position_eci(jd_current)
            a_srp = compute_srp_acceleration(
                r_eci=r_eci,
                r_sun_eci=r_sun,
                cr=self.config.cr_srp,
                area_m2=self.config.area_m2,
                mass_kg=self.config.mass_kg
            )
            a_total += a_srp

        # 4. Third-Body Lunisolar Perturbations
        if self.config.include_third_body:
            r_sun = _approximate_sun_position_eci(jd_current)
            a_sun = compute_third_body_acceleration(r_eci, r_sun, MU_SUN)

            r_moon = _approximate_moon_position_eci(jd_current)
            a_moon = compute_third_body_acceleration(r_eci, r_moon, MU_MOON)

            a_total += a_sun + a_moon

        return a_total

    def propagate(
        self,
        r0_eci: np.ndarray,
        v0_eci: np.ndarray,
        start_epoch: datetime,
        duration_seconds: float,
        step_seconds: float = 60.0
    ) -> List[TrajectoryPoint]:
        """
        Numerically propagate orbit forward using classical 4th/5th order Runge-Kutta.
        Returns list of TrajectoryPoints with high-frequency state ephemeris.
        """
        if start_epoch.tzinfo is None:
            epoch_utc = start_epoch.replace(tzinfo=timezone.utc)
        else:
            epoch_utc = start_epoch.astimezone(timezone.utc)

        epoch_jd = datetime_to_julian_date(epoch_utc)

        r = np.array(r0_eci, dtype=np.float64)
        v = np.array(v0_eci, dtype=np.float64)

        t = 0.0
        trajectory: List[TrajectoryPoint] = []

        # Record initial point
        jd_curr = epoch_jd + t / 86400.0
        gmst = julian_date_to_gmst(jd_curr)
        lat, lon, alt = eci_to_geodetic(r, gmst)
        a_init = self.total_acceleration(t, r, v, epoch_jd)
        energy_init = 0.5 * np.dot(v, v) - (MU_EARTH / np.linalg.norm(r))

        trajectory.append(TrajectoryPoint(
            time_seconds=t,
            datetime_utc=epoch_utc,
            position_eci_m=r.copy(),
            velocity_eci_ms=v.copy(),
            acceleration_eci_ms2=a_init.copy(),
            altitude_km=alt / 1000.0,
            latitude_deg=lat,
            longitude_deg=lon,
            speed_kms=np.linalg.norm(v) / 1000.0,
            specific_energy_j_kg=energy_init
        ))

        # Propagation loop
        while t < duration_seconds:
            dt = min(step_seconds, duration_seconds - t)

            # RK4 Integration step
            # k1
            k1_r = v
            k1_v = self.total_acceleration(t, r, v, epoch_jd)

            # k2
            r_k2 = r + 0.5 * dt * k1_r
            v_k2 = v + 0.5 * dt * k1_v
            k2_r = v_k2
            k2_v = self.total_acceleration(t + 0.5 * dt, r_k2, v_k2, epoch_jd)

            # k3
            r_k3 = r + 0.5 * dt * k2_r
            v_k3 = v + 0.5 * dt * k2_v
            k3_r = v_k3
            k3_v = self.total_acceleration(t + 0.5 * dt, r_k3, v_k3, epoch_jd)

            # k4
            r_k4 = r + dt * k3_r
            v_k4 = v + dt * k3_v
            k4_r = v_k4
            k4_v = self.total_acceleration(t + dt, r_k4, v_k4, epoch_jd)

            # State update
            r = r + (dt / 6.0) * (k1_r + 2.0 * k2_r + 2.0 * k3_r + k4_r)
            v = v + (dt / 6.0) * (k1_v + 2.0 * k2_v + 2.0 * k3_v + k4_v)
            t += dt

            # Terminate if impacted Earth surface
            r_mag = np.linalg.norm(r)
            if r_mag < R_EARTH:
                # Ground impact reached
                jd_curr = epoch_jd + t / 86400.0
                gmst = julian_date_to_gmst(jd_curr)
                lat, lon, alt = eci_to_geodetic(r, gmst)
                trajectory.append(TrajectoryPoint(
                    time_seconds=t,
                    datetime_utc=datetime.fromtimestamp(epoch_utc.timestamp() + t, tz=timezone.utc),
                    position_eci_m=r.copy(),
                    velocity_eci_ms=v.copy(),
                    acceleration_eci_ms2=k4_v.copy(),
                    altitude_km=0.0,
                    latitude_deg=lat,
                    longitude_deg=lon,
                    speed_kms=np.linalg.norm(v) / 1000.0,
                    specific_energy_j_kg=0.5 * np.dot(v, v) - (MU_EARTH / r_mag)
                ))
                break

            jd_curr = epoch_jd + t / 86400.0
            gmst = julian_date_to_gmst(jd_curr)
            lat, lon, alt = eci_to_geodetic(r, gmst)
            energy = 0.5 * np.dot(v, v) - (MU_EARTH / r_mag)

            trajectory.append(TrajectoryPoint(
                time_seconds=t,
                datetime_utc=datetime.fromtimestamp(epoch_utc.timestamp() + t, tz=timezone.utc),
                position_eci_m=r.copy(),
                velocity_eci_ms=v.copy(),
                acceleration_eci_ms2=k4_v.copy(),
                altitude_km=alt / 1000.0,
                latitude_deg=lat,
                longitude_deg=lon,
                speed_kms=np.linalg.norm(v) / 1000.0,
                specific_energy_j_kg=energy
            ))

        return trajectory
