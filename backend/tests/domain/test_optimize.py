"""Grid + optimizer tests."""

from __future__ import annotations

import numpy as np
import pytest

from app.domain.demand import Poisson
from app.domain.grid import build_policy_grid, comparison_policies
from app.domain.inventory import Costs
from app.domain.lead_time import Fixed, Triangular
from app.domain.optimize import (
    OptimizationMode,
    evaluate_policies,
    select_policy,
)
from app.domain.policies import PolicyFamily


def test_build_policy_grid_returns_unique_capped_policies() -> None:
    demand = Poisson(rate=2.0)
    lt = Triangular(min_days=2, mode_days=4, max_days=8)
    rq = build_policy_grid(PolicyFamily.RQ, demand, lt, np.random.default_rng(0))
    ss = build_policy_grid(PolicyFamily.SS, demand, lt, np.random.default_rng(0))
    assert 0 < len(rq) <= 240
    assert 0 < len(ss) <= 240
    keys = {p.key() for p in rq}
    assert len(keys) == len(rq)


def test_service_level_selector_picks_feasible_min_cost() -> None:
    demand = Poisson(rate=2.5)
    lt = Fixed(days=3)
    costs = Costs(
        holding_cost_per_unit_per_day=0.01,
        stockout_cost_per_unit=10.0,
        fixed_order_cost=1.0,
        starting_inventory=10.0,
    )
    grid = build_policy_grid(PolicyFamily.SS, demand, lt, np.random.default_rng(0))
    evals = evaluate_policies(
        grid, demand, lt, costs,
        horizon_days=60, n_sims=120, rng=np.random.default_rng(9),
    )
    chosen = select_policy(
        evals,
        mode=OptimizationMode.SERVICE_LEVEL,
        target_service_level=0.9,
    )
    assert chosen.metrics.cycle_service_level >= 0.9
    feasible_costs = [
        e.metrics.expected_total_cost
        for e in evals
        if e.metrics.cycle_service_level >= 0.9
    ]
    assert chosen.metrics.expected_total_cost == min(feasible_costs)


def test_stockout_risk_selector_respects_max() -> None:
    demand = Poisson(rate=1.5)
    lt = Fixed(days=2)
    costs = Costs(
        holding_cost_per_unit_per_day=0.01,
        stockout_cost_per_unit=5.0,
        fixed_order_cost=1.0,
        starting_inventory=5.0,
    )
    grid = build_policy_grid(PolicyFamily.RQ, demand, lt, np.random.default_rng(0))
    evals = evaluate_policies(
        grid, demand, lt, costs,
        horizon_days=40, n_sims=100, rng=np.random.default_rng(0),
    )
    chosen = select_policy(
        evals,
        mode=OptimizationMode.STOCKOUT_RISK,
        max_stockout_risk=0.05,
    )
    assert chosen.metrics.stockout_probability <= 0.05 or all(
        e.metrics.stockout_probability > 0.05 for e in evals
    )


def test_infeasible_target_falls_back_to_best_available() -> None:
    demand = Poisson(rate=5.0)
    lt = Fixed(days=10)
    costs = Costs(
        holding_cost_per_unit_per_day=0.5,
        stockout_cost_per_unit=1.0,
        fixed_order_cost=0.5,
        starting_inventory=1.0,
    )
    grid = build_policy_grid(PolicyFamily.RQ, demand, lt, np.random.default_rng(0))
    evals = evaluate_policies(
        grid, demand, lt, costs,
        horizon_days=30, n_sims=60, rng=np.random.default_rng(0),
    )
    chosen = select_policy(
        evals,
        mode=OptimizationMode.SERVICE_LEVEL,
        target_service_level=0.9999,
    )
    assert chosen is not None
    # The fallback picks the highest achievable service level.
    best_sl = max(e.metrics.cycle_service_level for e in evals)
    assert chosen.metrics.cycle_service_level == best_sl


def test_comparison_policies_are_distinct() -> None:
    demand = Poisson(rate=2.0)
    lt = Triangular(min_days=2, mode_days=4, max_days=8)
    refs = comparison_policies(demand, lt, PolicyFamily.RQ)
    assert set(refs.keys()) == {"lean", "conservative", "order_when_empty", "average_demand"}
    keys = {p.key() for p in refs.values()}
    assert len(keys) == len(refs)


def test_missing_constraint_arg_raises() -> None:
    demand = Poisson(rate=1.0)
    lt = Fixed(days=2)
    costs = Costs(starting_inventory=5.0, holding_cost_per_unit_per_day=0.01, stockout_cost_per_unit=1.0)
    grid = build_policy_grid(PolicyFamily.RQ, demand, lt, np.random.default_rng(0))
    evals = evaluate_policies(grid, demand, lt, costs, horizon_days=15, n_sims=20, rng=np.random.default_rng(0))
    with pytest.raises(ValueError):
        select_policy(evals, mode=OptimizationMode.SERVICE_LEVEL)
