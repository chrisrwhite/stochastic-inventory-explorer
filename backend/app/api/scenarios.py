"""Bundled scenario listing endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.data import load_scenario, load_scenario_summaries
from app.schemas import ScenarioListResponse, ScenarioSummaryOut

router = APIRouter()


class ScenarioDetailResponse(BaseModel):
    scenario_id: str
    title: str
    description: str
    domain: str
    sku_id: str
    history_days: int
    source: str
    start_date: str
    demand_history: list[int]
    weekday: list[int]
    costs: dict[str, float]
    lead_time: dict[str, object]


@router.get("/scenarios", response_model=ScenarioListResponse)
def list_scenarios() -> ScenarioListResponse:
    summaries = load_scenario_summaries()
    return ScenarioListResponse(
        scenarios=[
            ScenarioSummaryOut(
                scenario_id=s.scenario_id,
                title=s.title,
                description=s.description,
                domain=s.domain,
                sku_id=s.sku_id,
                history_days=s.history_days,
                source=s.source,
                start_date=s.start_date,
                sparkline=s.sparkline,
            )
            for s in summaries
        ]
    )


@router.get("/scenarios/{scenario_id}", response_model=ScenarioDetailResponse)
def get_scenario(scenario_id: str) -> ScenarioDetailResponse:
    try:
        bundle = load_scenario(scenario_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ScenarioDetailResponse(
        scenario_id=bundle.summary.scenario_id,
        title=bundle.summary.title,
        description=bundle.summary.description,
        domain=bundle.summary.domain,
        sku_id=bundle.summary.sku_id,
        history_days=bundle.summary.history_days,
        source=bundle.summary.source,
        start_date=bundle.summary.start_date,
        demand_history=bundle.demand_history.tolist(),
        weekday=bundle.weekday.tolist(),
        costs=bundle.costs,
        lead_time=bundle.lead_time,
    )
