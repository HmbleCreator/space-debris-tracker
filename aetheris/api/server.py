"""
FastAPI Server for AETHERIS-ADR Platform.
Provides RESTful endpoints and WebSocket streaming for real-time astrodynamics, fleet planning, and reentry ops.
"""

import asyncio
from datetime import datetime, timezone
import json
import os
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from aetheris.catalog.catalog_manager import CatalogManager
from aetheris.catalog.debris_object import ObjectType, OrbitRegime
from aetheris.core.orbital_elements import keplerian_to_cartesian
from aetheris.disposal.aerothermal_demise import AerothermalDemiseSimulator
from aetheris.disposal.chaser_propulsion import ChaserPropulsionEngine
from aetheris.disposal.point_nemo_targeter import PointNemoTargeter
from aetheris.dynamics.numerical_propagator import HPOPConfig, NumericalPropagator
from aetheris.dynamics.sgp4_propagator import FastPropagator
from aetheris.fleet_planner.fleet_optimizer import (
    FleetMissionOptimizer,
    RobotSpacecraftSpec
)
from aetheris.fleet_planner.j2_drift_optimizer import optimize_j2_drift_transfer
from aetheris.risk.criticality import update_catalog_criticality_rankings
from aetheris.risk.kessler_simulator import KesslerCascadeSimulator
from aetheris.api.schemas import (
    AerothermalReentryRequest,
    FleetOptimizationRequest,
    J2DriftRequest,
    KesslerSimRequest,
    ObjectQueryRequest,
    PointNemoDeorbitRequest,
    StatePredictionRequest
)


# Initialize global state and catalog
catalog_mgr = CatalogManager()
# Compute criticality rankings on initialization
ranked_objects = update_catalog_criticality_rankings(list(catalog_mgr.objects.values()))
demise_sim = AerothermalDemiseSimulator()
kessler_sim = KesslerCascadeSimulator()

app = FastAPI(
    title="AETHERIS-ADR Astrodynamics & Mission Ops API",
    description="High-fidelity space debris tracking, risk evaluation, fleet mission planner, and Point Nemo deorbit engine.",
    version="1.0.0"
)

# CORS middleware for Web client
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health_check():
    return {
        "status": "ONLINE",
        "system": "AETHERIS-ADR",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_catalog_objects": catalog_mgr.total_count,
        "high_criticality_targets": len([o for o in catalog_mgr.objects.values() if o.criticality_score >= 50.0])
    }


@app.get("/api/catalog")
async def get_catalog(
    regime: Optional[str] = None,
    object_type: Optional[str] = None,
    min_mass_kg: Optional[float] = None,
    search_query: Optional[str] = None,
    limit: int = 300
):
    """Retrieve catalog objects with optional filtering."""
    regime_enum = OrbitRegime(regime) if regime else None
    type_enum = ObjectType(object_type) if object_type else None

    objs = catalog_mgr.list_objects(
        regime=regime_enum,
        obj_type=type_enum,
        min_mass_kg=min_mass_kg,
        search_query=search_query,
        limit=limit
    )
    return {
        "total_returned": len(objs),
        "total_in_catalog": catalog_mgr.total_count,
        "objects": [o.to_dict() for o in objs]
    }


@app.get("/api/catalog/{norad_id}")
async def get_object_detail(norad_id: int):
    """Retrieve single object details by NORAD ID."""
    obj = catalog_mgr.get_object(norad_id)
    if not obj:
        raise HTTPException(status_code=404, detail=f"NORAD ID {norad_id} not found in catalog.")
    return obj.to_dict()


