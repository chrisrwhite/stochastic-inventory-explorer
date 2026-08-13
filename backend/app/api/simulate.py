"""Simulate-a-single-policy endpoint.

Accepts the same inputs as ``/optimize`` plus an explicit policy, then returns
metrics and simulation paths only (no grid, no comparison). Useful for the
"tweak my policy manually" UX and for the frontend to redraw the fan chart
without re-running the whole grid.
"""

from __future__ import annotations

from typing import Literal

import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.api.services import (
    _metrics_out,
    _pick_representative_paths,
    _policy_out,
    resolve_inputs,
)
from app.core.config import settings
from app.core.limits import simulation_slot
from app.domain import (
    build_demand_sampler,
    build_lead_time_sampler,
    compute_metrics,
    simulate,
)
from app.domain.policies import Policy, RQPolicy, SsPolicy
from app.schemas.optimize import (
    CostAssumptions,
    DemandModel,
    LeadTimeModel,
    MetricSummaryOut,
    PolicyFamilyIn,
    PolicyOut,
    SimulationSummaryOut,
)

router = APIRouter()


class SimulatePolicyIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    policy_family: PolicyFamilyIn
    reorder_point: int = Field(..., ge=0)
    order_quantity: int | None = Field(None, ge=1)
    order_up_to: int | None = Field(None, ge=1)

    @model_validator(mode="after")
    def _consistent(self) -> SimulatePolicyIn:
        if self.policy_family == "r_Q" and self.order_quantity is None:
            raise ValueError("r_Q requires order_quantity")
        if self.policy_family == "s_S" and self.order_up_to is None:
            raise ValueError("s_S requires order_up_to")
        return self

    def to_policy(self) -> Policy:
        if self.policy_family == "r_Q":
            assert self.order_quantity is not None
            return RQPolicy(reorder_point=self.reorder_point, order_quantity=self.order_quantity)
        assert self.order_up_to is not None
        return SsPolicy(reorder_point=self.reorder_point, order_up_to=self.order_up_to)


class SimulateRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    scenario_id: str = Field(..., min_length=1)

    policy: SimulatePolicyIn
    demand_model: DemandModel = "empirical_bootstrap"
    lead_time_model: LeadTimeModel

    costs: CostAssumptions | None = None
    n_simulations: int = Field(1000, ge=100, le=10000)
    horizon_days: int = Field(180, ge=14, le=365)
    random_seed: int = 42


class SimulateResponse(BaseModel):
    status: Literal["ok"] = "ok"
    policy: PolicyOut
    metrics: MetricSummaryOut
    simulation: SimulationSummaryOut


@router.post("/simulate", response_model=SimulateResponse)
def post_simulate(request: SimulateRequest) -> SimulateResponse:
    try:
        # Reuse OptimizeRequest's input resolution by faking a minimal shape.
        from app.schemas.optimize import OptimizeRequest

        fake = OptimizeRequest(
            scenario_id=request.scenario_id,
            demand_model=request.demand_model,
            lead_time_model=request.lead_time_model,
            costs=request.costs,
            policy_family=request.policy.policy_family,
            n_simulations=min(request.n_simulations, settings.max_n_simulations),
            horizon_days=min(request.horizon_days, settings.max_horizon_days),
            random_seed=request.random_seed,
        )
        inputs = resolve_inputs(fake)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    lt_kwargs = inputs.lead_time_model.model_dump(exclude_none=True)
    distribution = lt_kwargs.pop("distribution")
    lead_time = build_lead_time_sampler(distribution, **lt_kwargs)
    demand = build_demand_sampler(
        request.demand_model,
        history=inputs.history,
        weekday=inputs.weekday,
    )
    rng = np.random.default_rng(request.random_seed)

    with simulation_slot():
        result = simulate(
            policy=request.policy.to_policy(),
            demand=demand,
            lead_time=lead_time,
            costs=inputs.costs,
            horizon_days=min(request.horizon_days, settings.max_horizon_days),
            n_sims=min(request.n_simulations, settings.max_n_simulations),
            rng=rng,
        )
    metrics = compute_metrics(result)

    return SimulateResponse(
        policy=_policy_out(request.policy.to_policy()),
        metrics=_metrics_out(metrics),
        simulation=SimulationSummaryOut(
            horizon_days=result.horizon,
            paths=_pick_representative_paths(result),
        ),
    )
