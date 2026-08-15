"""
Autonomous Disposal, Deorbit Propulsion & Aerothermal Reentry Package for AETHERIS-ADR.
"""

from aetheris.disposal.ion_beam_shepherd import (
    IonBeamShepherdEngine,
    IonBeamDeorbitResult
)
from aetheris.disposal.chaser_propulsion import (
    ChaserPropulsionEngine,
    ImpulsiveDeorbitResult,
    ElectricDeorbitResult
)
from aetheris.disposal.aerothermal_demise import (
    AerothermalDemiseSimulator,
    ReentryDemiseResult,
    MaterialDemiseStatus
)
from aetheris.disposal.point_nemo_targeter import (
    PointNemoTargeter,
    PointNemoDeorbitPlan,
    point_in_polygon
)

__all__ = [
    "IonBeamShepherdEngine",
    "IonBeamDeorbitResult",
    "ChaserPropulsionEngine",
    "ImpulsiveDeorbitResult",
    "ElectricDeorbitResult",
    "AerothermalDemiseSimulator",
    "ReentryDemiseResult",
    "MaterialDemiseStatus",
    "PointNemoTargeter",
    "PointNemoDeorbitPlan",
    "point_in_polygon",
]
