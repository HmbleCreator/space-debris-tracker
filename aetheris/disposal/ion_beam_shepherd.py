"""
Ion Beam Shepherd (IBS) Contactless Active Debris Removal Physics Engine.
Based on the foundational mechanics of Bombardelli & Peláez (2011) and Merino et al. (2015).

Eliminates mechanical grapple risk and attitude-matching requirements for tumbling debris.
Models:
1. Gridded Ion Beam divergence and Gaussian/conical plasma plume profile.
2. Target momentum transfer efficiency eta_transfer(d) as a function of standoff distance.
3. Dual-thruster recoil cancellation and station-keeping propellant mass-flow equilibrium.
4. Direct impulse deorbit dwell time integration: Delta_v(t) = integral(F_target / m_target dt).
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
    target_cross_section_m2: float
    standoff_distance_m: float
    beam_divergence_half_angle_deg: float
    beam_footprint_radius_m: float
    flux_interception_efficiency_percent: float
    nominal_beam_thrust_mn: float
    net_target_push_force_mn: float
    chaser_recoil_force_mn: float
    station_keeping_compensation_force_mn: float
    delta_v_target_required_ms: float
    deorbit_dwell_duration_days: float
    daily_propellant_consumption_kg_day: float
    beam_propellant_used_kg: float
    station_keeping_propellant_used_kg: float
    total_chaser_propellant_used_kg: float
    target_perigee_altitude_km: float
    operational_mode: str  # "CONTACTLESS_ION_BEAM_SHEPHERD"
    tumbling_immunity_flag: bool = True
    zero_grapple_risk_flag: bool = True


class IonBeamShepherdEngine:
    """
    Simulates contactless Ion Beam Shepherding dynamics and dual-thruster reaction equilibrium.
    """

    def __init__(
        self,
        beam_thrust_n: float = 0.20,             # 200 mN primary plasma beam
        beam_isp_sec: float = 3500.0,            # High-Isp gridded ion thruster (Xenon/Krypton)
        station_keeping_isp_sec: float = 3500.0, # Secondary recoil-compensation thruster
        beam_divergence_half_angle_deg: float = 12.0, # Gridded ion beam divergence half-angle
        primary_grid_radius_m: float = 0.15      # Exit grid radius r0
    ):
        self.beam_thrust_n = beam_thrust_n
        self.beam_isp_sec = beam_isp_sec
        self.station_keeping_isp_sec = station_keeping_isp_sec
        self.beam_divergence_rad = math.radians(beam_divergence_half_angle_deg)
        self.primary_grid_radius_m = primary_grid_radius_m

    def compute_beam_footprint_radius(self, standoff_distance_m: float) -> float:
        """
        Compute beam footprint radius at standoff distance d:
        r_beam(d) = r0 + d * tan(theta_div)
        """
        return self.primary_grid_radius_m + standoff_distance_m * math.tan(self.beam_divergence_rad)

    def compute_flux_interception_efficiency(
        self,
        standoff_distance_m: float,
        target_cross_section_m2: float
    ) -> float:
        """
        Compute beam momentum transfer efficiency eta_transfer(d).
        Models Gaussian/conical plasma density distribution intercepted by target area:
        eta(d) = 1 - exp(-2 * (r_target / w_core(d))^2)
        where w_core(d) is the 1/e^2 beam waist radius with core divergence ~ 0.55 * theta_div.
        """
        # Core Gaussian beam waist radius
        core_divergence_rad = self.beam_divergence_rad * 0.55
        w_core = self.primary_grid_radius_m + standoff_distance_m * math.tan(core_divergence_rad)
        r_target = math.sqrt(max(0.01, target_cross_section_m2) / math.pi)

        ratio = r_target / max(0.05, w_core)
        efficiency = 1.0 - math.exp(-2.0 * (ratio ** 2))
        return float(np.clip(efficiency, 0.05, 0.98))

    def compute_standoff_deorbit(
        self,
        target_name: str,
        target_mass_kg: float,
        target_cross_section_m2: float,
        current_orbit: KeplerianElements,
        standoff_distance_m: float = 20.0,
        target_perigee_alt_km: float = 40.0,
        custom_beam_thrust_n: Optional[float] = None
    ) -> IonBeamDeorbitResult:
        """
        Calculate complete Ion Beam Shepherd contactless deorbit dwell time and propellant budget.
        """
        f_beam = custom_beam_thrust_n if custom_beam_thrust_n is not None else self.beam_thrust_n

        # Target deorbit Delta-V requirement (lower perigee to target_perigee_alt_km)
        r_a = current_orbit.semi_major_axis
        r_target_peri = R_EARTH + target_perigee_alt_km * 1000.0
        r_target_apo = r_a  # Initial orbit altitude

        a_trans = (r_target_peri + r_target_apo) / 2.0
        v_circ = math.sqrt(MU_EARTH / r_target_apo)
        v_trans_apo = math.sqrt(MU_EARTH * (2.0 / r_target_apo - 1.0 / a_trans))
        delta_v_req = abs(v_circ - v_trans_apo)

        # Beam geometry & efficiency
        r_beam = self.compute_beam_footprint_radius(standoff_distance_m)
        eta_transfer = self.compute_flux_interception_efficiency(standoff_distance_m, target_cross_section_m2)

        # Forces (in Newtons)
        f_target = f_beam * eta_transfer
        f_recoil = f_beam
        f_sk = f_beam  # Station keeping exactly cancels recoil to hold standoff formation

        # Dwell Time integration (target mass remains constant)
        # Delta_v = (F_target / m_target) * T_dwell
        # T_dwell = (m_target * Delta_v) / F_target
        t_dwell_sec = (target_mass_kg * delta_v_req) / max(1e-4, f_target)
        t_dwell_days = t_dwell_sec / 86400.0

        # Dual-thruster mass flow rates:
        # mdot_beam = F_beam / (Isp_beam * g0)
        # mdot_sk = F_sk / (Isp_sk * g0)
        mdot_beam = f_beam / (self.beam_isp_sec * G0)
        mdot_sk = f_sk / (self.station_keeping_isp_sec * G0)
        mdot_total = mdot_beam + mdot_sk

        daily_propellant_kg = mdot_total * 86400.0
        beam_propellant_kg = mdot_beam * t_dwell_sec
        sk_propellant_kg = mdot_sk * t_dwell_sec
        total_chaser_propellant_kg = mdot_total * t_dwell_sec

        return IonBeamDeorbitResult(
            target_name=target_name,
            target_mass_kg=round(target_mass_kg, 1),
            target_cross_section_m2=round(target_cross_section_m2, 2),
            standoff_distance_m=round(standoff_distance_m, 1),
            beam_divergence_half_angle_deg=round(math.degrees(self.beam_divergence_rad), 1),
            beam_footprint_radius_m=round(r_beam, 2),
            flux_interception_efficiency_percent=round(eta_transfer * 100.0, 1),
            nominal_beam_thrust_mn=round(f_beam * 1000.0, 1),
            net_target_push_force_mn=round(f_target * 1000.0, 1),
            chaser_recoil_force_mn=round(f_recoil * 1000.0, 1),
            station_keeping_compensation_force_mn=round(f_sk * 1000.0, 1),
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
