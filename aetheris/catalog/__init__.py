"""
Catalog & Characterization Package for AETHERIS-ADR.
"""

from aetheris.catalog.debris_object import (
    DebrisObject,
    ObjectType,
    OrbitRegime,
    MaterialFraction
)
from aetheris.catalog.characterization import (
    estimate_ballistic_coefficient_from_bstar,
    classify_object_by_name_and_orbit,
    estimate_physical_properties
)
from aetheris.catalog.catalog_manager import (
    CatalogManager,
    KNOWN_BENCHMARK_DEBRIS
)

__all__ = [
    "DebrisObject",
    "ObjectType",
    "OrbitRegime",
    "MaterialFraction",
    "estimate_ballistic_coefficient_from_bstar",
    "classify_object_by_name_and_orbit",
    "estimate_physical_properties",
    "CatalogManager",
    "KNOWN_BENCHMARK_DEBRIS",
]
