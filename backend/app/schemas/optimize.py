"""Request/response models for the optimization endpoints."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

DemandModel = Literal[
    "empirical_bootstrap",
    "seasonal_bootstrap",
    "poisson",
    "negative_binomial",
]

PolicyFamilyIn = Literal["r_Q", "s_S"]

LeadTimeDistribution = Literal[
    "fixed",
    "empirical",
    "empirical_discrete",
    "triangular",
    "lognormal",
    "poisson_shifted",
]

OptimizationModeIn = Literal[
    "service_level",
    "stockout_risk",
    "cvar_budget",
]


class LeadTimeModel(BaseModel):
    model_config = ConfigDict(extra="ignore")
    distribution: LeadTimeDistribution
    days: float | None = None
    min_days: float | None = None
    mode_days: float | None = None
    max_days: float | None = None
    mean_days: float | None = None
    std_days: float | None = None
    samples: list[int] | None = None


class CostAssumptions(BaseModel):
    model_config = ConfigDict(extra="ignore")
    unit_cost: float = 0.0
    holding_cost_per_unit_per_day: float = Field(0.0, ge=0.0)
    stockout_cost_per_unit: float = Field(0.0, ge=0.0)
    fixed_order_cost: float = Field(0.0, ge=0.0)
    variable_order_cost_per_unit: float = Field(0.0, ge=0.0)
    starting_inventory: float = Field(0.0, ge=0.0)
    review_period_days: int = Field(1, ge=1, le=30)


class OptimizeRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    scenario_id: str = Field(..., min_length=1)

    policy_family: PolicyFamilyIn = "s_S"
    demand_model: DemandModel = "empirical_bootstrap"
    lead_time_model: LeadTimeModel

    mode: OptimizationModeIn = "service_level"
    target_service_level: float | None = Field(0.95, ge=0.0, le=1.0)
    max_stockout_risk: float | None = Field(None, ge=0.0, le=1.0)
    cvar_stockout_budget: float | None = Field(None, ge=0.0)

    costs: CostAssumptions | None = None

    n_simulations: int = Field(1000, ge=100, le=10000)
    horizon_days: int = Field(180, ge=14, le=365)
    random_seed: int = 42

    @model_validator(mode="after")
    def _require_input(self) -> OptimizeRequest:
        if self.mode == "service_level" and self.target_service_level is None:
            raise ValueError("service_level mode requires target_service_level")
        if self.mode == "stockout_risk" and self.max_stockout_risk is None:
            raise ValueError("stockout_risk mode requires max_stockout_risk")
        if self.mode == "cvar_budget" and self.cvar_stockout_budget is None:
            raise ValueError("cvar_budget mode requires cvar_stockout_budget")
        return self


class PolicyOut(BaseModel):
    policy_family: PolicyFamilyIn
    reorder_point: int
    order_quantity: int | None = None
    order_up_to: int | None = None
    safety_stock: int | None = None


class MetricSummaryOut(BaseModel):
    expected_total_cost: float
    expected_holding_cost: float
    expected_ordering_cost: float
    expected_stockout_cost: float
    cycle_service_level: float
    fill_rate: float
    average_on_hand: float
    average_orders_per_month: float
    stockout_probability: float
    cvar_stockout_cost: float
    cvar_stockout_units: float
    expected_stockout_units: float
    horizon_days: int
    n_sims: int


class FrontierPoint(BaseModel):
    policy: PolicyOut
    expected_total_cost: float
    cycle_service_level: float
    stockout_probability: float
    fill_rate: float
    average_on_hand: float
    cvar_stockout_cost: float
    is_recommended: bool = False


class ComparisonPolicyOut(BaseModel):
    label: str
    policy: PolicyOut
    metrics: MetricSummaryOut
    cost_delta: float
    service_level_delta: float
    stockout_probability_delta: float
    average_on_hand_delta: float


class SimulationPath(BaseModel):
    percentile: float
    on_hand: list[int]
    demand: list[int]
    receipts: list[int]
    orders_placed: list[int]


class SimulationSummaryOut(BaseModel):
    horizon_days: int
    paths: list[SimulationPath]


class PolicyExplanationOut(BaseModel):
    reorder_point: int
    order_up_to: int | None
    order_quantity: int | None
    expected_lead_time_demand: float
    safety_stock: int
    service_level_target: float | None
    dominant_cost_driver: str
    narrative: str


class OptimizeResponse(BaseModel):
    status: str = "ok"
    scenario_id: str
    recommended_policy: PolicyOut
    metrics: MetricSummaryOut
    frontier: list[FrontierPoint]
    comparison_policies: list[ComparisonPolicyOut]
    simulation: SimulationSummaryOut
    explanation: PolicyExplanationOut
