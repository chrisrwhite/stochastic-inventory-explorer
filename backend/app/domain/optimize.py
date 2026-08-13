"""Policy evaluation and selection.

Evaluates a candidate policy grid with Monte Carlo and picks the best per the
spec's constraint modes (§6.3):

- min cost subject to ``service_level >= target``
- min cost subject to ``P(stockout) <= alpha``
- min cost subject to ``CVaR_stockout_cost <= budget``
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

import numpy as np

from app.domain.demand import DemandSampler
from app.domain.inventory import Costs, SimulationResult, simulate
from app.domain.lead_time import LeadTimeSampler
from app.domain.metrics import MetricSummary, compute_metrics
from app.domain.policies import Policy


class OptimizationMode(StrEnum):
    SERVICE_LEVEL = "service_level"
    STOCKOUT_RISK = "stockout_risk"
    CVAR_BUDGET = "cvar_budget"


@dataclass(frozen=True)
class PolicyEvaluation:
    policy: Policy
    metrics: MetricSummary
    result: SimulationResult


def _seeded_rng(base_rng: np.random.Generator, i: int) -> np.random.Generator:
    seed = int(base_rng.integers(0, 2**31 - 1)) + i
    return np.random.default_rng(seed)


def evaluate_policies(
    policies: Sequence[Policy],
    demand: DemandSampler,
    lead_time: LeadTimeSampler,
    costs: Costs,
    *,
    horizon_days: int,
    n_sims: int,
    rng: np.random.Generator,
    keep_result: bool = False,
) -> list[PolicyEvaluation]:
    """Simulate every policy and compute metrics.

    Each policy uses a distinct RNG seed so their draws are independent but
    reproducible from a single top-level seed.
    """

    evaluations: list[PolicyEvaluation] = []
    for i, policy in enumerate(policies):
        policy_rng = _seeded_rng(rng, i)
        result = simulate(
            policy=policy,
            demand=demand,
            lead_time=lead_time,
            costs=costs,
            horizon_days=horizon_days,
            n_sims=n_sims,
            rng=policy_rng,
        )
        metrics = compute_metrics(result)
        if not keep_result:
            trimmed = SimulationResult(
                demand=np.zeros((0, 0), dtype=np.int64),
                fulfilled=np.zeros((0, 0), dtype=np.int64),
                stockouts=np.zeros((0, 0), dtype=np.int64),
                on_hand=np.zeros((0, 0), dtype=np.float64),
                orders_placed=np.zeros((0, 0), dtype=np.int64),
                receipts=np.zeros((0, 0), dtype=np.int64),
                holding_cost=np.zeros(0),
                ordering_cost=np.zeros(0),
                stockout_cost=np.zeros(0),
                total_cost=np.zeros(0),
                n_orders=np.zeros(0, dtype=np.int64),
                days_with_stockout=np.zeros(0, dtype=np.int64),
                costs=costs,
            )
            evaluations.append(PolicyEvaluation(policy=policy, metrics=metrics, result=trimmed))
        else:
            evaluations.append(PolicyEvaluation(policy=policy, metrics=metrics, result=result))
    return evaluations


def select_policy(
    evaluations: Sequence[PolicyEvaluation],
    *,
    mode: OptimizationMode,
    target_service_level: float | None = None,
    max_stockout_risk: float | None = None,
    cvar_stockout_budget: float | None = None,
) -> PolicyEvaluation:
    """Return the min-cost feasible evaluation given the constraint mode.

    If no policy is feasible we fall back to the one with the closest
    constraint value so the UI can still show something useful.
    """

    if not evaluations:
        raise ValueError("no policies to select from")

    def cost(e: PolicyEvaluation) -> float:
        return e.metrics.expected_total_cost

    if mode == OptimizationMode.SERVICE_LEVEL:
        if target_service_level is None:
            raise ValueError("SERVICE_LEVEL mode requires target_service_level")
        feasible = [e for e in evaluations if e.metrics.cycle_service_level >= target_service_level]
        if feasible:
            return min(feasible, key=cost)
        # Infeasible: the target is unreachable (typically heavy-tailed demand).
        # Return the cheapest policy on the top of the achievable-CSL plateau
        # so we don't punish the user with a needlessly expensive S when
        # extra order-up-to headroom yields no CSL benefit.
        max_csl = max(e.metrics.cycle_service_level for e in evaluations)
        plateau = [e for e in evaluations if e.metrics.cycle_service_level >= max_csl - 0.01]
        return min(plateau, key=cost)

    if mode == OptimizationMode.STOCKOUT_RISK:
        if max_stockout_risk is None:
            raise ValueError("STOCKOUT_RISK mode requires max_stockout_risk")
        feasible = [e for e in evaluations if e.metrics.stockout_probability <= max_stockout_risk]
        if feasible:
            return min(feasible, key=cost)
        # Same idea as SERVICE_LEVEL: pick the cheapest policy on the
        # lowest-stockout plateau when nothing is feasible.
        min_stockout = min(e.metrics.stockout_probability for e in evaluations)
        plateau = [e for e in evaluations if e.metrics.stockout_probability <= min_stockout + 0.01]
        return min(plateau, key=cost)

    if mode == OptimizationMode.CVAR_BUDGET:
        if cvar_stockout_budget is None:
            raise ValueError("CVAR_BUDGET mode requires cvar_stockout_budget")
        feasible = [e for e in evaluations if e.metrics.cvar_stockout_cost <= cvar_stockout_budget]
        if feasible:
            return min(feasible, key=cost)
        min_cvar = min(e.metrics.cvar_stockout_cost for e in evaluations)
        plateau = [e for e in evaluations if e.metrics.cvar_stockout_cost <= min_cvar * 1.05]
        return min(plateau, key=cost)

    raise ValueError(f"unknown optimization mode {mode!r}")
