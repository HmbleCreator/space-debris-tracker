"""
Aerothermal Reentry Demise and Spacecraft Demisability Survivability Simulator.
Implements Detra-Kemp-Riddell / Fay-Riddell stagnation heat flux and multi-material phase-change ablation.
"""

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import numpy as np

from aetheris.catalog.debris_object import DebrisObject
from aetheris.core.constants import (
    C_DKR,
    G0,
    MATERIAL_DATABASE,
    MaterialProperties,
    RHO_0,
    R_EARTH,
    CASUALTY_AREA_LIMIT_M2,
    CRITICAL_IMPACT_KINETIC_ENERGY_J
)
from aetheris.dynamics.atmospheric_models import get_atmospheric_density


@dataclass
class MaterialDemiseStatus:
    material_name: str
    initial_mass_kg: float
    surviving_mass_kg: float
    demise_altitude_km: Optional[float]
    survived: bool
    temperature_k: float
    melting_point_k: float


@dataclass
class ReentryDemiseResult:
    target_name: str
    initial_mass_kg: float
    total_surviving_mass_kg: float
    mass_demised_fraction_percent: float
    peak_heat_flux_mw_m2: float
    peak_deceleration_g: float
    breakup_altitude_km: float
    estimated_casualty_area_m2: float
    ground_impact_kinetic_energy_j: float
    is_safe_demise: bool
    disposal_recommendation: str  # "SAFE_ATMOSPHERIC_INCINERATION" or "MANDATORY_POINT_NEMO_TARGETING"
    component_breakdown: List[MaterialDemiseStatus] = field(default_factory=list)
    altitude_profile_km: List[float] = field(default_factory=list)
    heat_flux_profile_kw_m2: List[float] = field(default_factory=list)
    temperature_profile_k: List[float] = field(default_factory=list)


