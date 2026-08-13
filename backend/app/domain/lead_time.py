"""Lead-time sampling processes.

Each sampler returns an ``(n_sims, n_orders)`` integer array of lead-time days.
Lead times are always at least one day (an order placed at end of day ``t``
arrives no earlier than day ``t + 1``).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np


class LeadTimeSampler(ABC):
    """Base class for lead-time-generating processes."""

    name: str

    @abstractmethod
    def sample(self, n_sims: int, n_orders: int, rng: np.random.Generator) -> np.ndarray:
        """Return integer lead times with shape ``(n_sims, n_orders)``."""

    @abstractmethod
    def mean_days(self) -> float:
        """Return the expected lead time in days."""

    @abstractmethod
    def high_quantile_days(self, q: float = 0.95) -> float:
        """Return an upper quantile of the lead-time distribution."""


def _clip_days(arr: np.ndarray) -> np.ndarray:
    return np.clip(np.round(arr), 1, None).astype(np.int64, copy=False)


@dataclass(frozen=True)
class Fixed(LeadTimeSampler):
    days: int
    name: str = "fixed"

    def __post_init__(self) -> None:
        if self.days < 1:
            raise ValueError("Fixed lead time must be at least 1 day")

    def sample(self, n_sims: int, n_orders: int, rng: np.random.Generator) -> np.ndarray:
        del rng
        return np.full((n_sims, n_orders), self.days, dtype=np.int64)

    def mean_days(self) -> float:
        return float(self.days)

    def high_quantile_days(self, q: float = 0.95) -> float:
        del q
        return float(self.days)


@dataclass(frozen=True)
class EmpiricalDiscrete(LeadTimeSampler):
    samples: np.ndarray
    name: str = "empirical_discrete"

    def __post_init__(self) -> None:
        if self.samples.ndim != 1 or self.samples.size == 0:
            raise ValueError("EmpiricalDiscrete samples must be a non-empty 1-D array")
        if np.any(self.samples < 1):
            raise ValueError("Lead times must be >= 1 day")

    def sample(self, n_sims: int, n_orders: int, rng: np.random.Generator) -> np.ndarray:
        idx = rng.integers(0, self.samples.size, size=(n_sims, n_orders))
        return self.samples[idx].astype(np.int64, copy=False)

    def mean_days(self) -> float:
        return float(self.samples.mean())

    def high_quantile_days(self, q: float = 0.95) -> float:
        return float(np.quantile(self.samples, q))


@dataclass(frozen=True)
class Triangular(LeadTimeSampler):
    min_days: float
    mode_days: float
    max_days: float
    name: str = "triangular"

    def __post_init__(self) -> None:
        if not (self.min_days <= self.mode_days <= self.max_days):
            raise ValueError("min_days <= mode_days <= max_days required")
        if self.min_days < 1:
            raise ValueError("min_days must be at least 1")

    def sample(self, n_sims: int, n_orders: int, rng: np.random.Generator) -> np.ndarray:
        raw = rng.triangular(self.min_days, self.mode_days, self.max_days, size=(n_sims, n_orders))
        return _clip_days(raw)

    def mean_days(self) -> float:
        return (self.min_days + self.mode_days + self.max_days) / 3.0

    def high_quantile_days(self, q: float = 0.95) -> float:
        a, m, b = self.min_days, self.mode_days, self.max_days
        f_mode = (m - a) / (b - a) if b > a else 0.5
        if q <= f_mode:
            return float(a + np.sqrt(q * (b - a) * (m - a)))
        return float(b - np.sqrt((1 - q) * (b - a) * (b - m)))


@dataclass(frozen=True)
class Lognormal(LeadTimeSampler):
    """Lognormal parameterized by the target mean/std in days."""

    mean_days_target: float
    std_days_target: float
    min_days: float = 1.0
    max_days: float | None = None
    name: str = "lognormal"

    def __post_init__(self) -> None:
        if self.mean_days_target <= 0:
            raise ValueError("mean_days must be positive")
        if self.std_days_target <= 0:
            raise ValueError("std_days must be positive")

    def _mu_sigma(self) -> tuple[float, float]:
        m = self.mean_days_target
        v = self.std_days_target ** 2
        sigma2 = np.log(1.0 + v / (m * m))
        mu = np.log(m) - 0.5 * sigma2
        return float(mu), float(np.sqrt(sigma2))

    def sample(self, n_sims: int, n_orders: int, rng: np.random.Generator) -> np.ndarray:
        mu, sigma = self._mu_sigma()
        raw = rng.lognormal(mean=mu, sigma=sigma, size=(n_sims, n_orders))
        if self.max_days is not None:
            raw = np.minimum(raw, self.max_days)
        raw = np.maximum(raw, self.min_days)
        return _clip_days(raw)

    def mean_days(self) -> float:
        return float(self.mean_days_target)

    def high_quantile_days(self, q: float = 0.95) -> float:
        mu, sigma = self._mu_sigma()
        from scipy.stats import lognorm

        val = float(lognorm.ppf(q, s=sigma, scale=np.exp(mu)))
        if self.max_days is not None:
            val = min(val, self.max_days)
        return max(val, self.min_days)


def build_lead_time_sampler(
    distribution: str,
    *,
    days: int | float | None = None,
    samples: np.ndarray | None = None,
    min_days: float | None = None,
    mode_days: float | None = None,
    max_days: float | None = None,
    mean_days: float | None = None,
    std_days: float | None = None,
) -> LeadTimeSampler:
    """Construct a lead-time sampler from a string identifier."""

    distribution = distribution.lower()
    if distribution == "fixed":
        if days is None:
            if mean_days is None:
                raise ValueError("fixed lead time requires days or mean_days")
            days = mean_days
        return Fixed(days=round(float(days)))
    if distribution in ("empirical", "empirical_discrete", "discrete"):
        if samples is None:
            raise ValueError("empirical distribution requires samples")
        return EmpiricalDiscrete(samples=np.asarray(samples, dtype=np.int64))
    if distribution == "triangular":
        if min_days is None or mode_days is None or max_days is None:
            raise ValueError("triangular requires min_days, mode_days, max_days")
        return Triangular(min_days=float(min_days), mode_days=float(mode_days), max_days=float(max_days))
    if distribution == "lognormal":
        if mean_days is None or std_days is None:
            raise ValueError("lognormal requires mean_days and std_days")
        return Lognormal(
            mean_days_target=float(mean_days),
            std_days_target=float(std_days),
            min_days=float(min_days) if min_days is not None else 1.0,
            max_days=float(max_days) if max_days is not None else None,
        )
    if distribution == "poisson_shifted":
        if mean_days is None:
            raise ValueError("poisson_shifted requires mean_days")
        lam = max(float(mean_days) - 1.0, 0.0)
        # Poisson-shifted: sample poisson then add 1 to enforce >=1 day
        rng_dummy = np.random.default_rng(0)
        del rng_dummy  # actually built at sample time via EmpiricalDiscrete workaround
        # Realize via a large empirical sample for simplicity.
        rng = np.random.default_rng(12345)
        emp = rng.poisson(lam, size=10000).astype(np.int64) + 1
        return EmpiricalDiscrete(samples=emp)
    raise ValueError(f"unknown lead-time distribution {distribution!r}")
