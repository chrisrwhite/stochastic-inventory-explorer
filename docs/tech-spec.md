# Stochastic Inventory Reorder / Safety Stock Explorer - Technical Spec

This is the build spec for a small hosted stochastic-optimization demo. A user
chooses a sample item or uploads demand history, configures lead-time
uncertainty and service-level targets, and the app recommends an inventory
policy: reorder point, order quantity, order-up-to level, and safety stock.

The signature UX is:

> "Here is the inventory policy, here is the stockout-risk distribution behind
> it, and here is the cost/service tradeoff if you choose a more aggressive or
> more conservative policy."

This project is the cleanest non-retirement stochastic optimization artifact in
the portfolio. It is supply-chain native, useful to everyday visitors, and avoids
the legal/reputational drag of personal-finance advice.

**Working directory (target repo):** `stochastic-inventory-reorder/`,
publishable as a standalone GitHub repo and linkable from
`mle-portfolio/src/data/projects.ts`.

---

## 1. Positioning

### 1.1 Portfolio role

This project is now the top-ranked stochastic build candidate. It demonstrates:

- stochastic demand modeling
- uncertain supplier lead times
- safety-stock / reorder-point math
- Monte Carlo policy evaluation
- chance constraints and CVaR-style tail-risk metrics
- an interactive cost vs service frontier
- full-stack implementation around an optimization core

It also has two clean framings:

- **Professional:** small-business / supply-chain reorder policy.
- **Everyday:** household essentials reorder planner.

That dual framing makes it more approachable than retirement withdrawals and
more directly stochastic than deterministic warehouse assignment.

### 1.2 What this is not

This app is not an ERP, not a pantry tracker, not a procurement system, and not
a purchase-order execution tool. It does not store personal inventory. It is a
stateless educational decision tool for understanding reorder policies under
uncertainty.

The About page should say:

> This demo models demand and lead-time uncertainty to compare reorder policies
> under service-level and inventory-cost tradeoffs. It is an educational
> stochastic-optimization app, not an inventory-management system or purchasing
> recommendation engine.

### 1.3 V1 scope walls

V1 supports:

- bundled sample datasets
- optional CSV upload of historical daily/weekly demand
- demand-distribution fitting
- lead-time-distribution configuration
- policy comparison across `(r, Q)` and `(s, S)` style rules
- service-level and fill-rate metrics
- expected cost and stockout-tail-risk metrics
- scenario comparison

V1 does not support:

- persistent user accounts
- barcode scanning
- vendor integrations
- purchase-order execution
- multi-echelon networks
- hundreds of SKUs in one solve
- live ERP data

---

## 2. Product UX

### 2.1 Primary user story

A visitor chooses a sample scenario:

- coffee beans for a household
- diapers for a family
- spare parts for a repair shop
- ingredients for a small bakery
- slow-moving industrial parts

The visitor clicks "Optimize Policy" and sees:

1. recommended reorder point
2. recommended order quantity or order-up-to level
3. expected monthly inventory cost
4. probability of stockout
5. fill rate
6. worst-5% stockout loss / CVaR
7. service-level vs cost frontier
8. simulated inventory paths

### 2.2 Main screens

- **Configure** - choose sample item, demand model, lead-time model, cost
  assumptions, and target service level.
- **Policy Frontier** - plot inventory cost vs service level / stockout risk.
- **Simulation** - show inventory paths, reorder events, stockouts, and
  distribution of outcomes.
- **Policy Details** - explain why the selected policy was chosen.
- **Scenario Compare** - compare conservative, balanced, and lean policies.
- **Methodology** - explain safety stock, reorder points, chance constraints,
  and CVaR.

### 2.3 Killer interaction

Move the service-level slider from 90% to 99%. The app redraws:

- reorder point
- safety stock
- expected inventory cost
- stockout probability
- tail stockout loss
- simulated inventory trajectories

The visitor should immediately see that higher service levels require more
inventory and lower stockout risk.

---

## 3. Stack

| Layer | Choice |
| --- | --- |
| Python runtime | Python 3.12 slim |
| Backend | FastAPI + Uvicorn |
| Optimization | NumPy / SciPy grid search; optional OR-Tools for constrained variants |
| Simulation | NumPy random generators with fixed seeds |
| Data | pandas, pydantic v2 |
| Frontend | React + Vite + TypeScript |
| Styling | Tailwind + shadcn/ui |
| Charts | Recharts |
| State | React Context + useReducer |
| Deploy | Docker multi-stage to Cloud Run |
| Tests | pytest, FastAPI TestClient, Vitest |

