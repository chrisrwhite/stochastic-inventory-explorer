"""Candidate policy grid construction.

The grid is sized from lead-time-demand quantiles per spec §6.1:

- reorder point ``r`` from 0 up to a high quantile of demand during lead time
- order quantity ``Q`` from average cycle demand to several weeks of demand
- order-up-to ``S`` from ``r + average demand`` to ``r + high quantile demand``
"""

from __future__ import annotations

import numpy as np

from app.domain.demand import DemandSampler
from app.domain.lead_time import LeadTimeSampler
from app.domain.policies import Policy, PolicyFamily, RQPolicy, SsPolicy

MAX_GRID_POLICIES = 240


def _lead_time_demand_quantile(
    demand: DemandSampler,
    lead_time: LeadTimeSampler,
    q: float,
    rng: np.random.Generator,
    *,
    n_draws: int = 2000,
) -> float:
    """Estimate the ``q``-quantile of total demand during a random lead time."""

    lts = lead_time.sample(n_draws, 1, rng).ravel()
    max_lt = int(lts.max())
    demand_draws = demand.sample(n_draws, max(max_lt, 1), rng)
    idx = np.arange(demand_draws.shape[1])[None, :]
    mask = idx < lts[:, None]
    lead_time_demand = np.where(mask, demand_draws, 0).sum(axis=1)
    return float(np.quantile(lead_time_demand, q))


def _linspace_int(low: float, high: float, n: int) -> list[int]:
    low_i = max(int(np.floor(low)), 0)
    high_i = max(int(np.ceil(high)), low_i + 1)
    if n <= 1:
        return [low_i]
    values = np.linspace(low_i, high_i, n)
    return sorted({round(v) for v in values})


def build_policy_grid(
    family: PolicyFamily,
    demand: DemandSampler,
    lead_time: LeadTimeSampler,
    rng: np.random.Generator,
    *,
    n_r: int = 12,
    n_q: int = 8,
    n_s_over_r: int = 8,
) -> list[Policy]:
    """Build a de-duplicated list of candidate policies."""

    avg_daily = max(demand.expected_daily_demand(), 0.5)
    # Heavy-tailed real-world SKUs (e.g. UCI online retail) plateau in CSL
    # well above the 99.5% quantile of lead-time demand. Push the ceiling to
    # the 99.9% quantile with a 1.5x safety multiplier so the grid always
    # spans up to the plateau; benign SKUs are unaffected because their
    # optimum sits far below the ceiling anyway.
    r_high = _lead_time_demand_quantile(demand, lead_time, 0.999, rng) * 1.5
    r_high = max(r_high, avg_daily * lead_time.mean_days() + avg_daily)

    r_grid = _linspace_int(0, r_high, n_r)

    if family == PolicyFamily.RQ:
        q_low = max(avg_daily * 3.0, 1.0)
        q_high = max(avg_daily * 35.0, q_low + 1.0)
        q_grid = _linspace_int(q_low, q_high, n_q)
        seen: set[tuple[float, ...]] = set()
        policies: list[Policy] = []
        for r in r_grid:
            for q in q_grid:
                p = RQPolicy(reorder_point=int(r), order_quantity=int(q))
                if p.key() in seen:
                    continue
                seen.add(p.key())
                policies.append(p)
        return _cap(policies)

    if family == PolicyFamily.SS:
        seen_ss: set[tuple[float, ...]] = set()
        policies_ss: list[Policy] = []
        top_up_low = max(avg_daily * 3.0, 1.0)
        top_up_high = max(avg_daily * 35.0, top_up_low + 1.0)
        top_ups = _linspace_int(top_up_low, top_up_high, n_s_over_r)
        for r in r_grid:
            for delta in top_ups:
                s_upper = int(r) + int(delta)
                if s_upper <= int(r):
                    continue
                p = SsPolicy(reorder_point=int(r), order_up_to=s_upper)
                if p.key() in seen_ss:
                    continue
                seen_ss.add(p.key())
                policies_ss.append(p)
        return _cap(policies_ss)

    raise ValueError(f"unsupported policy family {family!r}")


def _cap(policies: list[Policy]) -> list[Policy]:
    """Cap total policy count for latency."""

    if len(policies) <= MAX_GRID_POLICIES:
        return policies
    stride = int(np.ceil(len(policies) / MAX_GRID_POLICIES))
    return policies[::stride]


def comparison_policies(
    demand: DemandSampler,
    lead_time: LeadTimeSampler,
    family: PolicyFamily,
) -> dict[str, Policy]:
    """Reference policies for the "Why alternatives lost" panel (spec §7.3)."""

    avg_daily = max(demand.expected_daily_demand(), 0.5)
    mean_lt = max(lead_time.mean_days(), 1.0)
    high_lt = max(lead_time.high_quantile_days(0.95), mean_lt)

    lean_r = max(round(avg_daily * mean_lt), 0)
    balanced_r = max(round(avg_daily * mean_lt + avg_daily * 2), lean_r + 1)
    conservative_r = max(round(avg_daily * high_lt + avg_daily * 4), balanced_r + 1)
    empty_r = 0

    cycle_q = max(round(avg_daily * 14), 1)
    avg_q = max(round(avg_daily * mean_lt), 1)

    if family == PolicyFamily.RQ:
        return {
            "lean": RQPolicy(reorder_point=lean_r, order_quantity=cycle_q),
            "conservative": RQPolicy(reorder_point=conservative_r, order_quantity=cycle_q),
            "order_when_empty": RQPolicy(reorder_point=empty_r, order_quantity=cycle_q),
            "average_demand": RQPolicy(reorder_point=avg_q, order_quantity=avg_q),
        }
    return {
        "lean": SsPolicy(reorder_point=lean_r, order_up_to=lean_r + cycle_q),
        "conservative": SsPolicy(reorder_point=conservative_r, order_up_to=conservative_r + cycle_q),
        "order_when_empty": SsPolicy(reorder_point=empty_r, order_up_to=empty_r + cycle_q),
        "average_demand": SsPolicy(reorder_point=avg_q, order_up_to=avg_q + avg_q),
    }
