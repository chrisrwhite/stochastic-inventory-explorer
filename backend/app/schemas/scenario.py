"""Scenario list / metadata schemas."""

from __future__ import annotations

from pydantic import BaseModel


class ScenarioSummaryOut(BaseModel):
    scenario_id: str
    title: str
    description: str
    domain: str
    sku_id: str
    history_days: int
    source: str
    start_date: str
    sparkline: list[int]


class ScenarioListResponse(BaseModel):
    scenarios: list[ScenarioSummaryOut]
