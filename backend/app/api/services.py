"""Business-logic layer that adapts pydantic requests to the domain layer.

Kept out of route handlers so it can be unit-tested without the ASGI stack.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.core.config import settings
from app.data import ScenarioBundle, load_scenario
from app.domain import (
    OptimizationMode,
    build_demand_sampler,
    build_lead_time_sampler,
    build_policy_explanation,
    build_policy_grid,
    build_scenario_comparison,
    comparison_policies,
    compute_metrics,
    evaluate_policies,
    select_policy,
    simulate,
)
from app.domain.inventory import Costs, SimulationResult
from app.domain.optimize import PolicyEvaluation
from app.domain.policies import Policy, PolicyFamily
from app.schemas.optimize import (
    ComparisonPolicyOut,
    FrontierPoint,
    LeadTimeModel,
    MetricSummaryOut,
    OptimizeRequest,
    OptimizeResponse,
    PolicyExplanationOut,
    PolicyOut,
    SimulationPath,
    SimulationSummaryOut,
)

FRONTIER_MAX_POINTS = 100
FAN_CHART_PATHS = 30


@dataclass(frozen=True)
class ResolvedInputs:
    scenario_id: str
    history: np.ndarray
    weekday: np.ndarray
    costs: Costs
    lead_time_model: LeadTimeModel
    scenario_bundle: ScenarioBundle


def resolve_inputs(req: OptimizeRequest) -> ResolvedInputs:
    scenario_bundle = load_scenario(req.scenario_id)
    history = np.asarray(scenario_bundle.demand_history, dtype=np.int64)
    weekday = np.asarray(scenario_bundle.weekday, dtype=np.int64)
    default_costs = scenario_bundle.costs

    cost_payload = req.costs.model_dump() if req.costs is not None else default_costs

    costs = Costs(
        unit_cost=float(cost_payload.get("unit_cost", 0.0)),
        holding_cost_per_unit_per_day=float(cost_payload.get("holding_cost_per_unit_per_day", 0.0)),
        stockout_cost_per_unit=float(cost_payload.get("stockout_cost_per_unit", 0.0)),
        fixed_order_cost=float(cost_payload.get("fixed_order_cost", 0.0)),
        variable_order_cost_per_unit=float(cost_payload.get("variable_order_cost_per_unit", 0.0)),
        starting_inventory=float(cost_payload.get("starting_inventory", 0.0)),
        review_period_days=int(cost_payload.get("review_period_days", 1)),
    )

    lt_model = req.lead_time_model
    if lt_model.distribution == "fixed" and lt_model.days is None:
        default_lt = scenario_bundle.lead_time
        merged_lt_data = dict(default_lt)
        merged_lt_data.update(
            {k: v for k, v in lt_model.model_dump().items() if v is not None and k != "distribution"}
        )
        lt_model = LeadTimeModel(**merged_lt_data)

    return ResolvedInputs(
        scenario_id=req.scenario_id,
        history=history,
        weekday=weekday,
        costs=costs,
        lead_time_model=lt_model,
        scenario_bundle=scenario_bundle,
    )


def _policy_family(name: str) -> PolicyFamily:
    return PolicyFamily.RQ if name == "r_Q" else PolicyFamily.SS


def _optimization_mode(name: str) -> OptimizationMode:
    return {
        "service_level": OptimizationMode.SERVICE_LEVEL,
        "stockout_risk": OptimizationMode.STOCKOUT_RISK,
        "cvar_budget": OptimizationMode.CVAR_BUDGET,
    }[name]


def _policy_out(policy: Policy, lead_time_mean_demand: float | None = None) -> PolicyOut:
    d = policy.as_dict()
    reorder_point = int(d["reorder_point"])
    safety_stock: int | None = None
    if lead_time_mean_demand is not None:
        safety_stock = max(reorder_point - round(lead_time_mean_demand), 0)
    return PolicyOut(
        policy_family=d["policy_family"],
        reorder_point=reorder_point,
        order_quantity=d.get("order_quantity"),
        order_up_to=d.get("order_up_to"),
        safety_stock=safety_stock,
    )


def _metrics_out(m) -> MetricSummaryOut:
    return MetricSummaryOut(**m.to_dict())


def _clamp_request(req: OptimizeRequest) -> OptimizeRequest:
    n_sims = min(req.n_simulations, settings.max_n_simulations)
    horizon = min(req.horizon_days, settings.max_horizon_days)
    return req.model_copy(update={"n_simulations": n_sims, "horizon_days": horizon})


MIN_DISPLAY_SERVICE_LEVEL = 0.15
"""Policies below this reliability are dropped from the frontier chart.

