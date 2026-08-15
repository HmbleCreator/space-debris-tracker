"""
Pydantic Request & Response Schemas for AETHERIS-ADR REST API.
"""

from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel, Field


class ObjectQueryRequest(BaseModel):
    regime: Optional[str] = None
    object_type: Optional[str] = None
    min_mass_kg: Optional[float] = None
    search_query: Optional[str] = None
    limit: int = Field(default=200, ge=1, le=2000)


class StatePredictionRequest(BaseModel):
    norad_id: int
    target_time_utc: Optional[str] = None
    use_high_precision_hpop: bool = False
    duration_seconds: float = 5400.0  # ~1 orbit
    step_seconds: float = 60.0


class J2DriftRequest(BaseModel):
    origin_norad_id: int
    target_norad_id: int
    max_drift_days: float = 60.0


class FleetOptimizationRequest(BaseModel):
    top_n_critical_targets: int = Field(default=15, ge=1, le=50)
    chaser_dry_mass_kg: float = 600.0
    chaser_propellant_capacity_kg: float = 800.0
    chaser_isp_seconds: float = 325.0
    capture_kit_capacity: int = 5
    max_robots_allowed: int = 10


class AerothermalReentryRequest(BaseModel):
    norad_id: int
    entry_gamma_deg: float = -2.5
    entry_velocity_kms: float = 7.6


class PointNemoDeorbitRequest(BaseModel):
    norad_id: int
    chaser_mass_kg: float = 600.0
    isp_seconds: float = 320.0
    thrust_newtons: float = 450.0


class KesslerSimRequest(BaseModel):
    scenario_name: str = "Active Debris Removal (10 targets/year)"
    adr_removal_rate_per_year: int = 10
    pmd_compliance_rate: float = 0.90
    sim_years: int = 30