@app.post("/api/predict")
async def predict_object_state(req: StatePredictionRequest):
    """
    Predict object state vector (r, v, a) and geodetic coords at target time.
    Supports instant analytical SGP4/J2 or high-precision numerical HPOP integration.
    """
    obj = catalog_mgr.get_object(req.norad_id)
    if not obj:
        raise HTTPException(status_code=404, detail=f"NORAD ID {req.norad_id} not found.")

    target_time = (
        datetime.fromisoformat(req.target_time_utc.replace("Z", "+00:00"))
        if req.target_time_utc
        else datetime.now(timezone.utc)
    )

    if not req.use_high_precision_hpop:
        # Instant Analytical SGP4/J2 Secular Prediction
        state = FastPropagator.propagate_object_state(obj, target_time)
        return {
            "mode": "FAST_ANALYTICAL_SGP4_J2",
            "state": state
        }
    else:
        # Numerical HPOP Integration over duration
        r0, v0 = keplerian_to_cartesian(obj.keplerian)
        config = HPOPConfig(
            max_zonal_harmonics=4,
            include_drag=True,
            include_srp=True,
            include_third_body=True,
            area_m2=obj.cross_sectional_area_m2,
            mass_kg=obj.estimated_mass_kg,
            cd_drag=obj.drag_coefficient_cd
        )
        propagator = NumericalPropagator(config)
        trajectory = propagator.propagate(
            r0_eci=r0,
            v0_eci=v0,
            start_epoch=target_time,
            duration_seconds=req.duration_seconds,
            step_seconds=req.step_seconds
        )

        ephemeris = [
            {
                "time_sec": p.time_seconds,
                "datetime_utc": p.datetime_utc.isoformat(),
                "position_eci_km": (p.position_eci_m / 1000.0).tolist(),
                "velocity_eci_kms": (p.velocity_eci_ms / 1000.0).tolist(),
                "altitude_km": round(p.altitude_km, 2),
                "latitude_deg": round(p.latitude_deg, 4),
                "longitude_deg": round(p.longitude_deg, 4),
                "speed_kms": round(p.speed_kms, 3),
                "specific_energy_j_kg": round(p.specific_energy_j_kg, 2)
            }
            for p in trajectory
        ]

        return {
            "mode": "NUMERICAL_HPOP_COWELL_RK45",
            "norad_id": obj.norad_id,
            "name": obj.name,
            "points_count": len(ephemeris),
            "trajectory": ephemeris
        }


@app.get("/api/criticality/ranking")
async def get_criticality_ranking(limit: int = 25):
    """Retrieve ranked queue of highest-criticality space debris objects."""
    all_objs = list(catalog_mgr.objects.values())
    ranked = sorted(all_objs, key=lambda o: o.criticality_score, reverse=True)[:limit]
    return {
        "ranked_targets": [o.to_dict() for o in ranked]
    }


@app.post("/api/kessler/simulate")
async def simulate_kessler_cascade(req: KesslerSimRequest):
    """Simulate multi-decade orbital collision cascade with custom ADR removal cadence."""
    result = kessler_sim.simulate_scenario(
        scenario_name=req.scenario_name,
        adr_removal_rate_per_year=req.adr_removal_rate_per_year,
        pmd_compliance_rate=req.pmd_compliance_rate,
        sim_years=req.sim_years
    )

    # Also compute baseline (No ADR) for comparison
    baseline_result = kessler_sim.simulate_scenario(
        scenario_name="Baseline (No Active Debris Removal)",
        adr_removal_rate_per_year=0,
        pmd_compliance_rate=req.pmd_compliance_rate,
        sim_years=req.sim_years
    )

    return {
        "scenario": {
            "name": result.scenario_name,
            "adr_rate": result.adr_removal_rate_per_year,
            "pmd_rate": result.pmd_compliance_rate,
            "years": result.years,
            "total_population": result.total_population_trajectory,
            "cumulative_collisions": result.cumulative_collisions_trajectory,
            "annual_data": [
                {
                    "year": d.year,
                    "intact": d.intact_satellites,
                    "large_debris": d.large_debris,
                    "fragments": d.small_fragments,
                    "total": d.total_objects,
                    "annual_collisions": d.annual_collisions,
                    "cum_collisions": d.cumulative_collisions,
                    "risk_level": d.risk_level
                }
                for d in result.annual_data
            ],
            "risk_reduction_pct": result.risk_reduction_percent
        },
        "baseline": {
            "name": baseline_result.scenario_name,
            "years": baseline_result.years,
            "total_population": baseline_result.total_population_trajectory,
            "cumulative_collisions": baseline_result.cumulative_collisions_trajectory
        }
    }