The grid always includes many trivially-bad policies (very low reorder point
with high-demand SKUs). They dominate the bottom of the scatter plot and
obscure the story; the recommended is still included so the target-vs-recommended
comparison is preserved even if no grid policy hits the target.
"""


def _filter_for_display(
    evals: list[PolicyEvaluation], best_key: tuple[float, ...]
) -> list[PolicyEvaluation]:
    """Drop hopeless policies (very low reliability) except the recommended."""

    kept = [
        e
        for e in evals
        if e.metrics.cycle_service_level >= MIN_DISPLAY_SERVICE_LEVEL
        or e.policy.key() == best_key
    ]
    # Fallback: if the filter is too aggressive (grid mostly stuck at 0%),
    # still surface at least a handful so the chart isn't a single dot.
    if len(kept) < 5:
        by_csl = sorted(evals, key=lambda e: -e.metrics.cycle_service_level)
        kept = list({e.policy.key(): e for e in by_csl[:15] + kept}.values())
    return kept


def _downsample_frontier(evals: list[PolicyEvaluation], best_key: tuple[float, ...]) -> list[PolicyEvaluation]:
    """Downsample the scatter so the chart stays readable.

    Sort candidates by expected total cost and take an evenly-spaced subset,
    preserving both the low-cost/low-reliability end and the high-cost/high-
    reliability end of the tradeoff. This is *not* a strict Pareto filter - we
    intentionally include dominated points so the visitor can see the full
    scatter, then draw their own eye along its lower-right edge (which is the
    Pareto frontier). The recommended policy is always kept.
    """
    if len(evals) <= FRONTIER_MAX_POINTS:
        return evals
    ordered = sorted(evals, key=lambda e: e.metrics.expected_total_cost)
    step = max(1, len(ordered) // FRONTIER_MAX_POINTS)
    sampled = ordered[::step]
    if not any(e.policy.key() == best_key for e in sampled):
        sampled.append(next(e for e in evals if e.policy.key() == best_key))
    return sampled


def _pick_representative_paths(result: SimulationResult) -> list[SimulationPath]:
    if result.n_sims == 0 or result.horizon == 0:
        return []
    total_stockouts = result.stockouts.sum(axis=1)
    order = np.argsort(total_stockouts)
    percentiles = np.linspace(5, 95, FAN_CHART_PATHS)
    paths: list[SimulationPath] = []
    for p in percentiles:
        idx = round((p / 100.0) * (order.size - 1))
        sim_idx = int(order[idx])
        paths.append(
            SimulationPath(
                percentile=float(p),
                on_hand=result.on_hand[sim_idx, 1:].astype(int).tolist(),
                demand=result.demand[sim_idx].astype(int).tolist(),
                receipts=result.receipts[sim_idx].astype(int).tolist(),
                orders_placed=result.orders_placed[sim_idx].astype(int).tolist(),
            )
        )
    return paths


def run_optimization(request: OptimizeRequest) -> OptimizeResponse:
    req = _clamp_request(request)
    inputs = resolve_inputs(req)
    family = _policy_family(req.policy_family)

    lt_kwargs = inputs.lead_time_model.model_dump(exclude_none=True)
    distribution = lt_kwargs.pop("distribution")
    lead_time = build_lead_time_sampler(distribution, **lt_kwargs)

    demand = build_demand_sampler(
        req.demand_model,
        history=inputs.history,
        weekday=inputs.weekday,
    )

    rng = np.random.default_rng(req.random_seed)

    grid = build_policy_grid(family, demand, lead_time, rng)
    grid_evals = evaluate_policies(
        grid, demand, lead_time, inputs.costs,
        horizon_days=req.horizon_days,
        n_sims=req.n_simulations,
        rng=rng,
    )

    chosen = select_policy(
        grid_evals,
        mode=_optimization_mode(req.mode),
        target_service_level=req.target_service_level,
        max_stockout_risk=req.max_stockout_risk,
        cvar_stockout_budget=req.cvar_stockout_budget,
    )

    detail_rng = np.random.default_rng(req.random_seed + 7919)
    detail_result = simulate(
        policy=chosen.policy,
        demand=demand,
        lead_time=lead_time,
        costs=inputs.costs,
        horizon_days=req.horizon_days,
        n_sims=req.n_simulations,
        rng=detail_rng,
    )
    detail_metrics = compute_metrics(detail_result)

    refs = comparison_policies(demand, lead_time, family)
    ref_evals = evaluate_policies(
        list(refs.values()), demand, lead_time, inputs.costs,
        horizon_days=req.horizon_days,
        n_sims=req.n_simulations,
        rng=rng,
    )
    ref_by_label = dict(zip(refs.keys(), ref_evals, strict=True))

    explanation_rng = np.random.default_rng(req.random_seed + 31)
    explanation = build_policy_explanation(
        selected=PolicyEvaluation(chosen.policy, detail_metrics, chosen.result),
        demand=demand,
        lead_time=lead_time,
        target_service_level=req.target_service_level,
        rng=explanation_rng,
    )

    comparison_rows = build_scenario_comparison(
        selected=PolicyEvaluation(chosen.policy, detail_metrics, chosen.result),
        references=[(label, ev) for label, ev in ref_by_label.items()],
    )

    comparison_out = [
        ComparisonPolicyOut(
            label=row.label,
            policy=_policy_out(ref_by_label[row.label].policy, explanation.expected_lead_time_demand),
            metrics=_metrics_out(ref_by_label[row.label].metrics),
            cost_delta=row.cost_delta,
            service_level_delta=row.service_level_delta,
            stockout_probability_delta=row.stockout_probability_delta,
            average_on_hand_delta=row.average_on_hand_delta,
        )
        for row in comparison_rows
    ]

    best_key = chosen.policy.key()
    display_evals = _filter_for_display(grid_evals, best_key)
    frontier_evals = _downsample_frontier(display_evals, best_key)
    frontier = [
        FrontierPoint(
            policy=_policy_out(e.policy, explanation.expected_lead_time_demand),
            expected_total_cost=e.metrics.expected_total_cost,
            cycle_service_level=e.metrics.cycle_service_level,
            stockout_probability=e.metrics.stockout_probability,
            fill_rate=e.metrics.fill_rate,
            average_on_hand=e.metrics.average_on_hand,
            cvar_stockout_cost=e.metrics.cvar_stockout_cost,
            is_recommended=e.policy.key() == best_key,
        )
        for e in frontier_evals
    ]

    simulation = SimulationSummaryOut(
        horizon_days=req.horizon_days,
        paths=_pick_representative_paths(detail_result),
    )

    return OptimizeResponse(
        scenario_id=inputs.scenario_id,
        recommended_policy=_policy_out(chosen.policy, explanation.expected_lead_time_demand),
        metrics=_metrics_out(detail_metrics),
        frontier=frontier,
        comparison_policies=comparison_out,
        simulation=simulation,
        explanation=PolicyExplanationOut(
            reorder_point=explanation.reorder_point,
            order_up_to=explanation.order_up_to,
            order_quantity=explanation.order_quantity,
            expected_lead_time_demand=explanation.expected_lead_time_demand,
            safety_stock=explanation.safety_stock,
            service_level_target=explanation.service_level_target,
            dominant_cost_driver=explanation.dominant_cost_driver,
            narrative=explanation.narrative,
        ),
    )
