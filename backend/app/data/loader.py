"""Load bundled scenarios from disk."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from app.core.config import settings

SPARKLINE_DAYS = 90


@dataclass(frozen=True)
class ScenarioSummary:
    scenario_id: str
    title: str
    description: str
    domain: str
    sku_id: str
    history_days: int
    source: str
    start_date: str
    sparkline: list[int]


@dataclass(frozen=True)
class ScenarioBundle:
    summary: ScenarioSummary
    demand_history: np.ndarray  # (history_days,) int
    weekday: np.ndarray          # (history_days,) int 0..6
    costs: dict[str, float]
    lead_time: dict[str, Any]


def _scenarios_dir() -> Path:
    return Path(settings.scenario_data_dir)


def load_manifest() -> list[dict[str, Any]]:
    path = _scenarios_dir() / "MANIFEST.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return list(data.get("scenarios", []))


def _read_sparkline(scenario_id: str, n_days: int = SPARKLINE_DAYS) -> list[int]:
    """Return the last n_days of demand history for the given scenario.

    Returns an empty list if the demand CSV cannot be read.
    """
    path = _scenarios_dir() / scenario_id / "demand.csv"
    if not path.exists():
        return []
    try:
        demand, _ = _read_demand_csv(path)
    except (ValueError, KeyError):
        return []
    tail = demand[-n_days:]
    return [int(v) for v in tail]


def load_scenario_summaries() -> list[ScenarioSummary]:
    summaries: list[ScenarioSummary] = []
    for entry in load_manifest():
        scenario_id = entry["scenario_id"]
        summaries.append(
            ScenarioSummary(
                scenario_id=scenario_id,
                title=entry["title"],
                description=entry["description"],
                domain=entry["domain"],
                sku_id=entry["sku_id"],
                history_days=int(entry.get("history_days", 0)),
                source=str(entry.get("source", "")),
                start_date=str(entry.get("start_date", "")),
                sparkline=_read_sparkline(scenario_id),
            )
        )
    return summaries


def _read_demand_csv(path: Path) -> tuple[np.ndarray, np.ndarray]:
    df = pd.read_csv(path)
    required = {"date", "demand_units"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"demand CSV missing columns: {sorted(missing)}")
    dates = pd.to_datetime(df["date"], errors="raise")
    demand = df["demand_units"].astype(np.int64).to_numpy()
    weekday = dates.dt.weekday.to_numpy().astype(np.int64)
    if np.any(demand < 0):
        raise ValueError("demand_units must be non-negative")
    return demand, weekday


def load_scenario(scenario_id: str) -> ScenarioBundle:
    entries = {e["scenario_id"]: e for e in load_manifest()}
    if scenario_id not in entries:
        raise KeyError(f"unknown scenario: {scenario_id}")
    entry = entries[scenario_id]
    root = _scenarios_dir() / scenario_id

    demand, weekday = _read_demand_csv(root / "demand.csv")
    costs = yaml.safe_load((root / "costs.yaml").read_text(encoding="utf-8"))
    lead_time = yaml.safe_load((root / "lead_time.yaml").read_text(encoding="utf-8"))

    summary = ScenarioSummary(
        scenario_id=scenario_id,
        title=entry["title"],
        description=entry["description"],
        domain=entry["domain"],
        sku_id=entry["sku_id"],
        history_days=int(entry.get("history_days", demand.size)),
        source=str(entry.get("source", "")),
        start_date=str(entry.get("start_date", "")),
        sparkline=[int(v) for v in demand[-SPARKLINE_DAYS:]],
    )
    return ScenarioBundle(
        summary=summary,
        demand_history=demand,
        weekday=weekday,
        costs=costs,
        lead_time=lead_time,
    )
