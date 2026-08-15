"""
Published Aerospace ADR Mission Benchmark Cases for External Ground-Truth Validation.
Sources:
1. ESA e.Deorbit Study (CDF-134(A) & CDF-150(A)): Active deorbit of ENVISAT (768 km, 98.54° SSO, 8211 kg).
2. Castronuovo (2011), "Active space debris removal: a preliminary mission analysis", Acta Astronautica:
   Removal of 5 Sun-Synchronous Russian SL-16 / Cosmos Upper Stages via J2 nodal drift sequencing.
3. Bonnal et al. (2013), "Active debris removal: Recent progress and remaining challenges", Acta Astronautica.
"""

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class PublishedMissionBenchmark:
    study_name: str
    target_name: str
    target_altitude_km: float
    target_inclination_deg: float
    target_mass_kg: float
    target_count: int
    published_total_delta_v_ms: float      # Published mission Delta-V budget [m/s]
    published_deorbit_delta_v_ms: float    # Published single-target deorbit retro-burn [m/s]
    published_drift_duration_days_per_target: float  # Published J2 drift phase duration [days]
    published_propellant_fraction_percent: float     # m_prop / m_wet [%]
    published_servicer_dry_mass_kg: float
    published_isp_sec: float
    citation: str


# Reference Benchmark 1: ESA e.Deorbit Study (Envisat Single-Target Direct Controlled Reentry)
BENCHMARK_ESA_E_DEORBIT = PublishedMissionBenchmark(
    study_name="ESA e.Deorbit Phase B1 Study (CDF-150(A))",
    target_name="ENVISAT (NORAD 27386)",
    target_altitude_km=768.0,
    target_inclination_deg=98.54,
    target_mass_kg=8211.0,
    target_count=1,
    published_total_delta_v_ms=285.0,  # ~215 m/s deorbit + ~70 m/s phasing/rendezvous
    published_deorbit_delta_v_ms=215.0, # Retrograde burn to drop perigee to <50 km
    published_drift_duration_days_per_target=0.0,
    published_propellant_fraction_percent=42.0,
    published_servicer_dry_mass_kg=1400.0,
    published_isp_sec=320.0,
    citation="ESA CDF-150(A) e.Deorbit Assessment Study Report (2015)"
)

# Reference Benchmark 2: Castronuovo Multi-Target SL-16 Upper Stage Tour Study (5 Targets)
BENCHMARK_CASTRONUOVO_5_TARGET_TOUR = PublishedMissionBenchmark(
    study_name="Castronuovo Multi-Target ADR Mission Analysis (Acta Astronautica 2011)",
    target_name="SL-16 Upper Stage Cluster (5 Rocket Bodies at 840 km / 71°)",
    target_altitude_km=840.0,
    target_inclination_deg=71.0,
    target_mass_kg=9000.0,
    target_count=5,
    published_total_delta_v_ms=2450.0, # Cumulative for 5 targets using J2 drift
    published_deorbit_delta_v_ms=225.0, # per target
    published_drift_duration_days_per_target=32.0, # Average 30-35 days drift per 10-15° RAAN
    published_propellant_fraction_percent=55.0,
    published_servicer_dry_mass_kg=650.0,
    published_isp_sec=325.0,
    citation="Castronuovo, M. M. (2011). 'Active space debris removal: a preliminary mission analysis'. Acta Astronautica, 69(9-10), 848-859."
)
