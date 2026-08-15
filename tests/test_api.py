"""
Integration tests for FastAPI endpoints using httpx.AsyncClient.
"""

import asyncio
from httpx import AsyncClient, ASGITransport
import pytest

from aetheris.api.server import app


def _run_async(coro):
    return asyncio.run(coro)


def test_api_health():
    """Verify health endpoint."""
    async def _test():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res = await client.get("/api/health")
            assert res.status_code == 200
            data = res.json()
            assert data["status"] == "ONLINE"
            assert data["total_catalog_objects"] > 0
    _run_async(_test())


def test_api_catalog_query():
    """Verify catalog query and filtering."""
    async def _test():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res = await client.get("/api/catalog?limit=50")
            assert res.status_code == 200
            data = res.json()
            assert data["total_returned"] <= 50
            assert len(data["objects"]) > 0
    _run_async(_test())


def test_api_predict_fast_analytical():
    """Verify fast analytical prediction endpoint."""
    async def _test():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res = await client.post("/api/predict", json={
                "norad_id": 27386,  # ENVISAT
                "use_high_precision_hpop": False
            })
            assert res.status_code == 200
            data = res.json()
            assert data["mode"] == "FAST_ANALYTICAL_SGP4_J2"
            assert "position_eci_km" in data["state"]
            assert "velocity_eci_kms" in data["state"]
    _run_async(_test())


def test_api_criticality_ranking():
    """Verify criticality ranking endpoint returns sorted list."""
    async def _test():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res = await client.get("/api/criticality/ranking?limit=10")
            assert res.status_code == 200
            data = res.json()
            assert len(data["ranked_targets"]) == 10
            scores = [t["criticality_score"] for t in data["ranked_targets"]]
            assert scores == sorted(scores, reverse=True)
    _run_async(_test())


def test_api_fleet_optimizer():
    """Verify fleet mission optimizer endpoint."""
    async def _test():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res = await client.post("/api/fleet/optimize", json={
                "top_n_critical_targets": 6,
                "chaser_dry_mass_kg": 500.0,
                "chaser_propellant_capacity_kg": 800.0
            })
            assert res.status_code == 200
            data = res.json()
            assert data["summary"]["minimum_robots_needed"] >= 1
            assert data["summary"]["total_targets_cleaned"] == 6
            assert len(data["robots"]) >= 1
    _run_async(_test())


def test_api_aerothermal_demise():
    """Verify aerothermal demise simulation endpoint."""
    async def _test():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res = await client.post("/api/reentry/aerothermal", json={
                "norad_id": 27386  # ENVISAT
            })
            assert res.status_code == 200
            data = res.json()
            assert "disposal_recommendation" in data
            assert len(data["components"]) > 0
    _run_async(_test())


def test_api_point_nemo_targeter():
    """Verify Point Nemo deorbit planning endpoint."""
    async def _test():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res = await client.post("/api/reentry/point_nemo", json={
                "norad_id": 27386  # ENVISAT
            })
            assert res.status_code == 200
            data = res.json()
            assert data["delta_v_ms"] > 0
            assert data["is_contained_in_spoua_polygon"] is True
    _run_async(_test())


def test_api_ion_beam_shepherd():
    """Verify Ion Beam Shepherd contactless deorbit calculation endpoint."""
    async def _test():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res = await client.post("/api/reentry/ion_beam_shepherd", json={
                "norad_id": 27386,  # ENVISAT
                "standoff_distance_m": 25.0,
                "beam_thrust_mn": 250.0
            })
            assert res.status_code == 200
            data = res.json()
            assert data["target_name"] == "ENVISAT"
            assert data["flux_interception_efficiency_percent"] > 50.0
            assert data["chaser_recoil_force_mn"] == data["station_keeping_compensation_force_mn"] == 250.0
            assert data["deorbit_dwell_duration_days"] > 0
            assert data["tumbling_immunity_flag"] is True
    _run_async(_test())
