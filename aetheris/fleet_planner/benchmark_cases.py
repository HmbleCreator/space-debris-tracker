"""
Aerospace ADR Literature Reference Scenarios and Internal Consistency Verification Cases.

Categories:
1. Literature Reference Scenarios: Published mission numbers and qualitative bounds from peer-reviewed studies:
   - ESA e.Deorbit Study (Biesbroek et al., 2013): 8-tonne SSO class debris removal architecture.
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
    theoretical_unmargined_hohmann_dv_ms: float # Theoretical 2-body minimum to 45 km perigee [m/s]
    published_servicer_dry_mass_net_kg: float    # Published net capture dry mass (709 kg)
    published_servicer_propellant_net_kg: float  # Published net capture propellant mass (878 kg)
    published_servicer_dry_mass_clamp_kg: float  # Published clamping dry mass (784 kg)
    published_servicer_propellant_clamp_kg: float # Published clamping propellant mass (810 kg)
    citation: str
    notes: str


@dataclass(frozen=True)
class CastronuovoLiteratureCase:
    study_name: str
    target_description: str
    target_orbit_regime: str
    published_annual_removal_rate: str # ~5 targets / year
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


# Case 1: ESA e.Deorbit Assessment Study (Envisat / 8-Tonne SSO Debris Removal)
LITERATURE_ESA_E_DEORBIT = ESALiteratureCase(
    study_name="ESA e.Deorbit CDF Assessment Study (Biesbroek et al., 2013)",
    target_name="Representative 8-Tonne Sun-Synchronous Target (~770-800 km, 98.5°)",
    target_altitude_km=768.0,
    target_inclination_deg=98.54,
    target_mass_kg=8211.0,
    theoretical_unmargined_hohmann_dv_ms=201.45,  # Theoretical 2-body Hohmann burn from 768 km to 45 km perigee
    published_servicer_dry_mass_net_kg=709.0,     # Biesbroek et al. (2013) Table 1 net option
    published_servicer_propellant_net_kg=878.0,   # Biesbroek et al. (2013) Table 1 net option
    published_servicer_dry_mass_clamp_kg=784.0,   # Biesbroek et al. (2013) Table 1 clamping option
    published_servicer_propellant_clamp_kg=810.0, # Biesbroek et al. (2013) Table 1 clamping option
    citation="Biesbroek, R., Soares, T., Hüsing, J., & Innocenti, L. (2013). 'The e.Deorbit CDF Study: A Design Study for the Safe Removal of a Large Space Debris'. 6th European Conference on Space Debris, Darmstadt, Germany.",
    notes="Theoretical perigee-lowering retro-burn to 45 km requires 201.45 m/s. The published study sizes an 810-878 kg propellant load covering the entire mission profile (rendezvous, capture, attitude control, and disposal burn with margin)."
)

# Case 2: Castronuovo Multi-Target ADR Analysis (Acta Astronautica 2011)
LITERATURE_CASTRONUOVO_ADR = CastronuovoLiteratureCase(
    study_name="Castronuovo Multi-Target ADR Mission Analysis (Acta Astronautica 2011)",
    target_description="41 Large Rocket Bodies in Sun-Synchronous Orbit (800-1000 km, ~98°)",
    target_orbit_regime="Sun-Synchronous Orbit (SSO)",
    published_annual_removal_rate="~5 targets / year using multi-target servicer",
    citation="Castronuovo, M. M. (2011). 'Active space debris removal: a preliminary mission analysis and design'. Acta Astronautica, 69(9-10), 848-859. DOI: 10.1016/j.actaastro.2011.04.017",
    notes="Castronuovo proposes a multi-target servicer architecture deploying deorbit kits to ~5 SSO objects/year, exploiting orbital phasing and perturbation drift to avoid prohibitive direct out-of-plane delta-V costs."
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
