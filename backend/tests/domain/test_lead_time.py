"""Lead-time sampler tests."""

from __future__ import annotations

import numpy as np
import pytest

from app.domain.lead_time import (
    EmpiricalDiscrete,
    Fixed,
    Lognormal,
    Triangular,
    build_lead_time_sampler,
)


def test_fixed_lead_time_is_constant() -> None:
    sampler = Fixed(days=4)
    out = sampler.sample(10, 5, np.random.default_rng(0))
    assert (out == 4).all()
    assert sampler.mean_days() == 4.0


def test_empirical_discrete_stays_in_support() -> None:
    samples = np.array([1, 2, 3, 5, 8], dtype=np.int64)
    sampler = EmpiricalDiscrete(samples=samples)
    out = sampler.sample(50, 20, np.random.default_rng(3))
    assert set(np.unique(out)).issubset(set(samples.tolist()))


def test_triangular_lead_time_is_bounded() -> None:
    sampler = Triangular(min_days=2, mode_days=4, max_days=9)
    out = sampler.sample(500, 5, np.random.default_rng(11))
    assert out.min() >= 2
    assert out.max() <= 9
    assert 3.0 < out.mean() < 6.0


def test_lognormal_lead_time_matches_target_mean() -> None:
    sampler = Lognormal(mean_days_target=6.0, std_days_target=2.0, min_days=1.0, max_days=30.0)
    out = sampler.sample(20000, 1, np.random.default_rng(0)).ravel()
    assert 4.5 < out.mean() < 7.5  # rounded ints + clipping widen tolerance
    assert out.min() >= 1


def test_triangular_quantile_matches_empirical() -> None:
    sampler = Triangular(min_days=2, mode_days=4, max_days=8)
    empirical = sampler.sample(20000, 1, np.random.default_rng(5)).ravel()
    q = float(np.quantile(empirical, 0.95))
    assert abs(sampler.high_quantile_days(0.95) - q) < 0.5


def test_build_lead_time_sampler_dispatch() -> None:
    tri = build_lead_time_sampler("triangular", min_days=2, mode_days=4, max_days=6)
    assert isinstance(tri, Triangular)

    fix = build_lead_time_sampler("fixed", days=5)
    assert isinstance(fix, Fixed)
    assert fix.days == 5

    with pytest.raises(ValueError):
        build_lead_time_sampler("triangular")  # missing params