This project does not need a heavy solver in V1. A transparent policy grid
search with Monte Carlo evaluation is easier to explain and more robust on cheap
hosting. OR-Tools can be added for constrained multi-SKU variants later.

---

## 4. Data Model

### 4.1 Scenario manifest

`data/scenarios/MANIFEST.json`

Fields:

- `scenario_id`
- `title`
- `description`
- `domain`
- `source`
- `downloaded_at`
- `sha256`

### 4.2 Demand history

`data/scenarios/<scenario_id>/demand.csv`

Required columns:

- `date`
- `sku_id`
- `demand_units`

Optional columns:

- `promotion_flag`
- `weekday`
- `price`
- `stockout_observed`

### 4.3 Cost assumptions

`data/scenarios/<scenario_id>/costs.yaml`

Fields:

- `unit_cost`
- `holding_cost_per_unit_per_day`
- `stockout_cost_per_unit`
- `fixed_order_cost`
- `variable_order_cost_per_unit`
- `starting_inventory`
- `review_period_days`

### 4.4 Lead-time assumptions

`data/scenarios/<scenario_id>/lead_time.yaml`

Fields:

- `distribution`: empirical, discrete, lognormal, poisson_shifted
- `mean_days`
- `std_days`
- `min_days`
- `max_days`
- `samples`

V1 should make lead time editable in the UI even when demand history is fixed.

---

## 5. Stochastic Model

### 5.1 Demand process

Supported V1 demand models:

- empirical bootstrap from historical demand
- Poisson
- negative binomial for overdispersed demand
- seasonal empirical bootstrap by weekday / week-of-year

For portfolio clarity, default to empirical bootstrap. It is easy to explain:

> Future demand days are sampled from observed historical demand days, preserving
> realistic spikes without assuming a perfect distribution.

### 5.2 Lead-time process

Supported V1 lead-time models:

- fixed lead time
- empirical discrete distribution
- triangular distribution from min / most likely / max
- lognormal approximation

### 5.3 Inventory dynamics

For each simulated day `t`:

```text
inventory_position[t] = on_hand[t] + on_order[t] - backorders[t]
```

Demand consumes on-hand inventory:

```text
fulfilled[t] = min(on_hand[t], demand[t])
stockout[t] = max(0, demand[t] - on_hand[t])
on_hand[t+1] = on_hand[t] - fulfilled[t] + receipts[t]
```

### 5.4 Policies

V1 supports two policies.

Reorder point / fixed quantity `(r, Q)`:

```text
if inventory_position <= r:
    order Q
```

Order-up-to `(s, S)`:

```text
if inventory_position <= s:
    order S - inventory_position
```

The UI can call these:

- "Fixed order size"
- "Order up to target"

Use plain names in the interface; keep `(r, Q)` and `(s, S)` in Methodology.

---

## 6. Policy Optimization

### 6.1 Candidate policy grid

Generate candidate policies:

- reorder point `r`: from 0 to a high quantile of demand during lead time
- order quantity `Q`: from average cycle demand to several weeks of demand
- order-up-to `S`: from `r + average demand` to `r + high quantile demand`

Evaluate each policy with Monte Carlo simulation.

### 6.2 Metrics

For each policy compute:

- expected total cost
- expected holding cost
- expected ordering cost
- expected stockout cost
- cycle service level
- fill rate
- average on-hand inventory
- average orders per month
- probability of any stockout
- CVaR of stockout units or stockout cost

### 6.3 Feasibility / target selection

If the user sets target service level:

```text
minimize expected_total_cost
subject to service_level >= target
```

If the user sets target stockout risk:

```text
minimize expected_total_cost
subject to P(stockout) <= alpha
```

If the user chooses tail-risk mode:

```text
minimize expected_total_cost
subject to CVaR_stockout_cost <= budget
```

### 6.4 Frontier

The app should show a frontier of policies:

- x-axis: expected inventory cost
- y-axis: service level or stockout risk
- color: average inventory
- selected point: recommended policy

This is the main visual differentiator.

---

## 7. Explainability Layer

### 7.1 Policy explanation

For the selected policy, show:

- expected demand during lead time
- uncertainty buffer / safety stock
- service-level target
- cost tradeoff vs lean policy
- cost tradeoff vs conservative policy
- dominant cost driver

Example:

> The selected reorder point is 42 units. Average demand during lead time is 29
> units, and the remaining 13 units are safety stock. This raises expected
> holding cost by $18/month compared with the lean policy, but reduces stockout
> probability from 17% to 4%.

