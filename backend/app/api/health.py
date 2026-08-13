"""Health check endpoint used by Cloud Run and CI."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from app import __version__
from app.core.config import settings
from app.data import load_manifest

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    version: str
    n_scenarios: int
    scenario_data_dir: str


class DataInfoResponse(BaseModel):
    scenario_data_dir: str
    static_dir: str | None
    n_scenarios: int
    scenario_ids: list[str]


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    scenarios = load_manifest()
    return HealthResponse(
        status="ok",
        version=__version__,
        n_scenarios=len(scenarios),
        scenario_data_dir=str(settings.scenario_data_dir),
    )


@router.get("/data-info", response_model=DataInfoResponse)
def get_data_info() -> DataInfoResponse:
    scenarios = load_manifest()
    static_dir: str | None = str(settings.static_dir) if settings.static_dir else None
    scenario_data_dir = str(settings.scenario_data_dir)
    if not Path(scenario_data_dir).exists():
        scenario_data_dir = f"{scenario_data_dir} (missing)"
    return DataInfoResponse(
        scenario_data_dir=scenario_data_dir,
        static_dir=static_dir,
        n_scenarios=len(scenarios),
        scenario_ids=[s["scenario_id"] for s in scenarios],
    )
