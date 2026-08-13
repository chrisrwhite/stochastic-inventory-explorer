# How much should you order? A stochastic optimization demo you can actually play with

*Building an inventory-policy optimizer that reasons over thousands of possible futures, and shipping it as a live web app.*

<!--
Cover image:
  Replace this comment with the demo GIF or screenshot before publishing.
  Suggested source: docs/hero.gif (see docs/hero-placeholder.md for what to capture).
-->

**TL;DR** &nbsp;&nbsp; I built a small web app that solves a textbook inventory problem in a slightly non-textbook way. Instead of choosing a reorder policy from a single demand forecast, it defines the problem over thousands of simulated futures and returns the policy with the best expected outcome across all of them. It runs on three real point-of-sale datasets (Walmart, UCI Online Retail), shows you the whole cost-vs-reliability tradeoff, and explains its recommendation in plain English. Try it live at **<https://inventory.christopherrobertwhite.com>**, or read the code at **<https://github.com/chrisrwhite/stochastic-inventory-explorer>**.

---

## The one-forecast problem

Imagine you run inventory for a single SKU. Somebody hands you a demand forecast: "we expect to sell about 12 units a day." Great. You do the math: if a shipment takes five days, you'll sell 60 units during the wait, so you should reorder when stock drops to 60.

Then Tuesday happens and you sell 34 units.

This is the failure mode of running inventory off a point forecast: the forecast is right *on average*, and average is exactly the wrong thing to plan against. What actually matters is the shape of the distribution. A quiet SKU with a small standard deviation needs almost no safety buffer. A bursty SKU with occasional 4,000-unit spikes might need a much bigger one, or might need you to accept that you'll stock out sometimes because holding enough inventory to cover every spike would eat your entire margin.

The fix is well known in operations research, and it's older than most of us: **stochastic optimization**. Instead of optimizing against one forecast, you optimize against a distribution of possible futures. You pick the policy that performs best *across* those futures, weighted by how likely each one is. Whether the policy is "conservative" or "aggressive" is no longer a personality trait, it's a knob you turn.

That's the idea behind the demo.

## What I built

A three-page web app that lets you:

1. Pick one of three real POS scenarios (a steady Walmart pantry item, an intermittent Walmart hobbies item, and a heavy-tailed UK gift-shop item from UCI Online Retail II).
2. Configure lead-time uncertainty and pick a reliability target.
3. Click **Optimize**. The backend spins up a grid of about 240 candidate reorder policies, runs 1,000 Monte Carlo simulations of a 180-day future against each one, scores them, and returns the cheapest policy that meets your reliability target.
4. Inspect the result: the recommended policy in plain English, the full cost-vs-reliability Pareto frontier, a fan chart of simulated inventory paths, and a side-by-side comparison against textbook rules.

You can try it here: **<https://inventory.christopherrobertwhite.com>**

