"""Runtime configuration read from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    scenario_data_dir: Path
    static_dir: Path | None
    log_level: str
    max_n_simulations: int
    max_horizon_days: int
    max_concurrent_simulations: int
    cors_origins: tuple[str, ...]


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _default_scenario_dir() -> Path:
    env = os.environ.get("SCENARIO_DATA_DIR")
    if env:
        return Path(env)
    return _project_root() / "data" / "scenarios"


def _default_static_dir() -> Path | None:
    env = os.environ.get("STATIC_DIR")
    if env:
        p = Path(env)
        return p if p.exists() else None
    baked = _project_root() / "app" / "static"
    return baked if baked.exists() else None


def _cors_origins() -> tuple[str, ...]:
    raw = os.environ.get("CORS_ORIGINS", "").strip()
    if not raw:
        return ("http://localhost:5173", "http://127.0.0.1:5173")
    return tuple(part.strip() for part in raw.split(",") if part.strip())


def load_settings() -> Settings:
    return Settings(
        scenario_data_dir=_default_scenario_dir(),
        static_dir=_default_static_dir(),
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
        max_n_simulations=int(os.environ.get("MAX_N_SIMULATIONS", "10000")),
        max_horizon_days=int(os.environ.get("MAX_HORIZON_DAYS", "365")),
        max_concurrent_simulations=max(
            1, int(os.environ.get("MAX_CONCURRENT_SIMULATIONS", "2"))
        ),
        cors_origins=_cors_origins(),
    )


settings = load_settings()
