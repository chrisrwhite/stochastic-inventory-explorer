"""Demand-sampler tests."""

from __future__ import annotations

import numpy as np
import pytest

from app.domain.demand import (
    EmpiricalBootstrap,
    NegativeBinomial,
    Poisson,
    SeasonalBootstrap,
    build_demand_sampler,
)


def test_empirical_bootstrap_is_deterministic_with_seed() -> None:
    history = np.array([0, 1, 2, 3, 4], dtype=np.int64)
    sampler = EmpiricalBootstrap(history=history)
    a = sampler.sample(n_sims=8, horizon_days=30, rng=np.random.default_rng(42))
    b = sampler.sample(n_sims=8, horizon_days=30, rng=np.random.default_rng(42))
    np.testing.assert_array_equal(a, b)
    assert a.shape == (8, 30)
    assert a.min() >= 0
    assert a.max() <= 4


def test_empirical_bootstrap_rejects_negative_history() -> None:
    with pytest.raises(ValueError):
        EmpiricalBootstrap(history=np.array([1, -1, 2], dtype=np.int64))


def test_empirical_bootstrap_expected_daily_demand_matches_history() -> None:
    history = np.array([1, 3, 5, 7], dtype=np.int64)
    sampler = EmpiricalBootstrap(history=history)
    assert sampler.expected_daily_demand() == pytest.approx(4.0)


def test_seasonal_bootstrap_respects_weekday_buckets() -> None:
    history = np.array([0, 0, 0, 100, 0, 0, 0], dtype=np.int64)
    weekday = np.array([0, 1, 2, 3, 4, 5, 6], dtype=np.int64)
    sampler = SeasonalBootstrap(history=history, weekday=weekday)
    out = sampler.sample(n_sims=50, horizon_days=7, rng=np.random.default_rng(0))
    assert out[:, 0].max() == 0
    assert out[:, 3].min() == 100
    assert out[:, 6].max() == 0


def test_poisson_sampler_is_seeded_and_non_negative() -> None:
    sampler = Poisson(rate=2.5)
    out = sampler.sample(n_sims=100, horizon_days=50, rng=np.random.default_rng(7))
    assert out.min() >= 0
    assert 2.0 < out.mean() < 3.0


def test_negative_binomial_is_overdispersed() -> None:
    sampler = NegativeBinomial(mean=3.0, dispersion=1.0)
    out = sampler.sample(n_sims=1000, horizon_days=50, rng=np.random.default_rng(1))
    assert out.var(ddof=1) > out.mean()


def test_build_demand_sampler_dispatch() -> None:
    hist = np.array([1, 2, 3, 4, 5], dtype=np.int64)
    boot = build_demand_sampler("empirical_bootstrap", history=hist)
    assert isinstance(boot, EmpiricalBootstrap)

    pois = build_demand_sampler("poisson", history=hist)
    assert isinstance(pois, Poisson)
    assert pois.rate == pytest.approx(3.0)

    nb = build_demand_sampler("negative_binomial", history=hist)
    assert isinstance(nb, NegativeBinomial)

    with pytest.raises(ValueError):
        build_demand_sampler("unknown")
