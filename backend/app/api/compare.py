"""Scenario-comparison endpoint (spec §2.2, §7.3).

Evaluates a set of user-supplied labeled policies against the same scenario
and demand/lead-time inputs, returning aligned metrics for the compare page.
"""

from __future__ import annotations

from typing import Literal

import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.api.services import _metrics_out, _policy_out, resolve_inputs
from app.core.config import settings
from app.core.limits import simulation_slot
from app.domain import (
    build_demand_sampler,
    build_lead_time_sampler,
    compute_metrics,
    simulate,
)
from app.domain.policies import RQPolicy, SsPolicy
from app.schemas.optimize import (
    CostAssumptions,
    DemandModel,
    LeadTimeModel,
    MetricSummaryOut,
    PolicyFamilyIn,
    PolicyOut,
)

router = APIRouter()


class NamedPolicyIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    label: str
    policy_family: PolicyFamilyIn
    reorder_point: int = Field(..., ge=0)
    order_quantity: int | None = Field(None, ge=1)
    order_up_to: int | None = Field(None, ge=1)

    @model_validator(mode="after")
    def _consistent(self) -> NamedPolicyIn:
        if self.policy_family == "r_Q" and self.order_quantity is None:
            raise ValueError("r_Q requires order_quantity")
        if self.policy_family == "s_S" and self.order_up_to is None:
            raise ValueError("s_S requires order_up_to")
        return self


class CompareRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    scenario_id: str = Field(..., min_length=1)

    policies: list[NamedPolicyIn] = Field(..., min_length=1, max_length=10)
    demand_model: DemandModel = "empirical_bootstrap"
    lead_time_model: LeadTimeModel

    costs: CostAssumptions | None = None
    n_simulations: int = Field(1000, ge=100, le=10000)
    horizon_days: int = Field(180, ge=14, le=365)
    random_seed: int = 42


class ComparisonRow(BaseModel):
    label: str
    policy: PolicyOut
    metrics: MetricSummaryOut


class CompareResponse(BaseModel):
    status: Literal["ok"] = "ok"
    rows: list[ComparisonRow]


@router.post("/compare", response_model=CompareResponse)
def post_compare(request: CompareRequest) -> CompareResponse:
    try:
        from app.schemas.optimize import OptimizeRequest

        fake = OptimizeRequest(
            scenario_id=request.scenario_id,
            demand_model=request.demand_model,
            lead_time_model=request.lead_time_model,
            costs=request.costs,
            policy_family=request.policies[0].policy_family,
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
        request.demand_model, history=inputs.history, weekday=inputs.weekday
    )

    rows: list[ComparisonRow] = []
    # One slot for the whole batch: a compare request simulates up to 10
    # policies, and taking/releasing a slot per policy would let two batches
    # interleave and contend for the same core anyway.
    with simulation_slot():
        for i, named in enumerate(request.policies):
            rng = np.random.default_rng(request.random_seed + i * 101)
            if named.policy_family == "r_Q":
                assert named.order_quantity is not None
                policy = RQPolicy(reorder_point=named.reorder_point, order_quantity=named.order_quantity)
            else:
                assert named.order_up_to is not None
                policy = SsPolicy(reorder_point=named.reorder_point, order_up_to=named.order_up_to)
            result = simulate(
                policy=policy,
                demand=demand,
                lead_time=lead_time,
                costs=inputs.costs,
                horizon_days=min(request.horizon_days, settings.max_horizon_days),
                n_sims=min(request.n_simulations, settings.max_n_simulations),
                rng=rng,
            )
            m = compute_metrics(result)
            rows.append(ComparisonRow(label=named.label, policy=_policy_out(policy), metrics=_metrics_out(m)))
    return CompareResponse(rows=rows)