The stack is FastAPI plus NumPy on the backend, React plus Vite plus TypeScript on the frontend, Docker to Google Cloud Run for hosting, and Cloudflare for DNS. The full method write-up (with mermaid diagrams, math, and an honest comparison to solver-based alternatives) is in **[FORMULATION.md](https://github.com/chrisrwhite/stochastic-inventory-explorer/blob/main/FORMULATION.md)** on the repo.

## The core idea in one paragraph

You have a reorder policy `π` (for example: "when inventory drops to 60 units, order 100 more"). You have random future daily demand `D_t` and random lead times `L_i`. Under any given policy, your total cost `C(π)` for a 180-day horizon is a random variable, driven by holding cost, ordering cost, and stockout penalties. Instead of optimizing against a single deterministic future, you optimize the **expected** cost across many random ones, subject to a reliability constraint you choose:

```text
minimize     E[ C(π) ]
subject to   Pr(stockout on any day | π) ≤ 1 − α
```

α is your reliability target: 95%, 99%, whatever your business tolerates. The expectation is approximated by the sample mean over N=1,000 simulated futures, a standard technique in stochastic programming called **Sample Average Approximation** (SAA). Everything else in the app is engineering around that one formulation.

N=1,000 is a deliberate trade, and an instructive one. Sampling error shrinks as 1/√N, so the next decimal place of precision costs a hundredfold in compute — and the app has a human waiting on it. What makes 1,000 defensible isn't that the estimate has stopped moving; it's that the *part you're asking about* has. Across all three scenarios and both policy families, the reorder point — the number that decides whether you hit your reliability target — is identical at N=1,000 and N=2,000. The order quantity, which lives on a genuinely flat part of the cost surface, still wanders by up to 18%. Knowing which of your outputs has converged and which is still wandering is most of what SAA asks you to think about.

## The bit where I resist showing off with a solver

Purists reading this may be raising an eyebrow at "grid search plus Monte Carlo." Why not formulate it as a mixed-integer program and hand it to Gurobi? A few reasons.

First, the policy space is genuinely small. A reorder policy is two integers, `r` and `Q` (or `r` and `S` for the order-up-to family). The interesting range for each is a couple hundred units at most. That's a few thousand candidates before you dedupe, and the vectorized NumPy simulator I wrote scores the whole grid in about one to two seconds. Grid search converges to a global optimum within one unit of the true optimum, without any big-M constraints, warm-start heuristics, or license fees.

Second, the dynamics are non-convex. Inventory is a piecewise function of past demand and past orders. Threshold-triggered ordering is a discrete event. Encoding that in an MIP is possible, but the model gets ugly fast, and the solve time balloons for reasons that don't have much to do with the math and a lot to do with the modeling.

Third, the demand distribution is *empirical*. Real POS data is bursty, has zero-days, and doesn't follow a nice parametric family. Even a solver-based formulation would need to reduce that empirical distribution to a finite set of scenarios, at which point it's doing SAA anyway. So the honest choice is to skip the middleman and simulate directly.

There's a broader lesson in there, I think, about picking the simplest tool that gives you the right shape of answer. Which brings me to the frontier.

## What "reliability" actually costs

The single most useful visualization in the app is the **cost-vs-reliability frontier**. Every candidate policy is a dot on a scatter plot. The x-axis is expected monthly cost. The y-axis is the probability a random day ends without a stockout.

The upper-left edge of that cloud is the **Pareto frontier**: the set of policies that aren't dominated by anything else. If a policy is on the frontier, no other policy in the grid gives you more reliability at the same cost, or the same reliability at lower cost. Everything below the frontier is strictly worse and can be ignored.

Once you can see the frontier, one of the app's headline lessons appears immediately: **the last 5% of reliability costs a lot**. Going from 90% to 95% might cost you 20% more inventory. Going from 95% to 99% might double the inventory bill. On the heavy-tailed UK scenario, 99% isn't even reachable at any cost, because the demand distribution has a fat enough tail that no finite buffer covers every spike.

This is not a novel observation in OR, but it *is* new to almost every non-specialist I've shown the app to. Getting people to internalize that reliability is a knob with real dollars behind it, not a moral commitment to "good customer service," was the primary UX goal.

## Three real scenarios, three lessons

I resisted the temptation to ship ten scenarios. Three is enough to teach the story, and each one is deliberately chosen to break a different intuition:

1. **`walmart_pantry_m5`** — a Walmart Los Angeles pantry item, about 12 units per day, roughly 5% zero-days. The clean baseline. The optimizer's recommendation matches what a well-tuned Newsvendor-style rule would tell you, and the frontier has a nice smooth shape. Useful as an anchor.

2. **`walmart_hobbies_sparse_m5`** — another Walmart LA item, but hobbies, and very slow-moving. About 85% zero-days, roughly 0.2 units per day on average. Here the intuition-breaker is that **cycle service level** (the probability of no-stockout on a given day) and **fill rate** (the fraction of demanded units served) diverge sharply. A policy can hit 95% reliability at very low cost simply because most days have zero demand, but that number is misleading. Fill rate tells a truer story for intermittent SKUs.

3. **`retail_online_uk`** — a heavy-tailed UK gift-shop item from UCI Online Retail II. The median day sells 88 of them; the biggest day sells over 4,000. On this one, no policy in the grid reaches 95% cycle service level. The app *tells you* that explicitly, switches its narrative to explain why, and suggests fill rate as the better success metric. Getting that graceful-failure behavior right was one of the more educational things about the build.

I think a portfolio app is more useful when it can articulate the limits of its own method. This one tries to.

## Design decisions I'd defend in a technical interview

A few things I made deliberate calls on:

- **Real data over synthetic curves.** Every demand history you see is real POS data. Cost assumptions are illustrative (median observed prices plus reasonable domain assumptions), but the demand shape is untouched. I think portfolio demos that generate their own bell curves are subtly dishonest; real data has zero-days and outliers and weekly seasonality, and the model needs to handle those or admit that it doesn't.

- **Progressive disclosure.** The default UI shows the four inputs that actually matter (scenario, lead time, costs, reliability target). Everything else, including policy family (`r,Q` vs `s,S`), demand model choice (bootstrap vs Poisson vs negative binomial), and Monte Carlo horizon, is tucked behind an "Advanced" panel. I built the full version first, then hid two-thirds of it. The results tab is dramatically more legible for a non-specialist visitor.

- **Explicit optimization trigger.** Early versions re-optimized on every parameter change. It was fluid but disorienting: users couldn't tell which knob caused which effect. Now optimization runs only when you click Optimize, with a phase-based progress bar. Costs a click, buys a mental model.

- **Explainability panel.** Every recommendation comes with a plain-English breakdown: expected demand during the lead time, how much of the reorder point is safety stock, which cost component (holding, ordering, stockout) is dominant, and how the recommendation compares to four textbook reference rules. If a model can't explain itself, you can't trust it, and if it can't compare itself to something simpler, you can't say it's earning its complexity.

- **Ship the notebook too.** For people who'd rather read Python than click through a UI, the same optimizer is exposed end-to-end in a Jupyter notebook, wired to the same domain layer the API calls. Every parameter is at the top, every intermediate is visualized, no server required.

## What I'd change next

A few honest limitations I'd tackle if this were headed to production, not just to a portfolio:

- **The policy grid is discrete.** For a continuous version you'd move to a stochastic approximation method or something like SPSA. Not hard, mostly not necessary at this scale, but it would matter for a much larger SKU catalog.

- **Only one SKU at a time.** Real inventory decisions are joint: shared warehouse capacity, joint reorder cycles, substitution effects between SKUs. That's a whole different class of problem (multi-echelon, capacitated), and it's the interesting next step.

- **Costs are illustrative.** In the wild, unit cost is a negotiation, holding cost is often mis-attributed, and stockout penalty is a business-strategy discussion, not a number. The app surfaces all of them as editable, which is the honest thing to do, but if I were consulting on a real deployment the first workshop would be "what is your stockout actually worth."

- **No demand drift.** The empirical bootstrap assumes stationarity. A production version would need to handle seasonality changes, promotions, and stockouts in the *training* data (which suppress observed demand).

## Try it, or read the code

- **Live demo:** <https://inventory.christopherrobertwhite.com>
- **GitHub repo:** <https://github.com/chrisrwhite/stochastic-inventory-explorer>
- **Math and methodology:** [FORMULATION.md](https://github.com/chrisrwhite/stochastic-inventory-explorer/blob/main/FORMULATION.md) has the full model, mermaid diagrams of the pipeline and simulation loop, and an honest comparison to solver-based alternatives.
- **Notebook walkthrough:** the same pipeline exposed as a Jupyter notebook, with every parameter at the top and matplotlib plots inline. Good for a lunchtime read.
- **Data provenance:** [DATA_LICENSES.md](https://github.com/chrisrwhite/stochastic-inventory-explorer/blob/main/DATA_LICENSES.md).

If you build something on top of this, or find a scenario where the recommendation feels wrong, tell me. That's the most useful feedback a portfolio project can attract.
