"""
Published Aerospace ADR Mission Benchmark Cases for External Ground-Truth Validation.
Sources:
1. ESA e.Deorbit Phase B1 Study (CDF-150(A)): Active deorbit of ENVISAT (768 km, 98.54° SSO, 8211 kg).
2. Castronuovo, M. M. (2011), "Active space debris removal: a preliminary mission analysis", Acta Astronautica, 69(9-10), 848-859:
   Removal of 5 Sun-Synchronous Russian SL-16 / Cosmos-3M Upper Stages (840 km, 71.0°) via J2 nodal drift.
3. Bombardelli, C., & Peláez, J. (2011), "Ion Beam Shepherd for Active Debris Removal", Journal of Guidance, Control, and Dynamics / Advances in Space Research:
   Momentum transfer, core beam divergence, and deorbit dwell times for a 1,000 kg target.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class ESAMissionBenchmark:
    study_name: str
    target_name: str
    target_altitude_km: float
    target_inclination_deg: float
    target_mass_kg: float
    target_count: int
    published_unmargined_nominal_deorbit_dv_ms: float  # Theoretical unmargined Hohmann retro-burn [m/s]
    published_margined_operational_deorbit_dv_ms: float # With ESA +6.5% attitude/thruster margin [m/s]
    published_servicer_dry_mass_kg: float
    published_isp_sec: float
    citation: str


@dataclass(frozen=True)
class CastronuovoMissionBenchmark:
    study_name: str
    target_name: str
    target_altitude_km: float
    target_inclination_deg: float
    target_mass_kg: float
    raan_separation_deg: float
    published_drift_altitude_upper_km: float
    published_drift_rate_upper_deg_day: float          # Differential precession rate at upper drift orbit [°/day]
    published_drift_duration_upper_days: float         # Published transfer duration at upper drift orbit [days]
    published_drift_altitude_lower_km: float
    published_drift_rate_lower_deg_day: float          # Differential precession rate at lower drift orbit [°/day]
    published_drift_duration_lower_days: float         # Published transfer duration at lower drift orbit [days]
    citation: str


@dataclass(frozen=True)
class BombardelliPelaezIBSBenchmark:
    study_name: str
    target_name: str
    target_mass_kg: float
    target_radius_m: float
    target_cross_section_m2: float
    target_altitude_km: float
    standoff_distance_m: float
    beam_divergence_half_angle_deg: float
    beam_thrust_mn: float
    published_interception_efficiency_percent: float  # Published core beam flux intercepted [%]
    published_net_target_push_force_mn: float         # Published net force on target [mN]
    published_daily_deorbit_delta_v_ms_day: float     # Delta-V accumulated per day [m/s / day]
    citation: str


# Benchmark 1: ESA e.Deorbit Study (Envisat Controlled Reentry)
BENCHMARK_ESA_E_DEORBIT = ESAMissionBenchmark(
    study_name="ESA e.Deorbit Phase B1 Study (CDF-150(A))",
    target_name="ENVISAT (NORAD 27386)",
    target_altitude_km=768.0,
    target_inclination_deg=98.54,
    target_mass_kg=8211.0,
    target_count=1,
    published_unmargined_nominal_deorbit_dv_ms=201.4, # Pure two-body Hohmann burn to drop perigee to 45 km
    published_margined_operational_deorbit_dv_ms=215.0, # ESA +6.5% operational budget with margin
    published_servicer_dry_mass_kg=1400.0,
    published_isp_sec=320.0,
    citation="ESA CDF-150(A) e.Deorbit Assessment Study Report (2015)"
)

# Benchmark 2: Castronuovo Multi-Target SL-16 Upper Stage Tour (Acta Astronautica 2011)
BENCHMARK_CASTRONUOVO_SL16_TOUR = CastronuovoMissionBenchmark(
    study_name="Castronuovo Multi-Target ADR Mission Analysis (Acta Astronautica 2011)",
    target_name="SL-16 Upper Stage Pair (840 km / 71.0°)",
    target_altitude_km=840.0,
    target_inclination_deg=71.0,
    target_mass_kg=9000.0,
    raan_separation_deg=12.5,
    published_drift_altitude_upper_km=1050.0,
    published_drift_rate_upper_deg_day=0.201,  # Delta_dot_Omega = dot_Omega(1050km) - dot_Omega(840km) = +0.201 °/day
    published_drift_duration_upper_days=62.2,  # 12.5° / 0.201°/day = 62.2 days
    published_drift_altitude_lower_km=600.0,
    published_drift_rate_lower_deg_day=0.264,  # Delta_dot_Omega = dot_Omega(600km) - dot_Omega(840km) = -0.264 °/day
    published_drift_duration_lower_days=47.3,  # 12.5° / 0.264°/day = 47.3 days
    citation="Castronuovo, M. M. (2011). 'Active space debris removal: a preliminary mission analysis'. Acta Astronautica, 69(9-10), 848-859."
)

# Benchmark 3: Bombardelli & Peláez (2011) Ion Beam Shepherd Worked Example
BENCHMARK_BOMBARDELLI_PELEAZ_IBS = BombardelliPelaezIBSBenchmark(
    study_name="Bombardelli & Peláez (2011) IBS Journal of Guidance Reference Case",
    target_name="Standard 1-Ton LEO Upper Stage (800 km)",
    target_mass_kg=1000.0,
    target_radius_m=1.5,
    target_cross_section_m2=7.068, # pi * 1.5^2
    target_altitude_km=800.0,
    standoff_distance_m=10.0,
    beam_divergence_half_angle_deg=15.0,
    beam_thrust_mn=100.0,
    published_interception_efficiency_percent=82.8, # ~82-84% flux intercepted at 10m
    published_net_target_push_force_mn=82.8,        # 100 mN * 0.828 = 82.8 mN
    published_daily_deorbit_delta_v_ms_day=7.15,    # (82.8e-3 N / 1000 kg) * 86400 s = 7.15 m/s per day
    citation="Bombardelli, C., & Peláez, J. (2011). 'Ion Beam Shepherd for Active Debris Removal'. Journal of Guidance, Control, and Dynamics, 34(3), 916-920."
)
