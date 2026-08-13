"""QA sweep: run the optimizer against every bundled scenario and print a
compact report so we can eyeball whether each result is plausible.

Run from the repo root:
    poetry run python -m scripts.qa_scenarios  # from backend/
or
    cd backend && poetry run python ../scripts/qa_scenarios.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import numpy as np

from app.api.services import run_optimization
from app.data.loader import load_manifest, load_scenario
from app.schemas.optimize import CostAssumptions, LeadTimeModel, OptimizeRequest

TARGET_SL = 0.95
N_SIMS = 2000
HORIZON = 180
SEED = 42

RESET = "\033[0m"
DIM = "\033[2m"
BOLD = "\033[1m"
RED = "\033[31m"
YELLOW = "\033[33m"
GREEN = "\033[32m"
CYAN = "\033[36m"


def fmt_money(x: float) -> str:
    return f"${x:,.2f}"


def fmt_pct(x: float, digits: int = 1) -> str:
    return f"{x * 100:.{digits}f}%"


def check(cond: bool, ok_msg: str, bad_msg: str) -> str:
    return f"{GREEN}✓{RESET} {ok_msg}" if cond else f"{RED}✗{RESET} {bad_msg}"


def warn(msg: str) -> str:
    return f"{YELLOW}⚠{RESET} {msg}"


def run_one(scenario_id: str) -> None:
    bundle = load_scenario(scenario_id)
    demand = bundle.demand_history
    n = demand.size
    mean = float(demand.mean())
    std = float(demand.std())
    zero_frac = float((demand == 0).mean())
    p99 = float(np.percentile(demand, 99))
    max_d = int(demand.max())

    lt_cfg = bundle.lead_time
    lead_mean = float(lt_cfg.get("mean_days", 0.0))

    costs = bundle.costs
    unit_cost = float(costs.get("unit_cost", 0.0))
    holding = float(costs.get("holding_cost_per_unit_per_day", 0.0))
    stockout_pen = float(costs.get("stockout_cost_per_unit", 0.0))
    fixed_order = float(costs.get("fixed_order_cost", 0.0))
    var_order = float(costs.get("variable_order_cost_per_unit", 0.0))
    starting = float(costs.get("starting_inventory", 0.0))

    print(f"\n{BOLD}{CYAN}▊ {scenario_id}{RESET}")
    print(f"  {DIM}{bundle.summary.title}{RESET}")
    print(
        f"  Demand history · n={n} days · mean={mean:.2f}/day · std={std:.2f} · "
        f"zero-days={fmt_pct(zero_frac)} · p99={p99:.0f} · max={max_d}"
    )
    print(
        f"  Costs        · unit={fmt_money(unit_cost)} · holding/day={fmt_money(holding)} · "
        f"stockout={fmt_money(stockout_pen)} · fixed_order={fmt_money(fixed_order)} · "
        f"start_inv={starting:.0f}"
    )
    print(
        f"  Lead time    · dist={lt_cfg.get('distribution', '?')} · "
        f"mean={lead_mean:.1f}d · std={float(lt_cfg.get('std_days', 0.0)):.1f}d"
    )

    req = OptimizeRequest(
        scenario_id=scenario_id,
        policy_family="s_S",
        demand_model="empirical_bootstrap",
        lead_time_model=LeadTimeModel(**lt_cfg),
        mode="service_level",
        target_service_level=TARGET_SL,
        costs=CostAssumptions(**costs),
        n_simulations=N_SIMS,
        horizon_days=HORIZON,
        random_seed=SEED,
    )
    resp = run_optimization(req)

    p = resp.recommended_policy
    m = resp.metrics
    exp = resp.explanation

    rule = (
        f"r={p.reorder_point}, S={p.order_up_to}"
        if p.policy_family == "s_S"
        else f"r={p.reorder_point}, Q={p.order_quantity}"
    )
    lt_dem = mean * lead_mean
    print(f"  {BOLD}Recommended{RESET} · {rule} · safety_stock≈{exp.safety_stock}")
    print(f"                (lead-time demand ≈ {lt_dem:.1f}; r covers {p.reorder_point - lt_dem:+.1f})")

    print(
        f"  Metrics      · cost={fmt_money(m.expected_total_cost)} "
        f"(hold {fmt_money(m.expected_holding_cost)} · "
        f"order {fmt_money(m.expected_ordering_cost)} · "
        f"stockout {fmt_money(m.expected_stockout_cost)})"
    )
    print(
        f"  Service      · CSL={fmt_pct(m.cycle_service_level)} · "
        f"fill={fmt_pct(m.fill_rate)} · "
        f"stockout_prob={fmt_pct(m.stockout_probability)} · "
        f"avg_on_hand={m.average_on_hand:.1f} · "
        f"orders/mo={m.average_orders_per_month:.1f}"
    )

    print(f"  {DIM}References vs recommended:{RESET}")
    for c in resp.comparison_policies:
        cm = c.metrics
        cost_arrow = "▲" if c.cost_delta > 0 else ("▼" if c.cost_delta < 0 else "·")
        sl_arrow = "▲" if c.service_level_delta > 0 else ("▼" if c.service_level_delta < 0 else "·")
        crule = (
            f"r={c.policy.reorder_point}, S={c.policy.order_up_to}"
            if c.policy.policy_family == "s_S"
            else f"r={c.policy.reorder_point}, Q={c.policy.order_quantity}"
        )
        print(
            f"    {c.label:<18} {crule:<20} · cost {fmt_money(cm.expected_total_cost):>10} "
            f"({cost_arrow}{fmt_money(abs(c.cost_delta))}) · "
            f"CSL {fmt_pct(cm.cycle_service_level):>6} "
            f"({sl_arrow}{fmt_pct(abs(c.service_level_delta))})"
        )

    print("  " + "─" * 60)
    checks: list[str] = []

    hit_target = m.cycle_service_level >= TARGET_SL - 0.03
    checks.append(
        check(
            hit_target,
            f"CSL {fmt_pct(m.cycle_service_level)} ≥ target {fmt_pct(TARGET_SL)}",
            f"CSL {fmt_pct(m.cycle_service_level)} below target {fmt_pct(TARGET_SL)} — check if grid is too coarse or lead-time model is off",
        )
    )

    cost_total = m.expected_total_cost
    if cost_total > 0:
        stockout_share = m.expected_stockout_cost / cost_total
        holding_share = m.expected_holding_cost / cost_total
        order_share = m.expected_ordering_cost / cost_total
    else:
        stockout_share = holding_share = order_share = 0.0
    checks.append(
        check(
            stockout_share < 0.5,
            f"stockout cost is {fmt_pct(stockout_share)} of total (not dominant)",
            f"stockout cost is {fmt_pct(stockout_share)} of total — dominates the objective, verify penalty is realistic",
        )
    )

    lean = next((c for c in resp.comparison_policies if c.label == "lean"), None)
    conservative = next((c for c in resp.comparison_policies if c.label == "conservative"), None)
    if lean is not None:
        checks.append(
            check(
                lean.metrics.cycle_service_level <= m.cycle_service_level + 0.05,
                f"lean has CSL {fmt_pct(lean.metrics.cycle_service_level)} ≤ recommended (as expected)",
                f"lean beats recommended on CSL — grid may be missing a better cheaper policy",
            )
        )
    if conservative is not None:
        checks.append(
            check(
                conservative.metrics.expected_total_cost >= m.expected_total_cost - 1e-6,
                f"conservative costs ≥ recommended (as expected)",
                f"conservative is cheaper than recommended — grid may not include the true optimum",
            )
        )

    if m.average_orders_per_month > 30:
        checks.append(warn(f"orders/mo={m.average_orders_per_month:.1f} very high; Q may be too small"))
    if m.average_orders_per_month < 0.5 and mean > 1:
        checks.append(warn(f"orders/mo={m.average_orders_per_month:.1f} very low; check fixed order cost"))

    days_of_cover = m.average_on_hand / mean if mean > 0 else float("nan")
    if not np.isnan(days_of_cover):
        checks.append(
            warn(f"avg on-hand ≈ {days_of_cover:.1f} days of mean demand ({m.average_on_hand:.0f} units)")
            if days_of_cover > 60 or days_of_cover < lead_mean * 0.5
            else check(True, f"avg on-hand ≈ {days_of_cover:.1f} days of mean demand — reasonable", "")
        )

    for c in checks:
        print(f"  {c}")


def main() -> None:
    ids = [e["scenario_id"] for e in load_manifest()]
    print(f"{BOLD}Running optimizer QA sweep over {len(ids)} scenarios{RESET}")
    print(f"{DIM}Target CSL={fmt_pct(TARGET_SL)} · s_S policy · empirical bootstrap · "
          f"{N_SIMS} sims · {HORIZON}-day horizon · seed={SEED}{RESET}")
    for sid in ids:
        try:
            run_one(sid)
        except Exception as exc:  # noqa: BLE001
            print(f"\n{RED}✗ {sid} raised: {exc}{RESET}")
            raise


if __name__ == "__main__":
    main()
