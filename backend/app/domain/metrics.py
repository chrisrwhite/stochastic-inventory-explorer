"""Summary metrics derived from a simulation result.

The spec (§6.2) enumerates the exact set of metrics required for the frontier
and the "Why this policy" panel. Anything shown in the UI comes from this
module.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from app.domain.inventory import SimulationResult

CVAR_ALPHA = 0.95


@dataclass(frozen=True)
class MetricSummary:
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

    def to_dict(self) -> dict[str, float]:
        return {k: v for k, v in asdict(self).items()}


def _cvar(losses: np.ndarray, alpha: float = CVAR_ALPHA) -> float:
    """Empirical CVaR - mean of the worst ``(1 - alpha)`` tail."""

    if losses.size == 0:
        return 0.0
    sorted_losses = np.sort(losses)
    cutoff = int(np.ceil(alpha * sorted_losses.size))
    tail = sorted_losses[cutoff:]
    if tail.size == 0:
        return float(sorted_losses[-1])
    return float(tail.mean())


def compute_metrics(result: SimulationResult) -> MetricSummary:
    horizon = result.horizon
    n_sims = result.n_sims

    total_demand = result.demand.sum(axis=1)
    total_fulfilled = result.fulfilled.sum(axis=1)
    total_stockout_units = result.stockouts.sum(axis=1)

    with np.errstate(invalid="ignore", divide="ignore"):
        per_sim_fill = np.where(total_demand > 0, total_fulfilled / total_demand, 1.0)

    average_on_hand = float(result.on_hand[:, 1:].mean())
    stockout_days_any = result.days_with_stockout > 0

    orders_per_month = result.n_orders.astype(np.float64) * (30.0 / max(horizon, 1))

    stockout_cost_arr = result.stockout_cost
    stockout_units_arr = total_stockout_units.astype(np.float64)

    return MetricSummary(
        expected_total_cost=float(result.total_cost.mean()),
        expected_holding_cost=float(result.holding_cost.mean()),
        expected_ordering_cost=float(result.ordering_cost.mean()),
        expected_stockout_cost=float(stockout_cost_arr.mean()),
        cycle_service_level=float(1.0 - stockout_days_any.mean()),
        fill_rate=float(per_sim_fill.mean()),
        average_on_hand=average_on_hand,
        average_orders_per_month=float(orders_per_month.mean()),
        stockout_probability=float(stockout_days_any.mean()),
        cvar_stockout_cost=_cvar(stockout_cost_arr),
        cvar_stockout_units=_cvar(stockout_units_arr),
        expected_stockout_units=float(stockout_units_arr.mean()),
        horizon_days=horizon,
        n_sims=n_sims,
    )
