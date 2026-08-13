"""Demand sampling processes.

Each sampler returns an ``(n_sims, horizon_days)`` array of non-negative integer
demand draws so downstream code can vectorize the day loop across simulations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np


class DemandSampler(ABC):
    """Base class for demand-generating processes."""

    name: str

    @abstractmethod
    def sample(self, n_sims: int, horizon_days: int, rng: np.random.Generator) -> np.ndarray:
        """Return demand draws with shape ``(n_sims, horizon_days)``."""

    @abstractmethod
    def expected_daily_demand(self) -> float:
        """Return an estimate of mean daily demand (used to size the policy grid)."""


@dataclass(frozen=True)
class EmpiricalBootstrap(DemandSampler):
    """Sample days uniformly at random from historical demand observations."""

    history: np.ndarray
    name: str = "empirical_bootstrap"

    def __post_init__(self) -> None:
        if self.history.ndim != 1:
            raise ValueError("EmpiricalBootstrap history must be 1-D")
        if self.history.size == 0:
            raise ValueError("EmpiricalBootstrap requires at least one observation")
        if np.any(self.history < 0):
            raise ValueError("Demand history must be non-negative")

    def sample(self, n_sims: int, horizon_days: int, rng: np.random.Generator) -> np.ndarray:
        idx = rng.integers(0, self.history.size, size=(n_sims, horizon_days))
        return self.history[idx].astype(np.int64, copy=False)

    def expected_daily_demand(self) -> float:
        return float(self.history.mean())


@dataclass(frozen=True)
class SeasonalBootstrap(DemandSampler):
    """Sample days grouped by weekday to preserve weekly seasonality."""

    history: np.ndarray
    weekday: np.ndarray  # 0..6 aligned with history
    name: str = "seasonal_bootstrap"

    def __post_init__(self) -> None:
        if self.history.shape != self.weekday.shape:
            raise ValueError("history and weekday arrays must match in shape")
        if self.history.size == 0:
            raise ValueError("SeasonalBootstrap requires at least one observation")

    def sample(self, n_sims: int, horizon_days: int, rng: np.random.Generator) -> np.ndarray:
        buckets: list[np.ndarray] = [
            self.history[self.weekday == w] for w in range(7)
        ]
        out = np.zeros((n_sims, horizon_days), dtype=np.int64)
        for t in range(horizon_days):
            bucket = buckets[t % 7]
            if bucket.size == 0:
                bucket = self.history
            idx = rng.integers(0, bucket.size, size=n_sims)
            out[:, t] = bucket[idx]
        return out

    def expected_daily_demand(self) -> float:
        return float(self.history.mean())


@dataclass(frozen=True)
class Poisson(DemandSampler):
    """Poisson demand with a fixed rate."""

    rate: float
    name: str = "poisson"

    def __post_init__(self) -> None:
        if self.rate < 0:
            raise ValueError("Poisson rate must be non-negative")

    def sample(self, n_sims: int, horizon_days: int, rng: np.random.Generator) -> np.ndarray:
        return rng.poisson(self.rate, size=(n_sims, horizon_days)).astype(np.int64, copy=False)

    def expected_daily_demand(self) -> float:
        return float(self.rate)


@dataclass(frozen=True)
class NegativeBinomial(DemandSampler):
    """Negative binomial demand for overdispersed processes.

    Parameterized by ``mean`` and ``dispersion`` where ``variance = mean +
    mean^2 / dispersion``.
    """

    mean: float
    dispersion: float
    name: str = "negative_binomial"

    def __post_init__(self) -> None:
        if self.mean < 0:
            raise ValueError("NegativeBinomial mean must be non-negative")
        if self.dispersion <= 0:
            raise ValueError("NegativeBinomial dispersion must be positive")

    def sample(self, n_sims: int, horizon_days: int, rng: np.random.Generator) -> np.ndarray:
        n = self.dispersion
        p = n / (n + self.mean) if self.mean > 0 else 1.0
        return rng.negative_binomial(n, p, size=(n_sims, horizon_days)).astype(np.int64, copy=False)

    def expected_daily_demand(self) -> float:
        return float(self.mean)


def build_demand_sampler(
    model: str,
    history: np.ndarray | None = None,
    weekday: np.ndarray | None = None,
    rate: float | None = None,
    mean: float | None = None,
    dispersion: float | None = None,
) -> DemandSampler:
    """Construct a demand sampler from a string identifier."""

    model = model.lower()
    if model == "empirical_bootstrap":
        if history is None:
            raise ValueError("empirical_bootstrap requires history")
        return EmpiricalBootstrap(history=np.asarray(history, dtype=np.int64))
    if model == "seasonal_bootstrap":
        if history is None or weekday is None:
            raise ValueError("seasonal_bootstrap requires history and weekday arrays")
        return SeasonalBootstrap(
            history=np.asarray(history, dtype=np.int64),
            weekday=np.asarray(weekday, dtype=np.int64),
        )
    if model == "poisson":
        if rate is None:
            if history is None:
                raise ValueError("poisson requires rate or history")
            rate = float(np.asarray(history).mean())
        return Poisson(rate=float(rate))
    if model == "negative_binomial":
        if mean is None or dispersion is None:
            if history is None:
                raise ValueError("negative_binomial requires mean/dispersion or history")
            arr = np.asarray(history, dtype=np.float64)
            mean = float(arr.mean())
            var = float(arr.var(ddof=1)) if arr.size > 1 else mean
            dispersion = max(mean * mean / max(var - mean, 1e-6), 0.1)
        return NegativeBinomial(mean=float(mean), dispersion=float(dispersion))
    raise ValueError(f"unknown demand model {model!r}")
