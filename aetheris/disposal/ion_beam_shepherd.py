"""
Ion Beam Shepherd (IBS) Contactless Active Debris Removal Physics Engine.
Derived directly from the governing equations of Bombardelli & Peláez (2011),
"Ion Beam Shepherd for Contactless Space Debris Removal", JGCD 34(3) / arXiv:1102.1289.

Implements:
1. Contactless beam divergence geometry (Section II):
   d_max = s / (2 * tan(phi/2))
   eta_t(d) = min(1.0, (d_max / d)^2)
2. Constant-distance formation flight secondary thruster equilibrium (Eq. 5):
   F_p2 = F_p1 * (1 + eta_t * m_IBS / m_d)
   Ensuring: a_IBS = (F_p2 - F_p1) / m_IBS = F_target / m_d = a_target
3. Continuous low-thrust orbital transfer dynamics (Section IV & V):
   T_transfer = (m_d * Delta_v) / F_target
"""

from dataclasses import dataclass
import math
from typing import Dict, Optional
import numpy as np

from aetheris.core.constants import G0, MU_EARTH, R_EARTH
from aetheris.core.orbital_elements import KeplerianElements


@dataclass
class IonBeamDeorbitResult:
    target_name: str
    target_mass_kg: float
    target_characteristic_size_m: float
    target_cross_section_m2: float
    chaser_mass_kg: float
    standoff_distance_m: float
    max_standoff_distance_for_full_intercept_m: float
    beam_divergence_half_angle_deg: float
    beam_footprint_radius_m: float
    flux_interception_efficiency_percent: float
    primary_beam_thrust_mn: float             # F_p1 [mN]
    net_target_push_force_mn: float           # F_target = eta_t * F_p1 [mN]
    secondary_formation_thruster_mn: float    # F_p2 = F_p1 * (1 + eta_t * m_IBS/m_d) [mN]
    chaser_recoil_rebound_force_mn: float     # F_p1 recoil [mN]
    shepherd_formation_acceleration_ms2: float # a_IBS [m/s^2]
    target_deorbit_acceleration_ms2: float     # a_target [m/s^2]
    delta_v_target_required_ms: float
    deorbit_dwell_duration_days: float
    daily_propellant_consumption_kg_day: float
    beam_propellant_used_kg: float
    station_keeping_propellant_used_kg: float
    total_chaser_propellant_used_kg: float
    target_perigee_altitude_km: float
    operational_mode: str = "CONTACTLESS_ION_BEAM_SHEPHERD"
    tumbling_immunity_flag: bool = True
    zero_grapple_risk_flag: bool = True


