# Notebooks

## `inventory_workflow_walkthrough.ipynb`

Runs the same optimization pipeline the web app uses, but as a plain Python
script with visuals inline. Every parameter (scenario, policy family, mode,
target service level, cost overrides, Monte Carlo settings) is exposed at the
top so you can tweak and re-run all cells.

### Requirements

Uses the backend Python package directly, no FastAPI server needed.

```bash
# install the backend deps plus the notebook group (matplotlib, jupyter, ipykernel, nbformat)
cd backend && poetry install --with notebook --no-root

# launch Jupyter Lab pointed at the notebook
poetry run jupyter lab ../notebooks/inventory_workflow_walkthrough.ipynb
```

Or, from the repo root, `make notebook` runs both steps for you.

If for some reason you can't use Poetry, the notebook's first code cell will
also `pip install` any missing preview dependencies at runtime.

### What each section does

1. **Environment setup**: adds `backend/` to `sys.path` and installs missing
   visualization deps.
2. **Parameters**: the only cell you normally edit.
3. **Scenario, demand preview**: recent history bars, mean by weekday, stats
   strip, plus a table of all bundled scenarios.
4. **Lead-time distribution preview**: 5k draws from the configured sampler,
   histogram with mean and p95 marks.
5. **Cost inputs preview**: effective cost table plus dollar impact chart.
6. **Run the optimizer**: calls `app.api.services.run_optimization` and times
   the wall clock.
7. **Recommended policy and explanation**: recommended `(r, S)` or `(r, Q)`,
   headline metrics, and the natural-language narrative.
8. **Frontier chart**: every candidate policy scattered by cost and service
   level, with the efficient frontier line, reference-policy triangles, and a
   labeled callout on the recommendation.
9. **Fan chart**: inventory-on-hand percentile bands, with `r` and `S`
   reference lines plus order-placed and order-received markers on the median
   path.
10. **Alternatives comparison**: side-by-side table with green/red deltas
    versus the recommendation.