class AerothermalDemiseSimulator:
    """Simulates atmospheric entry, aerothermal stagnation heating, and material ablation."""

    def __init__(self):
        self.materials = MATERIAL_DATABASE

    def simulate_entry_demise(
        self,
        debris: DebrisObject,
        entry_gamma_deg: float = -2.5,
        entry_velocity_kms: float = 7.6
    ) -> ReentryDemiseResult:
        """
        Simulate aerothermal entry trajectory from 120 km altitude down to ground.
        Solves coupled equations of 2D entry motion, stagnation heat flux, and material phase-change.
        """
        # Entry initial conditions
        alt_m = 120000.0  # 120 km
        v_ms = entry_velocity_kms * 1000.0
        gamma_rad = math.radians(entry_gamma_deg)

        total_mass = max(1.0, debris.estimated_mass_kg)
        r_eff = max(0.1, 0.5 * debris.characteristic_size_m)
        area_proj = max(0.01, debris.cross_sectional_area_m2)
        cd = debris.drag_coefficient_cd

        # Initialize component tracking based on debris material breakdown
        components: Dict[str, dict] = {}
        for mat_key, frac in debris.material_breakdown.items():
            mat_prop = self.materials.get(mat_key, self.materials["ALUMINUM_6061"])
            m_comp = total_mass * frac
            components[mat_key] = {
                "prop": mat_prop,
                "initial_mass": m_comp,
                "current_mass": m_comp,
                "temperature": 300.0,  # 300 K initial orbital temperature
                "melted_energy": 0.0,
                "demise_alt": None,
                "survived": True
            }

        # Trajectory recording
        alt_history = []
        q_history = []
        temp_history = []

        peak_heat_flux = 0.0
        peak_decel = 0.0
        breakup_altitude = 78.0  # standard altitude where main structural fragmentation occurs

        dt = 0.5  # 0.5 sec integration step
        t = 0.0
        stefan_boltzmann = 5.670374419e-8

        while alt_m > 0 and v_ms > 50.0:
            rho = get_atmospheric_density(alt_m)

            # Stagnation point heat flux: q_stag = C_DKR * sqrt(rho / R_eff) * V^3 [W/m^2]
            q_stag = C_DKR * math.sqrt(rho / max(0.05, r_eff)) * (v_ms ** 3)
            peak_heat_flux = max(peak_heat_flux, q_stag)

            # Record profile periodically
            if int(t / dt) % 10 == 0:
                alt_history.append(round(alt_m / 1000.0, 1))
                q_history.append(round(q_stag / 1000.0, 1))  # in kW/m^2
                # Mean temperature of aluminum structure
                al_comp = components.get("ALUMINUM_6061", list(components.values())[0])
                temp_history.append(round(al_comp["temperature"], 1))

            # Aerodynamic drag deceleration
            # m_curr = sum of current component masses
            m_current = sum(c["current_mass"] for c in components.values())
            if m_current <= 0.01:
                # Fully demised before reaching ground
                break

            drag_force = 0.5 * rho * (v_ms ** 2) * cd * area_proj
            decel = drag_force / m_current
            peak_decel = max(peak_decel, decel / G0)

            # Heat transfer into each component
            # Unshielded small fragments have higher effective heating area-to-mass
            heating_efficiency = min(0.90, 0.45 + (1.0 / math.sqrt(max(1.0, total_mass))) * 0.45)
            q_absorbed = q_stag * heating_efficiency

            for mat_key, comp in components.items():
                if not comp["survived"]:
                    continue

                prop: MaterialProperties = comp["prop"]
                # Radiative heat rejection: q_rad = eps * sigma * T^4
                q_rad = prop.emissivity * stefan_boltzmann * (comp["temperature"] ** 4)
                net_heat_flux = max(0.0, q_absorbed - q_rad)
                q_in_watts = net_heat_flux * (area_proj * (comp["current_mass"] / total_mass))

                if comp["temperature"] < prop.melting_temp:
                    # Sensible heating: dT = Q_in / (m * cp)
                    delta_t = (q_in_watts * dt) / (comp["current_mass"] * prop.specific_heat)
                    comp["temperature"] += delta_t
                    if comp["temperature"] >= prop.melting_temp:
                        comp["temperature"] = prop.melting_temp
                else:
                    # Latent heat melting / ablation: dm = Q_in / H_fusion
                    dm_abl = (q_in_watts * dt) / prop.latent_heat_fusion
                    comp["current_mass"] -= dm_abl
                    if comp["current_mass"] <= 0.001:
                        comp["current_mass"] = 0.0
                        comp["survived"] = False
                        comp["demise_alt"] = alt_m / 1000.0

            # Kinematic update for entry trajectory
            # dv/dt = -decel + g * sin(gamma)
            g_local = G0 * ((R_EARTH / (R_EARTH + alt_m)) ** 2)
            dv = (-decel + g_local * math.sin(gamma_rad)) * dt
            # dgamma/dt = -(g/v - v/r) * cos(gamma)
            dgamma = -((g_local / max(1.0, v_ms)) - (v_ms / (R_EARTH + alt_m))) * math.cos(gamma_rad) * dt

            v_ms = max(20.0, v_ms + dv)
            gamma_rad = np.clip(gamma_rad + dgamma, -math.pi * 0.45, -0.01)

            # Altitude update: dh/dt = v * sin(gamma)
            alt_m += v_ms * math.sin(gamma_rad) * dt
            t += dt

        # Final assessment of surviving components
        component_results: List[MaterialDemiseStatus] = []
        total_surviving_mass = 0.0

        for mat_key, comp in components.items():
            surv_m = comp["current_mass"]
            total_surviving_mass += surv_m
            component_results.append(MaterialDemiseStatus(
                material_name=comp["prop"].name,
                initial_mass_kg=round(comp["initial_mass"], 2),
                surviving_mass_kg=round(surv_m, 2),
                demise_altitude_km=round(comp["demise_alt"], 1) if comp["demise_alt"] else None,
                survived=comp["survived"],
                temperature_k=round(comp["temperature"], 1),
                melting_point_k=comp["prop"].melting_temp
            ))

        demised_fraction_pct = ((total_mass - total_surviving_mass) / total_mass) * 100.0

        # Ground impact kinetic energy and casualty area
        # Terminal velocity at sea level: v_term = sqrt(2 * m * g / (rho_0 * Cd * A))
        if total_surviving_mass > 0:
            v_term = math.sqrt((2.0 * total_surviving_mass * G0) / (RHO_0 * cd * max(0.01, area_proj * 0.5)))
            impact_ke = 0.5 * total_surviving_mass * (v_term ** 2)
            # Casualty area (NASA standard: Ac = (sqrt(A_frag) + 0.6m)^2)
            casualty_area = (math.sqrt(max(0.01, area_proj * 0.3)) + 0.6) ** 2
        else:
            impact_ke = 0.0
            casualty_area = 0.0

        # NASA-STD-8719.14 Safety Rule
        is_safe = (casualty_area <= CASUALTY_AREA_LIMIT_M2) and (impact_ke <= CRITICAL_IMPACT_KINETIC_ENERGY_J)

        recommendation = (
            "SAFE_ATMOSPHERIC_INCINERATION"
            if is_safe
            else "MANDATORY_POINT_NEMO_TARGETING"
        )

        return ReentryDemiseResult(
            target_name=debris.name,
            initial_mass_kg=round(total_mass, 2),
            total_surviving_mass_kg=round(total_surviving_mass, 2),
            mass_demised_fraction_percent=round(demised_fraction_pct, 1),
            peak_heat_flux_mw_m2=round(peak_heat_flux / 1e6, 2),
            peak_deceleration_g=round(peak_decel, 1),
            breakup_altitude_km=round(breakup_altitude, 1),
            estimated_casualty_area_m2=round(casualty_area, 2),
            ground_impact_kinetic_energy_j=round(impact_ke, 1),
            is_safe_demise=is_safe,
            disposal_recommendation=recommendation,
            component_breakdown=component_results,
            altitude_profile_km=alt_history,
            heat_flux_profile_kw_m2=q_history,
            temperature_profile_k=temp_history
        )
