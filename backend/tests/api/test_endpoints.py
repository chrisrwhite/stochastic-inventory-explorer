"""FastAPI endpoint tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture(scope="module")
def client() -> TestClient:
    app = create_app()
    return TestClient(app)


def test_health(client: TestClient) -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["n_scenarios"] >= 1


def test_data_info(client: TestClient) -> None:
    r = client.get("/api/data-info")
    assert r.status_code == 200
    body = r.json()
    assert "scenario_ids" in body
    assert body["n_scenarios"] == len(body["scenario_ids"])


def test_list_scenarios_includes_bundled(client: TestClient) -> None:
    r = client.get("/api/scenarios")
    assert r.status_code == 200
    ids = {s["scenario_id"] for s in r.json()["scenarios"]}
    assert "walmart_pantry_m5" in ids
    assert "retail_online_uk" in ids


def test_list_scenarios_returns_source_and_sparkline(client: TestClient) -> None:
    r = client.get("/api/scenarios")
    assert r.status_code == 200
    scenarios = {s["scenario_id"]: s for s in r.json()["scenarios"]}
    pantry = scenarios["walmart_pantry_m5"]
    assert pantry["source"] == "m5_walmart"
    assert pantry["start_date"] == "2011-01-29"
    assert isinstance(pantry["sparkline"], list)
    assert 0 < len(pantry["sparkline"]) <= 90
    assert all(isinstance(v, int) and v >= 0 for v in pantry["sparkline"])
    uk = scenarios["retail_online_uk"]
    assert uk["source"] == "uci_online_retail_ii"
    hobbies = scenarios["walmart_hobbies_sparse_m5"]
    assert hobbies["source"] == "m5_walmart"


def test_scenario_detail(client: TestClient) -> None:
    r = client.get("/api/scenarios/walmart_pantry_m5")
    assert r.status_code == 200
    body = r.json()
    assert body["sku_id"]
    assert len(body["demand_history"]) == body["history_days"]


def test_scenario_detail_404_for_unknown(client: TestClient) -> None:
    r = client.get("/api/scenarios/does_not_exist")
    assert r.status_code == 404


def test_optimize_returns_policy_and_frontier(client: TestClient) -> None:
    payload = {
        "scenario_id": "walmart_pantry_m5",
        "policy_family": "s_S",
        "demand_model": "empirical_bootstrap",
        "lead_time_model": {
            "distribution": "triangular",
            "min_days": 2,
            "mode_days": 4,
            "max_days": 8,
        },
        "mode": "service_level",
        "target_service_level": 0.9,
        "n_simulations": 200,
        "horizon_days": 60,
        "random_seed": 7,
    }
    r = client.post("/api/optimize", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["recommended_policy"]["policy_family"] == "s_S"
    assert body["recommended_policy"]["reorder_point"] >= 0
    assert body["metrics"]["expected_total_cost"] >= 0
    assert len(body["frontier"]) >= 1
    assert any(pt["is_recommended"] for pt in body["frontier"])
    assert len(body["simulation"]["paths"]) > 0
    assert body["explanation"]["narrative"]


def test_optimize_rejects_missing_input(client: TestClient) -> None:
    r = client.post(
        "/api/optimize",
        json={
            "policy_family": "r_Q",
            "demand_model": "empirical_bootstrap",
            "lead_time_model": {"distribution": "fixed", "days": 3},
            "target_service_level": 0.9,
        },
    )
    assert r.status_code == 422


def test_simulate_endpoint(client: TestClient) -> None:
    payload = {
        "scenario_id": "walmart_pantry_m5",
        "policy": {
            "policy_family": "r_Q",
            "reorder_point": 30,
            "order_quantity": 60,
        },
        "demand_model": "empirical_bootstrap",
        "lead_time_model": {"distribution": "fixed", "days": 3},
        "n_simulations": 200,
        "horizon_days": 45,
    }
    r = client.post("/api/simulate", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["policy"]["reorder_point"] == 30
    assert body["metrics"]["horizon_days"] == 45
    assert len(body["simulation"]["paths"]) > 0


def test_compare_endpoint(client: TestClient) -> None:
    payload = {
        "scenario_id": "walmart_pantry_m5",
        "policies": [
            {"label": "lean", "policy_family": "s_S", "reorder_point": 20, "order_up_to": 60},
            {"label": "conservative", "policy_family": "s_S", "reorder_point": 60, "order_up_to": 150},
        ],
        "demand_model": "empirical_bootstrap",
        "lead_time_model": {"distribution": "fixed", "days": 3},
        "n_simulations": 200,
        "horizon_days": 45,
    }
    r = client.post("/api/compare", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert [row["label"] for row in body["rows"]] == ["lean", "conservative"]
