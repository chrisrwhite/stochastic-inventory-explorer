"""Deployment guardrails: the per-instance simulation semaphore and the
server-side compute clamp.

Both exist because the service runs on Cloud Run with a fixed, small CPU
allocation and a request timeout. They are the difference between a busy
instance shedding load cleanly and a busy instance thrashing until every
request on it times out.
"""

from __future__ import annotations

import threading
from dataclasses import replace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import services
from app.core import limits
from app.core.config import settings
from app.main import create_app


@pytest.fixture
def slot_app() -> FastAPI:
    """A minimal app exercising the guard without running a real simulation."""

    app = FastAPI()
    entered = threading.Event()
    release = threading.Event()

    @app.get("/slow")
    def slow() -> dict:
        with limits.simulation_slot():
            entered.set()
            release.wait(timeout=5)
            return {"ok": True}

    app.state.entered = entered
    app.state.release = release
    return app


def test_busy_instance_returns_429_not_a_queue(slot_app: FastAPI) -> None:
    """A request with no free slot fails fast instead of waiting its turn.

    Queueing would park the caller past the request timeout with no feedback;
    a retryable 429 lets the client (or Cloud Run's next instance) handle it.
    """

    # Exhaust every slot, then confirm the next caller is turned away.
    held = [limits._slots.acquire(blocking=False) for _ in range(settings.max_concurrent_simulations)]
    assert all(held)
    try:
        client = TestClient(slot_app)
        r = client.get("/slow")
        assert r.status_code == 429
        assert r.headers["Retry-After"] == "5"
        assert r.json()["detail"] == limits.BUSY_DETAIL
    finally:
        for _ in held:
            limits._slots.release()


def test_slot_is_released_after_the_request(slot_app: FastAPI) -> None:
    """A completed request must hand its slot back, or the instance bleeds
    capacity until it answers nothing but 429s."""

    slot_app.state.release.set()
    client = TestClient(slot_app)
    assert client.get("/slow").status_code == 200

    acquired = [
        limits._slots.acquire(blocking=False)
        for _ in range(settings.max_concurrent_simulations)
    ]
    for _ in [a for a in acquired if a]:
        limits._slots.release()
    assert all(acquired), "slot was not returned after the request completed"


def test_slot_is_released_when_the_handler_raises() -> None:
    """Same, for the error path -- an exception must not leak a slot."""

    app = FastAPI()

    @app.get("/boom")
    def boom() -> dict:
        with limits.simulation_slot():
            raise RuntimeError("boom")

    client = TestClient(app, raise_server_exceptions=False)
    assert client.get("/boom").status_code == 500

    acquired = [
        limits._slots.acquire(blocking=False)
        for _ in range(settings.max_concurrent_simulations)
    ]
    for _ in [a for a in acquired if a]:
        limits._slots.release()
    assert all(acquired), "slot was not returned after the handler raised"


def test_optimize_clamps_request_to_configured_ceiling(monkeypatch: pytest.MonkeyPatch) -> None:
    """A caller asking for more compute than the deployment allows gets a
    clamped run, not a request that outlives the Cloud Run timeout.

    The UI never asks for more than 1000 x 180, but /api/optimize is public and
    the schema alone permits 10000 x 365 -- measured at ~251 s and 727 MB.
    """

    # Settings is frozen, so swap in a replacement where services.py reads it.
    monkeypatch.setattr(
        services,
        "settings",
        replace(settings, max_n_simulations=200, max_horizon_days=20),
    )

    client = TestClient(create_app())
    r = client.post(
        "/api/optimize",
        json={
            "scenario_id": "walmart_pantry_m5",
            "policy_family": "s_S",
            "demand_model": "empirical_bootstrap",
            "lead_time_model": {"distribution": "fixed", "days": 3},
            "mode": "service_level",
            "target_service_level": 0.9,
            "n_simulations": 10000,
            "horizon_days": 365,
        },
    )
    assert r.status_code == 200
    metrics = r.json()["metrics"]
    assert metrics["n_sims"] == 200
    assert metrics["horizon_days"] == 20
