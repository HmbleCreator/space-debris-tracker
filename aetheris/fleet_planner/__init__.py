"""
Autonomous Fleet Mission Planner Package for AETHERIS-ADR.
"""

from aetheris.fleet_planner.transfer_cost import (
    compute_hohmann_transfer_delta_v,
    compute_direct_plane_change_delta_v,
    compute_combined_plane_change_hohmann_delta_v,
    compute_noncoplanar_direct_transfer,
    TransferCostBreakdown
)
from aetheris.fleet_planner.j2_drift_optimizer import (
    compute_j2_raan_precession_rate,
    optimize_j2_drift_transfer,
    J2DriftTransferPlan
)
from aetheris.fleet_planner.fleet_optimizer import (
    RobotSpacecraftSpec,
    MissionLeg,
    RobotMissionItinerary,
    FleetOptimizationResult,
    FleetMissionOptimizer
)

__all__ = [
    "compute_hohmann_transfer_delta_v",
    "compute_direct_plane_change_delta_v",
    "compute_combined_plane_change_hohmann_delta_v",
    "compute_noncoplanar_direct_transfer",
    "TransferCostBreakdown",
    "compute_j2_raan_precession_rate",
    "optimize_j2_drift_transfer",
    "J2DriftTransferPlan",
    "RobotSpacecraftSpec",
    "MissionLeg",
    "RobotMissionItinerary",
    "FleetOptimizationResult",
    "FleetMissionOptimizer",
]