@app.post("/api/j2_drift/optimize")
async def optimize_j2_drift(req: J2DriftRequest):
    """Compute optimal J2 nodal precession drift transfer between two orbital objects."""
    obj_a = catalog_mgr.get_object(req.origin_norad_id)
    obj_b = catalog_mgr.get_object(req.target_norad_id)

    if not obj_a or not obj_b:
        raise HTTPException(status_code=404, detail="Origin or target object not found in catalog.")

    plan = optimize_j2_drift_transfer(
        obj_a.keplerian,
        obj_b.keplerian,
        max_drift_days=req.max_drift_days
    )

    return {
        "origin": {"norad_id": obj_a.norad_id, "name": obj_a.name, "raan_deg": round(math.degrees(obj_a.keplerian.raan), 2)},
        "target": {"norad_id": obj_b.norad_id, "name": obj_b.name, "raan_deg": round(math.degrees(obj_b.keplerian.raan), 2)},
        "plan": {
            "origin_raan_deg": plan.origin_raan_deg,
            "target_raan_deg": plan.target_raan_deg,
            "raan_difference_deg": plan.raan_difference_deg,
            "drift_altitude_km": plan.drift_altitude_km,
            "drift_duration_days": plan.drift_duration_days,
            "delta_v_to_drift_ms": plan.delta_v_to_drift_ms,
            "delta_v_from_drift_ms": plan.delta_v_from_drift_ms,
            "delta_v_plane_trim_ms": plan.delta_v_plane_trim_ms,
            "delta_v_phasing_ms": plan.delta_v_phasing_ms,
            "delta_v_total_ms": plan.delta_v_total_ms,
            "direct_impulsive_delta_v_ms": plan.direct_impulsive_delta_v_ms,
            "propellant_savings_percent": plan.propellant_savings_percent
        }
    }


@app.post("/api/fleet/optimize")
async def optimize_fleet_mission(req: FleetOptimizationRequest):
    """
    Solve for the minimum number of robotic chasers (K_min) and multi-target cleanup tours.
    """
    all_objs = list(catalog_mgr.objects.values())
    top_targets = sorted(all_objs, key=lambda o: o.criticality_score, reverse=True)[:req.top_n_critical_targets]

    spec = RobotSpacecraftSpec(
        robot_id="ADR-SERVICER",
        robot_name="Aetheris Servicer",
        dry_mass_kg=req.chaser_dry_mass_kg,
        propellant_capacity_kg=req.chaser_propellant_capacity_kg,
        specific_impulse_sec=req.chaser_isp_seconds,
        capture_kit_payload_capacity=req.capture_kit_capacity
    )

    optimizer = FleetMissionOptimizer(robot_spec=spec)
    result = optimizer.optimize_fleet(
        targets=top_targets,
        max_robots_allowed=req.max_robots_allowed
    )

    return {
        "summary": {
            "total_targets_requested": result.total_targets_requested,
            "total_targets_cleaned": result.total_targets_cleaned,
            "minimum_robots_needed": result.minimum_robots_needed,
            "fleet_total_propellant_used_kg": result.fleet_total_propellant_used_kg,
            "fleet_total_delta_v_ms": result.fleet_total_delta_v_ms,
            "mean_mission_duration_days": result.mean_mission_duration_days,
            "average_propellant_savings_percent": result.average_propellant_savings_vs_direct_pct
        },
        "robots": [
            {
                "robot_id": r.robot_id,
                "robot_name": r.robot_name,
                "assigned_targets": r.assigned_targets,
                "targets_removed_count": r.targets_removed_count,
                "total_delta_v_ms": r.total_delta_v_ms,
                "total_propellant_used_kg": r.total_propellant_used_kg,
                "final_remaining_propellant_kg": r.final_remaining_propellant_kg,
                "total_mission_duration_days": r.total_mission_duration_days,
                "fuel_margin_percent": r.fuel_margin_percent,
                "legs": [
                    {
                        "leg_index": l.leg_index,
                        "action_type": l.action_type,
                        "target_norad_id": l.target_norad_id,
                        "target_name": l.target_name,
                        "start_time_days": l.start_time_days,
                        "duration_days": l.duration_days,
                        "delta_v_ms": l.delta_v_ms,
                        "propellant_used_kg": l.propellant_used_kg,
                        "remaining_propellant_kg": l.remaining_propellant_kg,
                        "description": l.description
                    }
                    for l in r.legs
                ]
            }
            for r in result.robot_itineraries
        ],
        "unserviced_targets": result.unserviced_targets
    }