### 7.2 Scenario explanation

For each simulated path, allow the user to inspect:

- reorder trigger date
- order arrival date
- stockout days
- maximum backorder
- ending inventory

### 7.3 Why alternatives lost

Compare the selected policy to:

- lean policy
- conservative policy
- naive "order when empty" policy
- simple average-demand policy

Show:

- cost difference
- stockout-risk difference
- inventory difference

---

## 8. API Design

### 8.1 Endpoints

- `GET /api/health`
- `GET /api/data-info`
- `GET /api/scenarios`
- `POST /api/optimize`
- `POST /api/simulate`
- `POST /api/compare`
- `POST /api/upload-demand`

### 8.2 Optimize request

```json
{
  "scenario_id": "household_coffee",
  "policy_family": "order_up_to",
  "demand_model": "empirical_bootstrap",
  "lead_time_model": {
    "distribution": "triangular",
    "min_days": 2,
    "mode_days": 4,
    "max_days": 8
  },
  "target_service_level": 0.95,
  "n_simulations": 5000,
  "horizon_days": 180,
  "random_seed": 42
}
```

### 8.3 Optimize response

```json
{
  "status": "ok",
  "recommended_policy": {
    "policy_family": "order_up_to",
    "reorder_point": 42,
    "order_up_to": 78,
    "safety_stock": 13
  },
  "metrics": {
    "expected_total_cost": 312.44,
    "service_level": 0.953,
    "fill_rate": 0.982,
    "stockout_probability": 0.047,
    "cvar_stockout_cost": 38.12
  },
  "frontier": [],
  "comparison_policies": [],
  "simulation_paths": []
}
```

---

## 9. Frontend Components

- `ScenarioSelector`
- `DemandModelSelector`
- `LeadTimeEditor`
- `CostAssumptionEditor`
- `ServiceLevelSlider`
- `PolicyFrontierChart`
- `InventoryPathFanChart`
- `PolicySummaryCards`
- `WhyThisPolicyPanel`
- `ScenarioCompare`
- `MethodologyPage`
- `LegalPages`

V1 should make the default sample scenario compelling without uploads.

---

## 10. Tests

### 10.1 Core tests

- demand bootstrap is deterministic with fixed seed
- lead-time sampler respects support
- inventory balance equations hold
- `(r, Q)` policy places orders correctly
- `(s, S)` policy places orders correctly
- metrics match hand-computed toy cases
- target service-level filter selects feasible minimum-cost policy

### 10.2 Golden fixtures

Create small deterministic cases:

- constant demand, fixed lead time
- zero demand
- demand spike
- long lead-time tail
- infeasible high service target with capped inventory

### 10.3 API tests

- `/api/health` returns ok
- `/api/scenarios` lists bundled scenarios
- `/api/optimize` returns policy, metrics, and frontier
- uploaded CSV validation catches missing columns

---

## 11. Rollout Milestones

### M0 - scaffold and sample scenarios (0.5 weekend)

- repo skeleton
- sample datasets
- demand and cost schemas
- scenario manifest
- README outline

### M1 - simulation core (1 weekend)

- demand samplers
- lead-time samplers
- inventory dynamics
- policy simulation
- metrics
- core tests

### M2 - optimizer and frontier (1 weekend)

- candidate policy grid
- service-level constrained selection
- CVaR stockout metric
- comparison policies
- API endpoints

### M3 - frontend v1 (1 weekend)

- config page
- frontier chart
- inventory fan chart
- policy explanation panel
- scenario compare

### M4 - deploy and writeup (0.5 weekend)

- Docker build
- Cloud Run deploy
- methodology page
- portfolio entry

**Total:** roughly 4 weekends. A narrower household-essentials-only version can
ship in 2.5-3 weekends.

---

## 12. Risks

- **Looks like a calculator, not an app:** make the frontier and simulation
  paths the center of the UX.
- **Too similar to generic safety-stock calculators:** emphasize stochastic
  simulation, lead-time uncertainty, CVaR tail risk, and explainability.
- **CSV upload rabbit hole:** bundled scenarios must carry the demo.
- **Too much supply-chain jargon:** use plain language first, math second.

---

## 13. Recommendation

Build this if the next portfolio goal is to prove stochastic optimization in a
supply-chain-native, visitor-useful way. It is the best replacement for SWR as
the stochastic flagship: less legal risk, stronger resume alignment, and a
clearer everyday-life hook.
