# Stochastic Inventory Reorder / Safety Stock Explorer

[![CI](https://github.com/chrisrwhite/stochastic-inventory-explorer/actions/workflows/ci.yml/badge.svg)](https://github.com/chrisrwhite/stochastic-inventory-explorer/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3120/)

<!--
Once you have a live URL, paste a demo GIF here:
![Demo](docs/hero.gif)
See docs/hero-placeholder.md for what to capture.
-->

An interactive stochastic-optimization demo. Pick one of three real POS
scenarios, dial in lead-time uncertainty and a reliability target, and the app
returns the cheapest reorder policy that hits your target, alongside the full
cost-vs-reliability frontier, a fan chart of simulated inventory paths, and a
plain-English "why this policy" breakdown.

Under the hood: **Monte Carlo simulation of ~240 candidate (r, Q) or (s, S)
policies over empirical or parametric demand, with risk-aware constraints
(service level, stockout probability, or CVaR budget)**. It's a textbook
Sample Average Approximation for inventory policy selection.

**Want the math?** See [FORMULATION.md](FORMULATION.md) for the full model
formulation, mermaid diagrams of the optimization pipeline and simulation
inner loop, and an honest comparison to solver-based alternatives (LP, MIP,
stochastic programming), none of which we use here. The file explains why.

This is an educational stochastic-optimization app. It is not an ERP, not a
pantry tracker, not a procurement system, and not a purchase-order execution
tool. See [About](./docs/tech-spec.md#12-what-this-is-not) for details.

## What you can learn from this demo

- **How stochastic optimization frames real decisions.** Instead of a single
  forecast, the problem is defined over thousands of possible futures and the
  optimizer picks the policy with the best expected outcome across all of them.
- **What "service level" actually costs.** The cost-vs-reliability chart makes
  the tradeoff visible: pushing from 95% to 99% almost always costs
  disproportionately more inventory.
- **Why safety stock exists.** The lead-time distribution preview and the
  inventory fan chart together show how variability in shipping, not average
  demand, drives most of the stockout risk.
- **How to build trust in a model's output.** Every input has an inline
  visualization, and every result has an alternative-policies table so you can
  see what the recommendation is being compared against.
- **Real POS data, transparent provenance.** Every bundled scenario is derived
  from an open real-world dataset (Walmart via Kaggle M5 and UCI Online Retail
  II); the fetch pipeline in
  `scripts/fetch_open_datasets.py` is deterministic and each derived
  `demand.csv` is checked into the repo.

## Live demo

**<https://inventory.christopherrobertwhite.com>**

Scale-to-zero on Cloud Run, so the first request after an idle period pays a
few seconds of cold start. An optimization run takes roughly 30 seconds — it is
simulating 1,000 futures against each of ~240 candidate policies, and that work
is genuinely being done, not faked.

See also [How it works](docs/tech-spec.md) and the
[notebook walkthrough](notebooks/inventory_workflow_walkthrough.ipynb), or run
locally with `make setup && make backend && make frontend`.

## Stack

| Layer | Choice |
| --- | --- |
| Python runtime | Python 3.12 slim |
| Backend | FastAPI + Uvicorn |
| Optimization | NumPy / SciPy grid search + Monte Carlo |
| Frontend | React + Vite + TypeScript |
| Styling | Tailwind + shadcn/ui |
| Charts | Recharts |
| Deploy | Docker multi-stage to Google Cloud Run |
| Infrastructure | Terraform (`infra/`), GitHub Actions + Workload Identity Federation |
| DNS/TLS | Cloudflare (proxied) |

## Repository layout

```
stochastic-inventory-explorer/
├── backend/                 FastAPI app + numpy optimization core
├── frontend/                React + Vite SPA
├── docker/Dockerfile        multi-stage build
├── infra/                   Terraform: Cloud Run service, WIF, Artifact Registry
├── scripts/                 real-dataset fetch pipeline, dev helpers
├── .github/workflows/       CI + Cloud Run deploy
├── docs/tech-spec.md        design document with the full OR context
├── FORMULATION.md           model formulation + mermaid diagrams + why no solver
├── DATA_LICENSES.md         data provenance and reuse terms
└── LICENSE                  MIT
```

## Prerequisites

- Python **3.12**
- [Poetry](https://python-poetry.org/) **2.x**
- Node **20**
- Docker (optional, only for the production image build)

## Local development

```bash
# one-time setup, installs Poetry venv in backend/.venv and npm deps
make setup

# run backend and frontend in two terminals
make backend        # http://localhost:8000 (FastAPI, hot reload)
make frontend       # http://localhost:5173 (Vite dev server, /api proxied)

# run tests
make test

# build the production docker image
make docker-build

# run the production image locally
make docker-run
```

Poetry-specific tips:

- All backend Python dependencies (runtime, dev, notebook) live in
  [backend/pyproject.toml](backend/pyproject.toml). The lock file is
  [backend/poetry.lock](backend/poetry.lock).
- Run any backend command inside its virtualenv with
  `cd backend && poetry run <command>` (e.g. `poetry run pytest`,
  `poetry run ruff check .`, `poetry run uvicorn app.main:app --reload`).
- Add a dependency with `cd backend && poetry add <package>`; add a dev-only
  dependency with `poetry add --group dev <package>`.

## Notebook walkthrough

Prefer to explore the pipeline in Python? Open
[`notebooks/inventory_workflow_walkthrough.ipynb`](notebooks/inventory_workflow_walkthrough.ipynb).
It runs the same `run_optimization` entry point the FastAPI route uses, with
all parameters (scenario, policy family, reliability target, costs, Monte Carlo
settings) at the top of the notebook and matplotlib visuals for demand,
lead-time distribution, cost impact, the frontier, the inventory fan chart, and
an alternatives comparison. No server needed.

## Sample data

Every bundled scenario is derived from a real open dataset. No synthetic
demand curves. Each scenario aggregates one real SKU (and for M5, one real
store) to daily unit demand and ships as `demand.csv`, `costs.yaml`, and
`lead_time.yaml` in `backend/data/scenarios/<scenario_id>/`, indexed from
`MANIFEST.json`.

See [DATA_LICENSES.md](DATA_LICENSES.md) for full provenance, transformation
notes, and upstream reuse terms per source.

| Scenario id | Source | Character |
| --- | --- | --- |
| `walmart_pantry_m5` | [Kaggle M5](https://www.kaggle.com/competitions/m5-forecasting-accuracy) (`FOODS_1_218` × `CA_3`) | Steady mid-volume Walmart pantry item, ~12/day, ~5% zero-days. **Default demo scenario.** |
| `walmart_hobbies_sparse_m5` | Kaggle M5 (`HOBBIES_2_017` × `CA_3`) | Very sparse: ~85% zero-days, ~0.2/day mean. Real intermittent-demand test where reliability and fill rate diverge sharply. |
| `retail_online_uk` | [UCI Online Retail II](https://doi.org/10.24432/C5CG6D) (StockCode `85123A`) | Heavy-tailed UK gift-shop item: median ~88/day but the occasional 4,000-unit spike. Reliability plateaus around 93 to 94% (95% isn't reachable) while fill rate stays near 100%; the app now says so explicitly. |

Two provenances (Kaggle M5, UCI Online Retail II) with three scenarios total,
each teaching a distinct demand shape (steady, sparse/intermittent, and
heavy-tailed). The fetch pipeline also ships pre-wired hooks for
[Corporación Favorita](https://www.kaggle.com/competitions/favorita-grocery-sales-forecasting)
and [Iowa Liquor Sales](https://data.iowa.gov/Sales-Distribution/Iowa-Liquor-Sales/m3tr-qhgy)
so a future contributor can add scenarios from either source by dropping a
pick into `scripts/fetch_open_datasets.py` and rerunning the fetch.

**What is and isn't real.** The `demand.csv` for every scenario is real
per-day POS demand aggregated from the underlying dataset. The bundled
`costs.yaml` (unit cost, holding cost, stockout penalty, fixed order cost) and
`lead_time.yaml` are *illustrative starting values* derived from median
observed prices plus reasonable domain assumptions. They are not audited cost
data from the retailer. The app UI surfaces both as editable, so you can plug
in your own numbers.

### Fetching / refreshing the data

Cached raw downloads live in `backend/data/scenarios/_raw/` (gitignored); the
derived `demand.csv`, `costs.yaml`, `lead_time.yaml`, and the `MANIFEST.json`
index are all checked in so the app runs offline once fetched.

```bash
# UCI only (no Kaggle account needed; populates the UK e-commerce scenario)
make fetch-open-data

# UCI + M5 (populates all 3 bundled scenarios; needs a Kaggle credential and
# accepted competition rules for M5)
make fetch-open-data-all

# One scenario at a time (useful while tuning a new pick):
cd backend && poetry run python ../scripts/fetch_open_datasets.py --only walmart_pantry_m5
```

Adding a new SKU is a one-line change: append to the `UCI_PICKS` / `M5_PICKS`
/ `FAVORITA_PICKS` / `IOWA_PICKS` tuple at the top of
`scripts/fetch_open_datasets.py`, then rerun `make fetch-open-data-all`. The
Favorita and Iowa hooks are already wired but ship with empty pick lists.

#### Pulling the M5 scenarios

The Kaggle CLI is installed inside the Poetry-managed venv (`backend/.venv`),
so you do **not** need `kaggle` on your shell `PATH` to run `make fetch-open-data-all`.
The script invokes it via `poetry run` for you. (If you want a global `kaggle`
command anyway, `pipx install kaggle` is the tidiest option.)

You need to accept the competition rules **once per competition** from the
Kaggle web UI:
- <https://www.kaggle.com/competitions/m5-forecasting-accuracy/rules>

(If you also enable a Favorita pick, accept
<https://www.kaggle.com/competitions/favorita-grocery-sales-forecasting/rules>
before rerunning the fetch.)

Any one of these auth methods works with the pinned `kaggle >= 1.8.3`:

1. **`KAGGLE_API_TOKEN=KGAT_...`** env var, a new-style access token
   generated at <https://www.kaggle.com/settings/account>.
2. **`~/.kaggle/access_token`**, the same `KGAT_...` token written to a file.
   Use `printf '%s' "$KAGGLE_API_TOKEN" > ~/.kaggle/access_token` so no
   trailing newline is included, then `chmod 600 ~/.kaggle/access_token`.
3. **Legacy `~/.kaggle/kaggle.json`** with `{"username":"...","key":"..."}`
   downloaded from the same settings page.

If your machine is behind a corporate MITM proxy (Zscaler, Netskope, etc.) and
the fetch fails with `SSLError: self-signed certificate in certificate chain`,
the script will auto-detect and use your system CA bundle when one of the
common locations exists (`/opt/homebrew/etc/openssl@3/cert.pem`,
`/etc/ssl/cert.pem`, `/etc/ssl/certs/ca-certificates.crt`, ...). To override,
export `SSL_CERT_FILE` / `REQUESTS_CA_BUNDLE` pointing at a bundle that
includes your corporate root.

## Deploy to Cloud Run + Cloudflare

See [docs/deploy.md](docs/deploy.md) for the full walkthrough and
[infra/README.md](infra/README.md) for the Terraform. Summary:

1. `cd infra && cp terraform.tfvars.example terraform.tfvars` (set
   `project_id` and `github_repo`), then `terraform apply`. This provisions the
   APIs, Artifact Registry, Workload Identity Federation, the service accounts,
   and the Cloud Run service.
2. Publish the three repo secrets from `terraform output`:
   `GCP_PROJECT_ID`, `GCP_WORKLOAD_IDENTITY_PROVIDER`,
   `GCP_DEPLOY_SERVICE_ACCOUNT`.
3. Push to `main`; the deploy workflow builds the image, rolls out a revision,
   and smoke-tests `/api/health`.
4. Map your Cloudflare subdomain: add a `CNAME inventory ghs.googlehosted.com`
   record (proxied), set SSL/TLS to `Full (strict)`, and run
   `gcloud beta run domain-mappings create --service stochastic-inventory-reorder --domain inventory.example.com` (replacing `inventory.example.com` with your zone).

Terraform owns **service configuration**; the workflow owns **the image** and
passes `--image` only. Change CPU, memory, concurrency, scaling, timeout or the
`MAX_*` compute caps in `infra/variables.tf` — never as flags in the workflow,
which would override Terraform invisibly on every push.

## Operations & dev access

The live site **auto-deploys on every push to `main`**: GitHub Actions → build
→ Artifact Registry → Cloud Run. There is no manual deploy step for code
changes; infra changes go through Terraform (`infra/`).

Project facts: region `us-east1`, Cloud Run service `stochastic-inventory-reorder`,
domain `inventory.christopherrobertwhite.com`.

> **The GCP project ID is deliberately not written down here.** This repo is on
> a documented path to becoming public (see
> [.github/PUBLISH_CHECKLIST.md](.github/PUBLISH_CHECKLIST.md)), and project /
> account identifiers are the kind of thing that is awkward to retract once
> published. Get the ID from `cd infra && terraform output -raw gcp_project_id`,
> or from `infra/terraform.tfvars` — both gitignored. Console links below are
> ID-free; pick the project once and Google remembers it.

| What | Where | Use it to… |
|---|---|---|
| Source & deploy | [GitHub Actions](https://github.com/chrisrwhite/stochastic-inventory-explorer/actions) | push to `main` to ship; watch or debug a deploy |
| Service metrics | [Cloud Run](https://console.cloud.google.com/run) | request count, latency, **instance count** (stateless scale-out signal), error rate, 429s |
| Logs | [Cloud Logging](https://console.cloud.google.com/logs) | tracebacks; `gcloud run services logs read stochastic-inventory-reorder --region us-east1` |
| Custom domain | [Cloud Run → domains](https://console.cloud.google.com/run/domains) | domain mapping & TLS cert status |
| DNS | [Cloudflare dashboard](https://dash.cloudflare.com) | the `inventory` CNAME → `ghs.googlehosted.com` (**DNS-only / grey cloud**, or Google cannot issue the cert) |
| Images | [Artifact Registry](https://console.cloud.google.com/artifacts) | see pushed image tags; each is a commit SHA |

**Common tasks**

- **Ship a code change** — push to `main`; `gh run watch` to follow it. The
  workflow smoke-tests `/api/health` before going green.
- **Change CPU / memory / max-instances / compute caps** — edit
  `infra/variables.tf`, then `cd infra && terraform apply` (see
  [infra/README.md](infra/README.md)). Do *not* click these in the console or
  add flags to the workflow; Terraform owns them.
- **Roll back** — route traffic to a previous revision (instant):
  ```bash
  gcloud run revisions list --service stochastic-inventory-reorder --region us-east1
  gcloud run services update-traffic stochastic-inventory-reorder \
    --region us-east1 --to-revisions REVISION_NAME=100
  ```
  Or revert the commit and let the pipeline redeploy.
- **A deploy failed** — `gh run view --log-failed`. A `poetry.lock` /
  `pyproject.toml` mismatch fails the CI lock check with a clear message; fix
  with `poetry lock` run under the **pinned** Poetry version (2.4.1), not
  whatever is on your PATH.
- **Users report "the simulator is busy"** — that is the app-level 429 guard,
  not an outage. Check instance count in Cloud Run: if it is pinned at
  `max_instances` the service is genuinely saturated and `max_instances` or
  `cpu` + `max_concurrent_simulations` should go up together. See
  [docs/deploy.md](docs/deploy.md#sizing-and-why-it-is-what-it-is).
- **Keep it warm** (optional) — a free UptimeRobot monitor hitting
  `GET /api/health` every 10 min hides cold starts from visitors.

### Session state

The backend keeps no per-visitor state: each request carries its full
configuration and gets its whole result back inline, so any instance can serve
any request and the service scales out freely. The client side of that is that
**the URL is the session** — the whole config round-trips through the query
string (`frontend/src/state/urlState.ts`), so reloads and shared links
reproduce the exact run. A new config field must be added there too, or it
silently resets on reload.

## Contributing

This is a personal portfolio project. Issues are welcome; PRs are considered
case-by-case.

## License

Source code is [MIT](LICENSE). Bundled datasets have separate upstream terms;
see [DATA_LICENSES.md](DATA_LICENSES.md).
