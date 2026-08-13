"""Explainability layer feeding the "Why this policy" panel.

Turns raw evaluations into human-readable structured deltas: expected demand
during lead time, safety stock, cost tradeoffs vs. reference policies, and
the dominant cost driver.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np

from app.domain.demand import DemandSampler
from app.domain.lead_time import LeadTimeSampler
from app.domain.optimize import PolicyEvaluation


@dataclass(frozen=True)
class PolicyComparisonRow:
    label: str
    policy: dict[str, float]
    cost_delta: float
    service_level_delta: float
    stockout_probability_delta: float
    average_on_hand_delta: float


@dataclass(frozen=True)
class PolicyExplanation:
    reorder_point: int
    order_up_to: int | None
    order_quantity: int | None
    expected_lead_time_demand: float
    safety_stock: int
    service_level_target: float | None
    dominant_cost_driver: str
    narrative: str


def _mean_lead_time_demand(
    demand: DemandSampler,
    lead_time: LeadTimeSampler,
    rng: np.random.Generator,
    n_draws: int = 4000,
) -> float:
    lts = lead_time.sample(n_draws, 1, rng).ravel()
    max_lt = int(lts.max())
    demand_draws = demand.sample(n_draws, max(max_lt, 1), rng)
    idx = np.arange(demand_draws.shape[1])[None, :]
    mask = idx < lts[:, None]
    return float(np.where(mask, demand_draws, 0).sum(axis=1).mean())


def build_policy_explanation(
    selected: PolicyEvaluation,
    demand: DemandSampler,
    lead_time: LeadTimeSampler,
    target_service_level: float | None,
    rng: np.random.Generator,
) -> PolicyExplanation:
    policy = selected.policy.as_dict()
    reorder_point = int(policy["reorder_point"])
    order_up_to = int(policy["order_up_to"]) if "order_up_to" in policy else None
    order_quantity = int(policy["order_quantity"]) if "order_quantity" in policy else None

    lead_demand = _mean_lead_time_demand(demand, lead_time, rng)
    safety_stock = max(reorder_point - round(lead_demand), 0)

    m = selected.metrics
    parts = {
        "holding": m.expected_holding_cost,
        "ordering": m.expected_ordering_cost,
        "stockout": m.expected_stockout_cost,
    }
    dominant = max(parts, key=lambda k: parts[k])

    label = "reorder point"
    tail = ""
    if order_up_to is not None:
        tail = f" and orders up to {order_up_to} units"
    elif order_quantity is not None:
        tail = f" and orders a fixed {order_quantity} units"

    narrative = (
        f"The selected {label} is {reorder_point} units. Average demand during lead time is "
        f"{lead_demand:.1f} units, so {safety_stock} units are held as safety stock{tail}. "
        f"Expected monthly cost is ${m.expected_total_cost:.2f} with a fill rate of "
        f"{m.fill_rate*100:.1f}% and a stockout probability of {m.stockout_probability*100:.1f}%. "
        f"The dominant cost driver is {dominant}."
    )

    return PolicyExplanation(
        reorder_point=reorder_point,
        order_up_to=order_up_to,
        order_quantity=order_quantity,
        expected_lead_time_demand=lead_demand,
        safety_stock=safety_stock,
        service_level_target=target_service_level,
        dominant_cost_driver=dominant,
        narrative=narrative,
    )


def build_scenario_comparison(
    selected: PolicyEvaluation,
    references: Iterable[tuple[str, PolicyEvaluation]],
) -> list[PolicyComparisonRow]:
    rows: list[PolicyComparisonRow] = []
    sel_m = selected.metrics
    for label, ref in references:
        rm = ref.metrics
        rows.append(
            PolicyComparisonRow(
                label=label,
                policy=ref.policy.as_dict(),
                cost_delta=sel_m.expected_total_cost - rm.expected_total_cost,
                service_level_delta=sel_m.cycle_service_level - rm.cycle_service_level,
                stockout_probability_delta=sel_m.stockout_probability - rm.stockout_probability,
                average_on_hand_delta=sel_m.average_on_hand - rm.average_on_hand,
            )
        )
    return rows
