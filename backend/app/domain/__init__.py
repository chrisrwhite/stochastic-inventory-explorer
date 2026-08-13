"""Pure-numpy stochastic inventory optimization core.

No FastAPI, pydantic, or IO imports live here. The domain layer is
unit-testable in isolation and swappable behind the API.
"""

from app.domain.demand import (
    DemandSampler,
    EmpiricalBootstrap,
    NegativeBinomial,
    Poisson,
    SeasonalBootstrap,
    build_demand_sampler,
)
from app.domain.explain import (
    PolicyExplanation,
    build_policy_explanation,
    build_scenario_comparison,
)
from app.domain.grid import build_policy_grid, comparison_policies
from app.domain.inventory import SimulationResult, simulate
from app.domain.lead_time import (
    EmpiricalDiscrete,
    Fixed,
    LeadTimeSampler,
    Lognormal,
    Triangular,
    build_lead_time_sampler,
)
from app.domain.metrics import MetricSummary, compute_metrics
from app.domain.optimize import (
    OptimizationMode,
    PolicyEvaluation,
    evaluate_policies,
    select_policy,
)
from app.domain.policies import Policy, PolicyFamily, RQPolicy, SsPolicy

__all__ = [
    "DemandSampler",
    "EmpiricalBootstrap",
    "EmpiricalDiscrete",
    "Fixed",
    "LeadTimeSampler",
    "Lognormal",
    "MetricSummary",
    "NegativeBinomial",
    "OptimizationMode",
    "Poisson",
    "Policy",
    "PolicyEvaluation",
    "PolicyExplanation",
    "PolicyFamily",
    "RQPolicy",
    "SeasonalBootstrap",
    "SimulationResult",
    "SsPolicy",
    "Triangular",
    "build_demand_sampler",
    "build_lead_time_sampler",
    "build_policy_explanation",
    "build_policy_grid",
    "build_scenario_comparison",
    "comparison_policies",
    "compute_metrics",
    "evaluate_policies",
    "select_policy",
    "simulate",
]
