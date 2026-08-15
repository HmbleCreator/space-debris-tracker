"""
Dynamics & Astrodynamic Propagation Package for AETHERIS-ADR.
"""

from aetheris.dynamics.atmospheric_models import (
    get_atmospheric_density,
    compute_drag_acceleration,
    ATMOSPHERE_TABLE
)
from aetheris.dynamics.gravity_harmonics import compute_geopotential_acceleration
from aetheris.dynamics.sgp4_propagator import FastPropagator
from aetheris.dynamics.numerical_propagator import (
    NumericalPropagator,
    HPOPConfig,
    TrajectoryPoint
)
from aetheris.dynamics.conjunction import (
    ConjunctionEvent,
    compute_2d_collision_probability,
    assess_conjunction
)

__all__ = [
    "get_atmospheric_density",
    "compute_drag_acceleration",
    "ATMOSPHERE_TABLE",
    "compute_geopotential_acceleration",
    "FastPropagator",
    "NumericalPropagator",
    "HPOPConfig",
    "TrajectoryPoint",
    "ConjunctionEvent",
    "compute_2d_collision_probability",
    "assess_conjunction",
]
