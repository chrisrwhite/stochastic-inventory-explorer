"""Vectorized Monte Carlo inventory simulator.

For a single policy this evaluates ``n_sims`` independent trajectories of
length ``horizon_days``. State is held in ``(n_sims,)`` NumPy arrays so the
inner Python loop runs once per day rather than once per (day, simulation).

Assumptions:

- One review per ``review_period_days`` days: policies decide at end of day.
- Orders placed at end of day ``t`` arrive at the start of day ``t + L`` where
  ``L`` is the sampled integer lead time (>= 1). Multiple outstanding orders
  can be in flight simultaneously.
- Unmet demand is treated as a lost sale in the fulfillment/service metrics,
  but a "backorder-like" accumulation is exposed for reporting. The default
  cost accounting charges ``stockout_cost_per_unit`` for each unfulfilled
  unit.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from app.domain.demand import DemandSampler
from app.domain.lead_time import LeadTimeSampler
from app.domain.policies import Policy


@dataclass(frozen=True)
class Costs:
    """Cost inputs for the inventory simulator.

    Only ``holding_cost_per_unit_per_day``, ``stockout_cost_per_unit``,
    ``fixed_order_cost``, and ``variable_order_cost_per_unit`` are charged in
    the objective (see the cost accounting block in :func:`simulate`).

    ``unit_cost`` is captured as the wholesale/acquisition reference price
    (median observed retail price times a wholesale ratio in the fetch
    pipeline). It is used to *derive* ``holding_cost_per_unit_per_day``
    upstream and is displayed to the user for context, but it is not charged
    in the per-simulation total: for a fixed horizon and lost-sales
    assumption, total purchase cost is roughly constant across policies and
    does not change the argmin.
    """

    unit_cost: float = 0.0
    holding_cost_per_unit_per_day: float = 0.0
    stockout_cost_per_unit: float = 0.0
    fixed_order_cost: float = 0.0
    variable_order_cost_per_unit: float = 0.0
    starting_inventory: float = 0.0
    review_period_days: int = 1


@dataclass
class SimulationResult:
    """Raw per-simulation outputs from a single policy evaluation."""

    demand: np.ndarray            # (n_sims, horizon)
    fulfilled: np.ndarray         # (n_sims, horizon)
    stockouts: np.ndarray         # (n_sims, horizon), unfulfilled units
    on_hand: np.ndarray           # (n_sims, horizon+1), start-of-day on-hand
    orders_placed: np.ndarray     # (n_sims, horizon), qty ordered end-of-day
    receipts: np.ndarray          # (n_sims, horizon), qty received start-of-day
    holding_cost: np.ndarray      # (n_sims,)
    ordering_cost: np.ndarray     # (n_sims,)
    stockout_cost: np.ndarray     # (n_sims,)
    total_cost: np.ndarray        # (n_sims,)
    n_orders: np.ndarray          # (n_sims,), integer count of orders placed
    days_with_stockout: np.ndarray  # (n_sims,)
    costs: Costs = field(default_factory=Costs)

    @property
    def n_sims(self) -> int:
        return int(self.demand.shape[0])

    @property
    def horizon(self) -> int:
        return int(self.demand.shape[1])


def _sample_lead_times(
    lead_time: LeadTimeSampler,
    n_sims: int,
    max_orders: int,
    rng: np.random.Generator,
) -> np.ndarray:
    if max_orders <= 0:
        return np.zeros((n_sims, 0), dtype=np.int64)
    return lead_time.sample(n_sims, max_orders, rng)


def simulate(
    policy: Policy,
    demand: DemandSampler,
    lead_time: LeadTimeSampler,
    costs: Costs,
    *,
    horizon_days: int,
    n_sims: int,
    rng: np.random.Generator,
) -> SimulationResult:
    """Run ``n_sims`` Monte Carlo trajectories for ``policy``."""

    if horizon_days <= 0:
        raise ValueError("horizon_days must be > 0")
    if n_sims <= 0:
        raise ValueError("n_sims must be > 0")

    demand_arr = demand.sample(n_sims, horizon_days, rng)
    demand_arr = np.asarray(demand_arr, dtype=np.int64)

    # Upper bound on number of orders any simulation could place - one per review day.
    review = max(int(costs.review_period_days), 1)
    max_orders = (horizon_days + review - 1) // review
    lead_times = _sample_lead_times(lead_time, n_sims, max_orders, rng)

    on_hand = np.zeros((n_sims, horizon_days + 1), dtype=np.float64)
    on_hand[:, 0] = float(costs.starting_inventory)

    fulfilled = np.zeros((n_sims, horizon_days), dtype=np.int64)
    stockouts = np.zeros((n_sims, horizon_days), dtype=np.int64)
    orders_placed = np.zeros((n_sims, horizon_days), dtype=np.int64)
    receipts = np.zeros((n_sims, horizon_days), dtype=np.int64)

    # Track outstanding orders as (qty, arrival_day) buckets in a matrix.
    # Each sim holds a slot per potential order. We stamp the arrival day
    # relative to horizon; entries with arrival_day == -1 are empty.
    order_qty = np.zeros((n_sims, max_orders), dtype=np.int64)
    order_arrival = np.full((n_sims, max_orders), -1, dtype=np.int64)
    order_lead = np.zeros((n_sims, max_orders), dtype=np.int64)  # captured lead time
    next_slot = np.zeros(n_sims, dtype=np.int64)

    sim_index = np.arange(n_sims)

    for t in range(horizon_days):
        arriving_mask = order_arrival == t
        if arriving_mask.any():
            arriving_qty = np.where(arriving_mask, order_qty, 0).sum(axis=1)
            receipts[:, t] = arriving_qty
            order_arrival = np.where(arriving_mask, -1, order_arrival)
            order_qty = np.where(arriving_mask, 0, order_qty)

        available = on_hand[:, t] + receipts[:, t]

        today_demand = demand_arr[:, t]
        served = np.minimum(available, today_demand).astype(np.int64)
        fulfilled[:, t] = served
        stockouts[:, t] = today_demand - served
        on_hand[:, t + 1] = available - served

        outstanding = np.where(order_arrival > t, order_qty, 0).sum(axis=1)
        inventory_position = on_hand[:, t + 1] + outstanding

        if t % review == (review - 1) or review == 1:
            qty = policy.order(inventory_position)
            place_mask = qty > 0
            if place_mask.any():
                slot = next_slot[place_mask]
                sims_placing = sim_index[place_mask]
                lts = lead_times[sims_placing, slot]
                arrivals = t + lts
                order_qty[sims_placing, slot] = qty[place_mask]
                order_arrival[sims_placing, slot] = arrivals
                order_lead[sims_placing, slot] = lts
                orders_placed[sims_placing, t] = qty[place_mask]
                next_slot[place_mask] = slot + 1

    # ---- cost accounting ----
    holding = on_hand[:, 1:].sum(axis=1) * float(costs.holding_cost_per_unit_per_day)
    n_orders = (orders_placed > 0).sum(axis=1)
    total_units_ordered = orders_placed.sum(axis=1)
    ordering = (
        n_orders * float(costs.fixed_order_cost)
        + total_units_ordered * float(costs.variable_order_cost_per_unit)
    )
    stockout_cost = stockouts.sum(axis=1) * float(costs.stockout_cost_per_unit)
    total = holding + ordering + stockout_cost

    days_with_stockout = (stockouts > 0).sum(axis=1)

    return SimulationResult(
        demand=demand_arr,
        fulfilled=fulfilled,
        stockouts=stockouts,
        on_hand=on_hand,
        orders_placed=orders_placed,
        receipts=receipts,
        holding_cost=holding,
        ordering_cost=ordering.astype(np.float64),
        stockout_cost=stockout_cost.astype(np.float64),
        total_cost=total.astype(np.float64),
        n_orders=n_orders.astype(np.int64),
        days_with_stockout=days_with_stockout.astype(np.int64),
        costs=costs,
    )
