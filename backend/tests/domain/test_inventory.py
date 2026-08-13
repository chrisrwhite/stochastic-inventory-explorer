"""Simulator + metrics tests with golden fixtures."""

from __future__ import annotations

import numpy as np

from app.domain.demand import EmpiricalBootstrap, Poisson
from app.domain.inventory import Costs, simulate
from app.domain.lead_time import Fixed
from app.domain.metrics import compute_metrics
from app.domain.policies import RQPolicy, SsPolicy


def test_zero_demand_produces_no_stockout_or_orders() -> None:
    demand = EmpiricalBootstrap(history=np.array([0], dtype=np.int64))
    lead = Fixed(days=3)
    costs = Costs(
        unit_cost=1.0,
        holding_cost_per_unit_per_day=0.1,
        stockout_cost_per_unit=10.0,
        fixed_order_cost=5.0,
        starting_inventory=10.0,
        review_period_days=1,
    )
    policy = RQPolicy(reorder_point=5, order_quantity=5)
    result = simulate(
        policy=policy,
        demand=demand,
        lead_time=lead,
        costs=costs,
        horizon_days=30,
        n_sims=5,
        rng=np.random.default_rng(0),
    )
    assert result.stockouts.sum() == 0
    assert result.orders_placed.sum() == 0
    m = compute_metrics(result)
    assert m.stockout_probability == 0.0
    assert m.cycle_service_level == 1.0
    assert m.fill_rate == 1.0


def test_constant_demand_fixed_lead_time_deterministic() -> None:
    demand = EmpiricalBootstrap(history=np.array([2], dtype=np.int64))
    lead = Fixed(days=2)
    costs = Costs(
        holding_cost_per_unit_per_day=0.1,
        stockout_cost_per_unit=10.0,
        fixed_order_cost=5.0,
        starting_inventory=20.0,
    )
    policy = RQPolicy(reorder_point=6, order_quantity=10)
    result = simulate(
        policy=policy,
        demand=demand,
        lead_time=lead,
        costs=costs,
        horizon_days=60,
        n_sims=3,
        rng=np.random.default_rng(0),
    )
    demand_units = int(result.demand.sum(axis=1).mean())
    fulfilled_units = int(result.fulfilled.sum(axis=1).mean())
    stockout_units = int(result.stockouts.sum(axis=1).mean())
    assert demand_units == fulfilled_units + stockout_units


def test_inventory_balance_identity_holds_across_random_seeds() -> None:
    """on_hand[t+1] = on_hand[t] + receipts[t] - fulfilled[t] for every day."""

    demand = Poisson(rate=3.0)
    lead = Fixed(days=4)
    costs = Costs(
        holding_cost_per_unit_per_day=0.05,
        stockout_cost_per_unit=8.0,
        fixed_order_cost=4.0,
        starting_inventory=15.0,
    )
    policy = SsPolicy(reorder_point=10, order_up_to=25)
    result = simulate(
        policy=policy,
        demand=demand,
        lead_time=lead,
        costs=costs,
        horizon_days=90,
        n_sims=25,
        rng=np.random.default_rng(123),
    )
    expected_next = result.on_hand[:, :-1] + result.receipts - result.fulfilled
    np.testing.assert_allclose(result.on_hand[:, 1:], expected_next, atol=1e-9)


def test_high_service_target_is_met_with_conservative_policy() -> None:
    demand = Poisson(rate=2.0)
    lead = Fixed(days=3)
    costs = Costs(
        holding_cost_per_unit_per_day=0.01,
        stockout_cost_per_unit=10.0,
        fixed_order_cost=1.0,
        starting_inventory=30.0,
    )
    policy = SsPolicy(reorder_point=30, order_up_to=60)
    result = simulate(
        policy=policy,
        demand=demand,
        lead_time=lead,
        costs=costs,
        horizon_days=60,
        n_sims=200,
        rng=np.random.default_rng(9),
    )
    m = compute_metrics(result)
    assert m.cycle_service_level > 0.9
    assert m.stockout_probability < 0.1


def test_stockouts_appear_when_undersupplied() -> None:
    demand = EmpiricalBootstrap(history=np.array([5], dtype=np.int64))
    lead = Fixed(days=2)
    costs = Costs(
        holding_cost_per_unit_per_day=0.1,
        stockout_cost_per_unit=10.0,
        fixed_order_cost=1.0,
        starting_inventory=2.0,
    )
    policy = RQPolicy(reorder_point=0, order_quantity=1)
    result = simulate(
        policy=policy,
        demand=demand,
        lead_time=lead,
        costs=costs,
        horizon_days=30,
        n_sims=5,
        rng=np.random.default_rng(0),
    )
    m = compute_metrics(result)
    assert m.stockout_probability > 0.9
    assert m.fill_rate < 0.5


def test_cvar_never_below_expected_stockout_cost() -> None:
    demand = Poisson(rate=3.0)
    lead = Fixed(days=3)
    costs = Costs(
        holding_cost_per_unit_per_day=0.02,
        stockout_cost_per_unit=15.0,
        fixed_order_cost=2.0,
        starting_inventory=6.0,
    )
    policy = RQPolicy(reorder_point=5, order_quantity=8)
    result = simulate(
        policy=policy,
        demand=demand,
        lead_time=lead,
        costs=costs,
        horizon_days=45,
        n_sims=200,
        rng=np.random.default_rng(4),
    )
    m = compute_metrics(result)
    assert m.cvar_stockout_cost + 1e-6 >= m.expected_stockout_cost


def test_seeded_run_is_reproducible() -> None:
    demand = Poisson(rate=2.5)
    lead = Fixed(days=3)
    costs = Costs(starting_inventory=10.0, holding_cost_per_unit_per_day=0.01, stockout_cost_per_unit=5.0)
    policy = RQPolicy(reorder_point=8, order_quantity=12)

    r1 = simulate(
        policy=policy, demand=demand, lead_time=lead, costs=costs,
        horizon_days=30, n_sims=20, rng=np.random.default_rng(1234),
    )
    r2 = simulate(
        policy=policy, demand=demand, lead_time=lead, costs=costs,
        horizon_days=30, n_sims=20, rng=np.random.default_rng(1234),
    )
    np.testing.assert_array_equal(r1.demand, r2.demand)
    np.testing.assert_allclose(r1.total_cost, r2.total_cost)
