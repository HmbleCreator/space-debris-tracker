"""
Chaser Spacecraft Propulsion and Active Debris Deorbit Dynamics.
Supports impulsive chemical retro-burns and continuous low-thrust electric Edelbaum spirals.
"""

import math
from dataclasses import dataclass
from typing import Optional, Tuple
import numpy as np

from aetheris.core.constants import G0, MU_EARTH, R_EARTH, REENTRY_INTERFACE_ALT_M
from aetheris.core.orbital_elements import KeplerianElements


@dataclass
class ImpulsiveDeorbitResult:
    delta_v_required_ms: float
    propellant_mass_kg: float
    burn_duration_seconds: float
    initial_perigee_km: float
    target_perigee_km: float
    entry_flight_path_angle_deg: float
    entry_velocity_kms: float
    time_to_entry_interface_minutes: float


@dataclass
class ElectricDeorbitResult:
    thrust_newtons: float
    specific_impulse_sec: float
    delta_v_required_ms: float
    propellant_mass_kg: float
    spiral_duration_days: float
    initial_altitude_km: float
    final_altitude_km: float


class ChaserPropulsionEngine:
    """Computes required thrust, delta-v, and propellant consumption for active debris deorbit."""

    @staticmethod
    def compute_impulsive_retro_burn(
        current_orbit: KeplerianElements,
        chaser_mass_kg: float,
        target_mass_kg: float,
        target_perigee_alt_km: float = 40.0,
        thrust_newtons: float = 450.0,
        isp_seconds: float = 320.0
    ) -> ImpulsiveDeorbitResult:
        """
        Compute impulsive retrograde deorbit burn at apogee to lower perigee to entry interface (target_perigee_alt_km).
        """
        r_apo = current_orbit.apogee_radius
        r_peri_target = R_EARTH + target_perigee_alt_km * 1000.0

        # Velocity in current orbit at apogee: v_apo = sqrt(mu * (2/r_apo - 1/a))
        v_current_apo = math.sqrt(MU_EARTH * (2.0 / r_apo - 1.0 / current_orbit.semi_major_axis))

        # Transfer orbit with new perigee: a_trans = 0.5 * (r_apo + r_peri_target)
        a_deorbit = 0.5 * (r_apo + r_peri_target)
        v_deorbit_apo = math.sqrt(MU_EARTH * (2.0 / r_apo - 1.0 / a_deorbit))

        # Delta-V required (retrograde, opposing velocity vector)
        dv_deorbit = abs(v_current_apo - v_deorbit_apo)

        # Combined mass being maneuvered (chaser + captured debris)
        m_total_0 = chaser_mass_kg + target_mass_kg

        # Tsiolkovsky equation: m_prop = m_total * (1 - exp(-dv / (Isp * g0)))
        prop_mass = m_total_0 * (1.0 - math.exp(-dv_deorbit / (isp_seconds * G0)))

        # Mass flow rate: m_dot = Thrust / (Isp * g0)
        m_dot = thrust_newtons / (isp_seconds * G0)
        burn_duration = prop_mass / max(1e-6, m_dot)

        # Velocity at reentry interface (altitude 120 km)
        r_entry = R_EARTH + REENTRY_INTERFACE_ALT_M
        v_entry = math.sqrt(MU_EARTH * (2.0 / r_entry - 1.0 / a_deorbit))

        # Entry flight path angle gamma: cos(gamma) = h / (r_entry * v_entry)
        h_deorbit = math.sqrt(MU_EARTH * a_deorbit * (1.0 - ((r_apo - r_peri_target) / (r_apo + r_peri_target)) ** 2))
        cos_gamma = np.clip(h_deorbit / (r_entry * v_entry), -1.0, 1.0)
        gamma_deg = -math.degrees(math.acos(cos_gamma))

        # Time of flight from apogee burn to entry interface (half orbital period)
        tof_minutes = (math.pi * math.sqrt((a_deorbit ** 3) / MU_EARTH)) / 60.0

        return ImpulsiveDeorbitResult(
            delta_v_required_ms=round(dv_deorbit, 2),
            propellant_mass_kg=round(prop_mass, 2),
            burn_duration_seconds=round(burn_duration, 1),
            initial_perigee_km=round(current_orbit.perigee_altitude_km, 2),
            target_perigee_km=round(target_perigee_alt_km, 2),
            entry_flight_path_angle_deg=round(gamma_deg, 3),
            entry_velocity_kms=round(v_entry / 1000.0, 3),
            time_to_entry_interface_minutes=round(tof_minutes, 1)
        )

    @staticmethod
    def compute_electric_low_thrust_spiral(
        current_orbit: KeplerianElements,
        chaser_mass_kg: float,
        target_mass_kg: float,
        target_altitude_km: float = 120.0,
        thrust_newtons: float = 0.25,      # e.g., 250 mN Hall/Ion Thruster
        isp_seconds: float = 3000.0         # Xenon electric propulsion
    ) -> ElectricDeorbitResult:
        """
        Compute continuous low-thrust Edelbaum spiral deorbit dynamics:
        Delta-V = v_initial - v_final (circular to circular)
        """
        r_init = current_orbit.semi_major_axis
        r_final = R_EARTH + target_altitude_km * 1000.0

        v_init = math.sqrt(MU_EARTH / r_init)
        v_final = math.sqrt(MU_EARTH / r_final)

        dv_spiral = abs(v_final - v_init)

        m_total_0 = chaser_mass_kg + target_mass_kg
        prop_mass = m_total_0 * (1.0 - math.exp(-dv_spiral / (isp_seconds * G0)))

        # Mass flow rate
        m_dot = thrust_newtons / (isp_seconds * G0)
        spiral_seconds = prop_mass / max(1e-8, m_dot)
        spiral_days = spiral_seconds / 86400.0

        return ElectricDeorbitResult(
            thrust_newtons=thrust_newtons,
            specific_impulse_sec=isp_seconds,
            delta_v_required_ms=round(dv_spiral, 2),
            propellant_mass_kg=round(prop_mass, 2),
            spiral_duration_days=round(spiral_days, 1),
            initial_altitude_km=round((r_init - R_EARTH) / 1000.0, 2),
            final_altitude_km=round(target_altitude_km, 2)
        )
