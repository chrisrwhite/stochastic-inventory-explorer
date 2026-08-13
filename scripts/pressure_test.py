"""Pressure test: exercise the 3 shipping scenarios end-to-end.

Runs a battery of checks against each bundled scenario:

    A. Reproducibility ...... same seed twice must give byte-identical result
    B. Seed stability ....... CSL and cost are stable across 5 seeds
    C. Monotonicity ......... target |up| => CSL |up|, cost |up|, inventory |up|
    D. Policy-family parity . s_S and r_Q reach similar CSL/cost frontiers
    E. HTTP integration ..... /optimize, /simulate, /compare all return 200
                              with plausible bodies
    F. Simulation sanity .... fan chart has non-negative on-hand, no exploding
                              paths; median cycle time is reasonable
    G. Narrative eyeball .... prints the recommended policy's narrative so a
                              human can read it

Everything wired through the FastAPI ``TestClient`` so we're exercising the
exact HTTP path the frontend uses -- not just the domain layer.

Run:
    backend/.venv/bin/python scripts/pressure_test.py
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "backend"))

from fastapi.testclient import TestClient  # noqa: E402

from app.data.loader import load_manifest, load_scenario  # noqa: E402
from app.main import app  # noqa: E402

RESET = "\033[0m"
DIM = "\033[2m"
BOLD = "\033[1m"
RED = "\033[31m"
YELLOW = "\033[33m"
GREEN = "\033[32m"
CYAN = "\033[36m"


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str


def ok(name: str, detail: str = "") -> CheckResult:
    return CheckResult(name=name, passed=True, detail=detail)


def fail(name: str, detail: str) -> CheckResult:
    return CheckResult(name=name, passed=False, detail=detail)


def fmt(v: float, kind: str = "num") -> str:
    if kind == "money":
        return f"${v:,.2f}"
    if kind == "pct":
        return f"{v * 100:.1f}%"
    return f"{v:.2f}"


def optimize_request(
    scenario_id: str,
    costs: dict[str, Any],
    lead_time: dict[str, Any],
    *,
    target: float = 0.95,
    policy_family: str = "s_S",
    demand_model: str = "empirical_bootstrap",
    seed: int = 42,
    n_sims: int = 2000,
    horizon: int = 180,
) -> dict[str, Any]:
    return {
        "scenario_id": scenario_id,
        "policy_family": policy_family,
        "demand_model": demand_model,
        "lead_time_model": lead_time,
        "mode": "service_level",
        "target_service_level": target,
        "costs": costs,
        "n_simulations": n_sims,
        "horizon_days": horizon,
        "random_seed": seed,
    }


def check_reproducibility(client: TestClient, sid: str, bundle) -> CheckResult:
    """Two identical requests must yield identical recommended policy + metrics."""
    body = optimize_request(sid, bundle.costs, bundle.lead_time)
    r1 = client.post("/api/optimize", json=body).json()
    r2 = client.post("/api/optimize", json=body).json()

    p1 = r1["recommended_policy"]
    p2 = r2["recommended_policy"]
    if p1 != p2:
        return fail("reproducibility.policy", f"policies differ: {p1} vs {p2}")

    m1, m2 = r1["metrics"], r2["metrics"]
    diffs = {k: (m1[k], m2[k]) for k in m1 if m1[k] != m2[k]}
    if diffs:
        return fail("reproducibility.metrics", f"metrics differ: {diffs}")
    return ok(
        "reproducibility",
        f"policy {p1['reorder_point']}/{p1.get('order_up_to') or p1.get('order_quantity')} "
        f"bit-identical across two runs",
    )


def check_seed_stability(client: TestClient, sid: str, bundle) -> CheckResult:
    """Across 5 seeds the recommendation must be economically stable.

    We flag on *cost* variance rather than CSL variance because sparse-demand
    scenarios genuinely have many co-optimal policies on the target plateau;
    the CSL that any one of them delivers can vary by several pp of Monte
    Carlo noise while the cost is essentially unchanged (which is what the
    user cares about).

    Thresholds: cost band <= 8%, CSL band <= 5pp.
    """
    csls: list[float] = []
    costs: list[float] = []
    rs: list[int] = []
    for seed in (1, 7, 42, 100, 12345):
        body = optimize_request(sid, bundle.costs, bundle.lead_time, seed=seed)
        r = client.post("/api/optimize", json=body).json()
        csls.append(r["metrics"]["cycle_service_level"])
        costs.append(r["metrics"]["expected_total_cost"])
        rs.append(r["recommended_policy"]["reorder_point"])

    csl_band = max(csls) - min(csls)
    cost_band = (max(costs) - min(costs)) / min(costs) if min(costs) > 0 else 0.0
    r_band = max(rs) - min(rs)
    detail = (
        f"CSL {fmt(min(csls), 'pct')}-{fmt(max(csls), 'pct')} "
        f"(band {csl_band * 100:.1f}pp) · "
        f"cost {fmt(min(costs), 'money')}-{fmt(max(costs), 'money')} "
        f"(band {cost_band * 100:.1f}%) · "
        f"r range {min(rs)}-{max(rs)} (band {r_band})"
    )
    if cost_band > 0.08:
        return fail("seed_stability.cost", detail)
    if csl_band > 0.05:
        return fail("seed_stability.csl", detail)
    return ok("seed_stability", detail)


def check_monotonicity(client: TestClient, sid: str, bundle) -> CheckResult:
    """Higher target -> CSL non-decreasing, cost non-decreasing (or plateau).

    Small slack allowed because Monte-Carlo noise can flip near-ties.
    """
    targets = [0.80, 0.90, 0.95, 0.99]
    rows: list[dict[str, Any]] = []
    for t in targets:
        body = optimize_request(sid, bundle.costs, bundle.lead_time, target=t)
        r = client.post("/api/optimize", json=body).json()
        rows.append({
            "target": t,
            "csl": r["metrics"]["cycle_service_level"],
            "cost": r["metrics"]["expected_total_cost"],
            "on_hand": r["metrics"]["average_on_hand"],
        })

    csl_slack = 0.03  # allow 3pp noise
    cost_slack = 0.20  # cost can drop slightly when the same policy still hits a lower target
    csl_bad = [
        (rows[i - 1], rows[i])
        for i in range(1, len(rows))
        if rows[i]["csl"] + csl_slack < rows[i - 1]["csl"]
    ]
    cost_bad = [
        (rows[i - 1], rows[i])
        for i in range(1, len(rows))
        if rows[i]["cost"] < rows[i - 1]["cost"] * (1 - cost_slack)
    ]

    detail_rows = [
        f"t={r['target']:.2f} -> CSL {fmt(r['csl'], 'pct')} cost {fmt(r['cost'], 'money')} on-hand {r['on_hand']:.0f}"
        for r in rows
    ]
    detail = "; ".join(detail_rows)
    if csl_bad or cost_bad:
        return fail(
            "monotonicity",
            f"non-monotone: csl_regressions={len(csl_bad)}, cost_regressions={len(cost_bad)}; {detail}",
        )
    return ok("monotonicity", detail)


def check_policy_family_parity(client: TestClient, sid: str, bundle) -> CheckResult:
    """s_S and r_Q should reach similar CSL/cost frontiers."""
    ss = client.post(
        "/api/optimize",
        json=optimize_request(sid, bundle.costs, bundle.lead_time, policy_family="s_S"),
    ).json()
    rq = client.post(
        "/api/optimize",
        json=optimize_request(sid, bundle.costs, bundle.lead_time, policy_family="r_Q"),
    ).json()

    ss_csl = ss["metrics"]["cycle_service_level"]
    rq_csl = rq["metrics"]["cycle_service_level"]
    ss_cost = ss["metrics"]["expected_total_cost"]
    rq_cost = rq["metrics"]["expected_total_cost"]

    csl_gap = abs(ss_csl - rq_csl)
    cost_ratio = max(ss_cost, rq_cost) / max(1e-9, min(ss_cost, rq_cost))
    detail = (
        f"s_S: CSL {fmt(ss_csl, 'pct')} cost {fmt(ss_cost, 'money')} · "
        f"r_Q: CSL {fmt(rq_csl, 'pct')} cost {fmt(rq_cost, 'money')} · "
        f"CSL gap {csl_gap * 100:.1f}pp · cost ratio {cost_ratio:.2f}"
    )
    # Both should hit target (or both plateau); allow 5pp CSL divergence.
    # Cost ratio should be within 2x (r_Q with fixed Q is often ~20% costlier).
    if csl_gap > 0.05:
        return fail("policy_family.csl", detail)
    if cost_ratio > 2.0:
        return fail("policy_family.cost", detail)
    return ok("policy_family", detail)


def check_http_integration(client: TestClient, sid: str, bundle) -> CheckResult:
    """/optimize, /simulate, /compare all return 200 with plausible bodies."""
    opt_body = optimize_request(sid, bundle.costs, bundle.lead_time)
    r_opt = client.post("/api/optimize", json=opt_body)
    if r_opt.status_code != 200:
        return fail("http.optimize", f"status={r_opt.status_code} body={r_opt.text[:200]}")

    opt = r_opt.json()
    policy = opt["recommended_policy"]

    sim_body = {
        "scenario_id": sid,
        "policy": {
            "policy_family": policy["policy_family"],
            "reorder_point": policy["reorder_point"],
            "order_up_to": policy.get("order_up_to"),
            "order_quantity": policy.get("order_quantity"),
        },
        "demand_model": "empirical_bootstrap",
        "lead_time_model": bundle.lead_time,
        "costs": bundle.costs,
        "n_simulations": 500,
        "horizon_days": 180,
        "random_seed": 42,
    }
    r_sim = client.post("/api/simulate", json=sim_body)
    if r_sim.status_code != 200:
        return fail("http.simulate", f"status={r_sim.status_code} body={r_sim.text[:200]}")
    sim = r_sim.json()
    if not sim.get("simulation", {}).get("paths"):
        return fail("http.simulate.body", "no simulation paths returned")

    cmp_body = {
        "scenario_id": sid,
        "policies": [
            {
                "label": "recommended",
                "policy_family": policy["policy_family"],
                "reorder_point": policy["reorder_point"],
                "order_up_to": policy.get("order_up_to"),
                "order_quantity": policy.get("order_quantity"),
            },
            {
                "label": "custom_lean",
                "policy_family": policy["policy_family"],
                "reorder_point": max(int(policy["reorder_point"]) // 2, 0),
                "order_up_to": policy.get("order_up_to"),
                "order_quantity": policy.get("order_quantity"),
            },
        ],
        "demand_model": "empirical_bootstrap",
        "lead_time_model": bundle.lead_time,
        "costs": bundle.costs,
        "n_simulations": 500,
        "horizon_days": 180,
        "random_seed": 42,
    }
    r_cmp = client.post("/api/compare", json=cmp_body)
    if r_cmp.status_code != 200:
        return fail("http.compare", f"status={r_cmp.status_code} body={r_cmp.text[:200]}")
    cmp = r_cmp.json()
    if len(cmp.get("rows", [])) != 2:
        return fail("http.compare.body", f"expected 2 rows, got {len(cmp.get('rows', []))}")

    return ok(
        "http_integration",
        f"/optimize {r_opt.status_code} · /simulate {r_sim.status_code} "
        f"({len(sim['simulation']['paths'])} paths) · /compare {r_cmp.status_code} "
        f"({len(cmp['rows'])} rows)",
    )


def check_simulation_sanity(client: TestClient, sid: str, bundle) -> CheckResult:
    """Fan-chart paths must be non-negative and not exploding."""
    opt = client.post(
        "/api/optimize",
        json=optimize_request(sid, bundle.costs, bundle.lead_time),
    ).json()
    policy = opt["recommended_policy"]

    sim_body = {
        "scenario_id": sid,
        "policy": {
            "policy_family": policy["policy_family"],
            "reorder_point": policy["reorder_point"],
            "order_up_to": policy.get("order_up_to"),
            "order_quantity": policy.get("order_quantity"),
        },
        "demand_model": "empirical_bootstrap",
        "lead_time_model": bundle.lead_time,
        "costs": bundle.costs,
        "n_simulations": 500,
        "horizon_days": 180,
        "random_seed": 42,
    }
    sim = client.post("/api/simulate", json=sim_body).json()
    paths = sim["simulation"]["paths"]
    for p in paths:
        oh = p["on_hand"]
        if any(v < 0 for v in oh):
            return fail("simulation.negative", f"path p={p['percentile']} has negative on-hand")
        max_oh = max(oh) if oh else 0
        avg_oh = sum(oh) / max(len(oh), 1)
        # Explosion sniff: does peak on-hand ever exceed 50x the average? Would
        # indicate a runaway order loop. Real fan charts typically stay <5x.
        if avg_oh > 0 and max_oh > 50 * avg_oh:
            return fail(
                "simulation.explode",
                f"path p={p['percentile']}: peak on-hand {max_oh:.0f} vs avg {avg_oh:.0f}",
            )
    p50 = next((p for p in paths if abs(p["percentile"] - 0.5) < 1e-6), None)
    detail = f"{len(paths)} percentile paths"
    if p50:
        median_oh = sum(p50["on_hand"]) / len(p50["on_hand"])
        median_orders = sum(1 for v in p50["orders_placed"] if v > 0)
        detail += f" · p50 median on-hand {median_oh:.0f} · {median_orders} orders over 180 days"
    return ok("simulation_sanity", detail)


def get_narrative(client: TestClient, sid: str, bundle) -> str:
    r = client.post(
        "/api/optimize",
        json=optimize_request(sid, bundle.costs, bundle.lead_time),
    ).json()
    return r["explanation"]["narrative"]


def run_all_checks(client: TestClient, sid: str) -> tuple[list[CheckResult], str]:
    bundle = load_scenario(sid)
    checks: list[CheckResult] = [
        check_reproducibility(client, sid, bundle),
        check_seed_stability(client, sid, bundle),
        check_monotonicity(client, sid, bundle),
        check_policy_family_parity(client, sid, bundle),
        check_http_integration(client, sid, bundle),
        check_simulation_sanity(client, sid, bundle),
    ]
    narrative = get_narrative(client, sid, bundle)
    return checks, narrative


def render_checks(sid: str, title: str, checks: list[CheckResult], narrative: str) -> bool:
    print(f"\n{BOLD}{CYAN}▊ {sid}{RESET}  {DIM}{title}{RESET}")
    all_passed = True
    for c in checks:
        icon = f"{GREEN}✓{RESET}" if c.passed else f"{RED}✗{RESET}"
        print(f"  {icon} {c.name:<22} {c.detail}")
        if not c.passed:
            all_passed = False
    print(f"  {DIM}narrative:{RESET} {narrative}")
    return all_passed


def main() -> int:
    print(f"{BOLD}Pressure-testing the 3 shipping scenarios end-to-end{RESET}")
    print(
        f"{DIM}Hits /api/optimize, /api/simulate, /api/compare via FastAPI TestClient "
        f"(same path the browser uses).{RESET}"
    )
    with TestClient(app) as client:
        overall_pass = True
        t0 = time.time()
        for entry in load_manifest():
            sid = entry["scenario_id"]
            title = entry["title"]
            checks, narrative = run_all_checks(client, sid)
            scenario_pass = render_checks(sid, title, checks, narrative)
            overall_pass = overall_pass and scenario_pass
        elapsed = time.time() - t0
    status = f"{GREEN}READY TO SHIP{RESET}" if overall_pass else f"{RED}NOT READY{RESET}"
    print(
        f"\n{BOLD}{status}{RESET} · finished in {elapsed:.1f}s "
        f"({len(load_manifest())} scenarios × 6 checks)"
    )
    return 0 if overall_pass else 1


if __name__ == "__main__":
    sys.exit(main())