class IonBeamShepherdEngine:
    """
    Simulates contactless Ion Beam Shepherding dynamics and dual-thruster reaction equilibrium
    following Bombardelli & Peláez (2011) arXiv:1102.1289.
    """

    def __init__(
        self,
        beam_thrust_n: float = 0.20,              # Primary beam thrust F_p1 [N] (e.g. 200 mN)
        beam_isp_sec: float = 3500.0,             # Primary ion beam Isp [s]
        station_keeping_isp_sec: float = 3500.0,  # Secondary thruster Isp [s]
        beam_divergence_half_angle_deg: float = 12.0, # Divergence half-angle phi/2 [deg]
        nominal_chaser_mass_kg: float = 550.0     # Shepherd dry/wet mass m_IBS [kg]
    ):
        self.beam_thrust_n = beam_thrust_n
        self.beam_isp_sec = beam_isp_sec
        self.station_keeping_isp_sec = station_keeping_isp_sec
        self.beam_divergence_rad = math.radians(beam_divergence_half_angle_deg)
        self.nominal_chaser_mass_kg = nominal_chaser_mass_kg

    def compute_beam_footprint_radius(self, standoff_distance_m: float) -> float:
        """Compute beam footprint radius at standoff distance d: r = d * tan(phi/2)."""
        return max(0.1, standoff_distance_m * math.tan(self.beam_divergence_rad))

    def compute_max_standoff_distance(
        self,
        target_characteristic_size_m: Optional[float] = None,
        target_cross_section_m2: Optional[float] = None
    ) -> float:
        """
        Compute maximum distance d_max for 100% beam interception (Bombardelli & Pelaez 2011 Sec II):
        d_max = s / (2 * tan(phi/2))
        """
        if target_characteristic_size_m is not None:
            s = max(0.2, target_characteristic_size_m)
        elif target_cross_section_m2 is not None:
            s = 2.0 * math.sqrt(max(0.1, target_cross_section_m2) / math.pi)
        else:
            s = 2.0
        return s / (2.0 * math.tan(self.beam_divergence_rad))

    def compute_flux_interception_efficiency(
        self,
        standoff_distance_m: float,
        target_characteristic_size_m: Optional[float] = None,
        target_cross_section_m2: Optional[float] = None
    ) -> float:
        """
        Compute beam interception efficiency eta_t(d) (Bombardelli & Pelaez 2011 Sec II):
        d_max = s / (2 * tan(phi/2))
        eta_t(d) = 1.0 if d <= d_max else (d_max / d)^2
        """
        d_max = self.compute_max_standoff_distance(target_characteristic_size_m, target_cross_section_m2)
        if standoff_distance_m <= d_max:
            return 1.0
        ratio = d_max / max(0.1, standoff_distance_m)
        return float(np.clip(ratio ** 2, 0.05, 1.0))

    def compute_secondary_thruster_thrust(
        self,
        primary_thrust_n: float,
        interception_efficiency: float,
        chaser_mass_kg: float,
        target_mass_kg: float
    ) -> float:
        """
        Compute secondary thruster force F_p2 using Bombardelli & Pelaez (2011) Eq. 5:
        F_p2 = F_p1 * (1 + eta_t * (m_IBS / m_d))
        """
        mass_ratio = chaser_mass_kg / max(1.0, target_mass_kg)
        return primary_thrust_n * (1.0 + interception_efficiency * mass_ratio)

    def compute_standoff_deorbit(
        self,
        target_name: str,
        target_mass_kg: float,
        current_orbit: KeplerianElements,
        target_characteristic_size_m: Optional[float] = None,
        target_cross_section_m2: Optional[float] = None,
        standoff_distance_m: float = 20.0,
        chaser_mass_kg: Optional[float] = None,
        target_perigee_alt_km: float = 40.0,
        custom_beam_thrust_n: Optional[float] = None
    ) -> IonBeamDeorbitResult:
        """
        Calculate complete Ion Beam Shepherd deorbit timeline and dual-thruster budget.
        """
        m_ibs = chaser_mass_kg if chaser_mass_kg is not None else self.nominal_chaser_mass_kg
        f_p1 = custom_beam_thrust_n if custom_beam_thrust_n is not None else self.beam_thrust_n

        if target_characteristic_size_m is None:
            if target_cross_section_m2 is not None:
                s_char = 2.0 * math.sqrt(max(0.1, target_cross_section_m2) / math.pi)
            else:
                s_char = 3.0
        else:
            s_char = target_characteristic_size_m

        a_cross = target_cross_section_m2 if target_cross_section_m2 is not None else math.pi * (s_char / 2.0)**2

        # Target deorbit Delta-V requirement (lower perigee to target_perigee_alt_km)
        r_a = current_orbit.semi_major_axis
        r_target_peri = R_EARTH + target_perigee_alt_km * 1000.0
        r_target_apo = r_a

        a_trans = (r_target_peri + r_target_apo) / 2.0
        v_circ = math.sqrt(MU_EARTH / r_target_apo)
        v_trans_apo = math.sqrt(MU_EARTH * (2.0 / r_target_apo - 1.0 / a_trans))
        delta_v_req = abs(v_circ - v_trans_apo)

        # Beam geometry & efficiency (Bombardelli & Pelaez 2011 Sec II)
        d_max = self.compute_max_standoff_distance(s_char)
        eta_t = self.compute_flux_interception_efficiency(standoff_distance_m, s_char)
        r_beam = self.compute_beam_footprint_radius(standoff_distance_m)

        # Forces (in Newtons)
        f_target = f_p1 * eta_t  # Force transmitted to debris
        f_p2 = self.compute_secondary_thruster_thrust(f_p1, eta_t, m_ibs, target_mass_kg) # Eq. 5

        # Verify accelerations match (a_IBS = a_target)
        a_target = f_target / max(1.0, target_mass_kg)
        a_ibs = (f_p2 - f_p1) / max(1.0, m_ibs)

        # Dwell Time integration (Bombardelli & Pelaez 2011 Sec IV)
        t_dwell_sec = (target_mass_kg * delta_v_req) / max(1e-5, f_target)
        t_dwell_days = t_dwell_sec / 86400.0

        # Dual-thruster mass flow rates (F_p1 and F_p2):
        mdot_beam = f_p1 / (self.beam_isp_sec * G0)
        mdot_sk = f_p2 / (self.station_keeping_isp_sec * G0)
        mdot_total = mdot_beam + mdot_sk

        daily_propellant_kg = mdot_total * 86400.0
        beam_propellant_kg = mdot_beam * t_dwell_sec
        sk_propellant_kg = mdot_sk * t_dwell_sec
        total_chaser_propellant_kg = mdot_total * t_dwell_sec

        return IonBeamDeorbitResult(
            target_name=target_name,
            target_mass_kg=round(target_mass_kg, 1),
            target_characteristic_size_m=round(s_char, 2),
            target_cross_section_m2=round(a_cross, 2),
            chaser_mass_kg=round(m_ibs, 1),
            standoff_distance_m=round(standoff_distance_m, 1),
            max_standoff_distance_for_full_intercept_m=round(d_max, 2),
            beam_divergence_half_angle_deg=round(math.degrees(self.beam_divergence_rad), 1),
            beam_footprint_radius_m=round(r_beam, 2),
            flux_interception_efficiency_percent=round(eta_t * 100.0, 1),
            primary_beam_thrust_mn=round(f_p1 * 1000.0, 1),
            net_target_push_force_mn=round(f_target * 1000.0, 1),
            secondary_formation_thruster_mn=round(f_p2 * 1000.0, 1),
            chaser_recoil_rebound_force_mn=round(f_p1 * 1000.0, 1),
            shepherd_formation_acceleration_ms2=float(a_ibs),
            target_deorbit_acceleration_ms2=float(a_target),
            delta_v_target_required_ms=round(delta_v_req, 2),
            deorbit_dwell_duration_days=round(t_dwell_days, 1),
            daily_propellant_consumption_kg_day=round(daily_propellant_kg, 3),
            beam_propellant_used_kg=round(beam_propellant_kg, 2),
            station_keeping_propellant_used_kg=round(sk_propellant_kg, 2),
            total_chaser_propellant_used_kg=round(total_chaser_propellant_kg, 2),
            target_perigee_altitude_km=round(target_perigee_alt_km, 1),
            operational_mode="CONTACTLESS_ION_BEAM_SHEPHERD",
            tumbling_immunity_flag=True,
            zero_grapple_risk_flag=True
        )
