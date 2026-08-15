"""
Physical, Astrodynamical, and Atmospheric Constants for AETHERIS-ADR.
References: WGS-84, EGM2008, IERS Conventions, NASA-STD-8719.14.
"""

from dataclasses import dataclass
from typing import Dict

# ---------------------------------------------------------------------------
# Earth Gravitational & Geodetic Parameters (WGS-84 / EGM2008)
# ---------------------------------------------------------------------------
# Standard gravitational parameter of Earth (m^3 / s^2)
MU_EARTH: float = 3.986004418e14  # m^3/s^2
MU_EARTH_KM3: float = 3.986004418e5  # km^3/s^2

# Earth equatorial radius (meters and km)
R_EARTH: float = 6378137.0  # m
R_EARTH_KM: float = 6378.137  # km

# Earth polar radius (meters and km)
R_EARTH_POLAR: float = 6356752.3142  # m

# Earth flattening
FLATTENING_EARTH: float = 1.0 / 298.257223563

# Earth rotational angular velocity (rad/s)
OMEGA_EARTH: float = 7.2921150e-5  # rad/s

# Standard acceleration due to gravity (m/s^2)
G0: float = 9.80665  # m/s^2

# Earth Geopotential Zonal Harmonics (un-normalized, EGM2008)
J2: float = 1.08262668e-3
J3: float = -2.53265649e-6
J4: float = -1.61962159e-6
J5: float = -2.27296082e-7
J6: float = 5.40681239e-7

# ---------------------------------------------------------------------------
# Astronomical & Solar System Constants
# ---------------------------------------------------------------------------
# Astronomical Unit (meters and km)
AU_METERS: float = 149597870700.0  # m
AU_KM: float = 149597870.7  # km

# Speed of light (m/s)
SPEED_OF_LIGHT: float = 299792458.0  # m/s

# Solar Radiation Pressure at 1 AU (N/m^2)
SOLAR_FLUX_1AU: float = 1361.0  # W/m^2
SOLAR_RADIATION_PRESSURE_1AU: float = SOLAR_FLUX_1AU / SPEED_OF_LIGHT  # ~4.54e-6 N/m^2

# Gravitational parameters of third bodies (m^3/s^2)
MU_SUN: float = 1.32712440018e20  # m^3/s^2
MU_MOON: float = 4.9048695e12     # m^3/s^2

# ---------------------------------------------------------------------------
# Atmospheric & Reentry Constants
# ---------------------------------------------------------------------------
# Reentry interface altitude (km & meters)
REENTRY_INTERFACE_ALT_KM: float = 120.0
REENTRY_INTERFACE_ALT_M: float = 120000.0

# Standard sea-level atmospheric density (kg/m^3)
RHO_0: float = 1.225  # kg/m^3

# Atmospheric scale height for simple exponential model (m)
H_SCALE_LEO: float = 8500.0  # m

# Detra-Kemp-Riddell / Fay-Riddell reference stagnation heating constant
# q = C_DKR * sqrt(rho / R_eff) * V^3 (W/m^2 with rho in kg/m^3, R_eff in m, V in m/s)
C_DKR: float = 1.7415e-4  # W / (m^2 * (kg/m^3)^0.5 * (m/s)^3 * m^-0.5)

# NASA Safety Standards (NASA-STD-8719.14) Thresholds
CASUALTY_RISK_THRESHOLD: float = 1.0e-4  # 1 in 10,000 threshold
CASUALTY_AREA_LIMIT_M2: float = 8.0     # m^2
CRITICAL_IMPACT_KINETIC_ENERGY_J: float = 15.0  # Joules

# ---------------------------------------------------------------------------
# Oceanic Disposal Zone: South Pacific Ocean Uninhabited Area (SPOUA / Point Nemo)
# ---------------------------------------------------------------------------
# Point Nemo exact coordinates
POINT_NEMO_LAT_DEG: float = -48.876667  # 48°52.6' S
POINT_NEMO_LON_DEG: float = -123.393333 # 123°23.6' W

# SPOUA Safety Corridor Bounding Polygon (Lat, Lon pairs in degrees)
SPOUA_CORRIDOR_POLYGON = [
    (-35.0, -150.0),
    (-35.0, -100.0),
    (-55.0, -100.0),
    (-60.0, -140.0),
    (-50.0, -160.0),
    (-35.0, -150.0)
]


# ---------------------------------------------------------------------------
# Aerothermal Demise Material Properties
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class MaterialProperties:
    name: str
    density: float          # kg/m^3
    melting_temp: float     # K
    specific_heat: float    # J / (kg * K)
    latent_heat_fusion: float  # J / kg
    emissivity: float       # surface emissivity [0, 1]
    demise_difficulty: str  # "Low", "Moderate", "High", "Refractory"


MATERIAL_DATABASE: Dict[str, MaterialProperties] = {
    "ALUMINUM_6061": MaterialProperties(
        name="Aluminum 6061-T6",
        density=2700.0,
        melting_temp=855.0,
        specific_heat=896.0,
        latent_heat_fusion=397000.0,
        emissivity=0.25,
        demise_difficulty="Low"
    ),
    "ALUMINUM_7075": MaterialProperties(
        name="Aluminum 7075",
        density=2810.0,
        melting_temp=890.0,
        specific_heat=960.0,
        latent_heat_fusion=380000.0,
        emissivity=0.25,
        demise_difficulty="Low"
    ),
    "TITANIUM_TI6AL4V": MaterialProperties(
        name="Titanium Ti-6Al-4V",
        density=4430.0,
        melting_temp=1933.0,
        specific_heat=526.0,
        latent_heat_fusion=290000.0,
        emissivity=0.55,
        demise_difficulty="High"
    ),
    "STAINLESS_STEEL_304": MaterialProperties(
        name="Stainless Steel 304",
        density=8000.0,
        melting_temp=1673.0,
        specific_heat=500.0,
        latent_heat_fusion=268000.0,
        emissivity=0.60,
        demise_difficulty="High"
    ),
    "CARBON_COMPOSITE_CFRP": MaterialProperties(
        name="Carbon Fiber Reinforced Polymer",
        density=1550.0,
        melting_temp=3800.0,  # Sublimation / decomposition
        specific_heat=1130.0,
        latent_heat_fusion=30000000.0, # High sublimation enthalpy
        emissivity=0.85,
        demise_difficulty="Refractory"
    ),
    "BERYLLIUM": MaterialProperties(
        name="Beryllium",
        density=1850.0,
        melting_temp=1560.0,
        specific_heat=1825.0,
        latent_heat_fusion=1357000.0,
        emissivity=0.35,
        demise_difficulty="High"
    ),
    "INCONEL_718": MaterialProperties(
        name="Inconel 718 Superalloy",
        density=8190.0,
        melting_temp=1609.0,
        specific_heat=435.0,
        latent_heat_fusion=210000.0,
        emissivity=0.70,
        demise_difficulty="High"
    ),
}
