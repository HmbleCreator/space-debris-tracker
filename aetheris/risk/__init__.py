"""
Risk, Criticality, and Kessler Cascade Modeling Package for AETHERIS-ADR.
"""

from aetheris.risk.criticality import (
    compute_spatial_density_leo,
    estimate_fragmentation_yield,
    compute_debris_criticality,
    update_catalog_criticality_rankings
)
from aetheris.risk.kessler_simulator import (
    KesslerCascadeSimulator,
    KesslerScenarioResult,
    KesslerSimulationYear
)

__all__ = [
    "compute_spatial_density_leo",
    "estimate_fragmentation_yield",
    "compute_debris_criticality",
    "update_catalog_criticality_rankings",
    "KesslerCascadeSimulator",
    "KesslerScenarioResult",
    "KesslerSimulationYear",
]
