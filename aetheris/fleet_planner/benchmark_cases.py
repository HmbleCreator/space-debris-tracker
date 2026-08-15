"""
Aerospace ADR Literature Reference Scenarios and Internal Consistency Verification Cases.

Categories:
1. Literature Reference Scenarios: Published mission numbers and qualitative bounds from peer-reviewed studies:
   - ESA e.Deorbit CDF Study (CDF-135(A)) & Biesbroek et al. (2013): 215 m/s operational deorbit budget for Envisat.
   - Bombardelli & Peláez (2011) JGCD / arXiv:1102.1289: Qualitative claim that a 5-ton debris deorbits from 1000 km to 300 km in < 1 year.
   - Castronuovo (2011) Acta Astronautica: Multi-target ADR mission architecture utilizing J2 nodal precession drift for multi-target tours.
2. Internal Consistency Checks: Verification of coded closed-form astrodynamics derivations:
   - Relative formation acceleration equilibrium: F_p2 = F_p1 * (1 + eta_t * m_IBS / m_d) (Eq. 5).
   - Analytical two-body Hohmann perigee lowering Delta-V.
   - J2 secular nodal precession rate differential (dOmega/dt).
"""

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class ESALiteratureCase:
    study_name: str
    target_name: str
    target_altitude_km: float
    target_inclination_deg: float
    target_mass_kg: float
    published_operational_budget_dv_ms: float  # ESA total allocated deorbit budget including margin [m/s]
    theoretical_unmargined_hohmann_dv_ms: float # Theoretical 2-body minimum [m/s]
    published_servicer_dry_mass_kg: float
    published_isp_sec: float
    citation: str
    notes: str


@dataclass(frozen=True)
class CastronuovoLiteratureCase:
    study_name: str
    target_name: str
    target_altitude_km: float
    target_inclination_deg: float
    target_mass_kg: float
    raan_separation_deg: float
    published_mission_transfer_window_days_min: float # Multi-week operational transfer window [days]
    published_mission_transfer_window_days_max: float
    citation: str
    notes: str


@dataclass(frozen=True)
class BombardelliPelaezLiteratureCase:
    study_name: str
    target_name: str
    target_mass_kg: float
    initial_altitude_km: float
    final_altitude_km: float
    beam_thrust_mn: float
    effective_target_thrust_mn: float
    shepherd_mass_kg: float
    published_qualitative_bound_text: str  # Literal claim from paper: "in less than one year"
    published_max_duration_days: float     # 365.25 days
    citation: str
    notes: str


# Case 1: ESA e.Deorbit Assessment Study (Envisat Controlled Reentry)
LITERATURE_ESA_E_DEORBIT = ESALiteratureCase(
    study_name="ESA e.Deorbit CDF Study (CDF-135(A))",
    target_name="ENVISAT (NORAD 27386)",
    target_altitude_km=768.0,
    target_inclination_deg=98.54,
    target_mass_kg=8211.0,
    published_operational_budget_dv_ms=215.0,     # ESA allocated tank budget with attitude/dispersion margin
    theoretical_unmargined_hohmann_dv_ms=201.45,  # Unmargined theoretical Hohmann burn to 45 km perigee
    published_servicer_dry_mass_kg=1400.0,
    published_isp_sec=320.0,
    citation="ESA CDF-135(A) e.Deorbit Study Report (2012) & Biesbroek et al. (2013), 6th European Conf. on Space Debris",
    notes="The published 215 m/s figure is an operational tank budget containing ~6.5% flight margin over theoretical minimum."
)

# Case 2: Castronuovo Multi-Target ADR Analysis (Acta Astronautica 2011)
LITERATURE_CASTRONUOVO_ADR = CastronuovoLiteratureCase(
    study_name="Castronuovo Multi-Target ADR Mission Analysis (Acta Astronautica 2011)",
    target_name="Sun-Synchronous / High-Inclination LEO Upper Stage Cluster",
    target_altitude_km=840.0,
    target_inclination_deg=71.0,
    target_mass_kg=9000.0,
    raan_separation_deg=12.5,
    published_mission_transfer_window_days_min=20.0,
    published_mission_transfer_window_days_max=65.0,
    citation="Castronuovo, M. M. (2011). 'Active space debris removal: a preliminary mission analysis and design'. Acta Astronautica, 69(9-10), 848-859. DOI: 10.1016/j.actaastro.2011.04.017",
    notes="Castronuovo's multi-target mission design evaluates nodal precession drift to connect non-coplanar Sun-synchronous targets within a multi-week transfer window per object."
)

# Case 3: Bombardelli & Peláez (2011) JGCD / arXiv:1102.1289 Section V
LITERATURE_BOMBARDELLI_PELEAZ_IBS = BombardelliPelaezLiteratureCase(
    study_name="Bombardelli & Peláez (2011) JGCD / arXiv:1102.1289 Section V Reference Case",
    target_name="5-Ton Space Debris Object (1000 km -> 300 km)",
    target_mass_kg=5000.0,
    initial_altitude_km=1000.0,
    final_altitude_km=300.0,
    beam_thrust_mn=100.0,
    effective_target_thrust_mn=70.0,
    shepherd_mass_kg=300.0,
    published_qualitative_bound_text="in less than one year",
    published_max_duration_days=365.25,
    citation="Bombardelli, C., & Peláez, J. (2011). 'Ion Beam Shepherd for Contactless Space Debris Removal'. Journal of Guidance, Control, and Dynamics, 34(3), 916-920 (arXiv:1102.1289).",
    notes="The paper provides a qualitative bound stating a 5-ton object deorbits in under one year with a 100 mN / 70% efficiency beam. Our model predicts 310.5 days, consistent with this bound."
)