@app.post("/api/reentry/aerothermal")
async def simulate_aerothermal_demise(req: AerothermalReentryRequest):
    """Simulate aerothermal demise and material survivability for chosen debris."""
    obj = catalog_mgr.get_object(req.norad_id)
    if not obj:
        raise HTTPException(status_code=404, detail=f"NORAD ID {req.norad_id} not found.")

    res = demise_sim.simulate_entry_demise(
        debris=obj,
        entry_gamma_deg=req.entry_gamma_deg,
        entry_velocity_kms=req.entry_velocity_kms
    )

    return {
        "target_name": res.target_name,
        "initial_mass_kg": res.initial_mass_kg,
        "total_surviving_mass_kg": res.total_surviving_mass_kg,
        "mass_demised_percent": res.mass_demised_fraction_percent,
        "peak_heat_flux_mw_m2": res.peak_heat_flux_mw_m2,
        "peak_deceleration_g": res.peak_deceleration_g,
        "breakup_altitude_km": res.breakup_altitude_km,
        "estimated_casualty_area_m2": res.estimated_casualty_area_m2,
        "ground_impact_ke_joules": res.ground_impact_kinetic_energy_j,
        "is_safe_demise": res.is_safe_demise,
        "disposal_recommendation": res.disposal_recommendation,
        "components": [
            {
                "material": c.material_name,
                "initial_kg": c.initial_mass_kg,
                "surviving_kg": c.surviving_mass_kg,
                "demise_altitude_km": c.demise_altitude_km,
                "survived": c.survived,
                "temp_k": c.temperature_k,
                "melting_pt_k": c.melting_point_k
            }
            for c in res.component_breakdown
        ],
        "profile": {
            "altitude_km": res.altitude_profile_km,
            "heat_flux_kw_m2": res.heat_flux_profile_kw_m2,
            "temperature_k": res.temperature_profile_k
        }
    }


@app.post("/api/reentry/point_nemo")
async def plan_point_nemo_targeting(req: PointNemoDeorbitRequest):
    """Compute controlled deorbit burn into Point Nemo (SPOUA) with 3-Sigma dispersion ellipse."""
    obj = catalog_mgr.get_object(req.norad_id)
    if not obj:
        raise HTTPException(status_code=404, detail=f"NORAD ID {req.norad_id} not found.")

    plan = PointNemoTargeter.plan_point_nemo_deorbit(
        debris=obj,
        chaser_mass_kg=req.chaser_mass_kg,
        isp_seconds=req.isp_seconds,
        thrust_newtons=req.thrust_newtons
    )

    return {
        "target_name": plan.target_name,
        "norad_id": plan.target_norad_id,
        "burn_timestamp_utc": plan.burn_timestamp_utc,
        "delta_v_ms": plan.burn_magnitude_delta_v_ms,
        "burn_direction_eci": plan.burn_direction_vector_eci,
        "burn_duration_seconds": plan.burn_duration_seconds,
        "propellant_required_kg": plan.propellant_required_kg,
        "entry_flight_path_angle_deg": plan.entry_interface_flight_path_angle_deg,
        "impact_point": {
            "latitude_deg": plan.nominal_impact_latitude_deg,
            "longitude_deg": plan.nominal_impact_longitude_deg,
            "name": "Point Nemo (SPOUA Oceanic Pole of Inaccessibility)"
        },
        "dispersion_ellipse": {
            "along_track_sigma_km": plan.dispersion_ellipse_along_track_km,
            "cross_track_sigma_km": plan.dispersion_ellipse_cross_track_km,
            "azimuth_deg": plan.ellipse_azimuth_deg
        },
        "is_contained_in_spoua_polygon": plan.is_contained_in_spoua_polygon,
        "ground_track": plan.ground_track_coordinates,
        "spoua_safety_polygon": plan.spoua_safety_polygon
    }


@app.websocket("/ws/telemetry")
async def websocket_telemetry_stream(websocket: WebSocket):
    """Real-time WebSocket streaming of orbital positions and telemetry."""
    await websocket.accept()
    try:
        # Stream top 60 high-criticality objects with updated positions every second
        all_objs = list(catalog_mgr.objects.values())
        stream_subset = sorted(all_objs, key=lambda o: o.criticality_score, reverse=True)[:60]

        while True:
            now_utc = datetime.now(timezone.utc)
            states = FastPropagator.batch_propagate_catalog(stream_subset, now_utc)

            payload = {
                "timestamp": now_utc.isoformat(),
                "objects_count": len(states),
                "states": [
                    {
                        "id": s["norad_id"],
                        "name": s["name"],
                        "type": s["object_type"],
                        "pos_eci_km": s["position_eci_km"],
                        "lat": s["latitude_deg"],
                        "lon": s["longitude_deg"],
                        "alt_km": s["altitude_km"],
                        "speed_kms": s["speed_kms"],
                        "criticality": s["criticality_score"]
                    }
                    for s in states
                ]
            }

            await websocket.send_text(json.dumps(payload))
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass


# Mount Web UI directory if exists
web_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "web")
if os.path.exists(web_dir):
    app.mount("/static", StaticFiles(directory=web_dir), name="static")

    @app.get("/")
    async def serve_index():
        return FileResponse(os.path.join(web_dir, "index.html"))
