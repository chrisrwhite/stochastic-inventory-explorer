# Data licenses and attribution

This project ships with three pre-derived demand scenarios under
`backend/data/scenarios/`. Every scenario is an aggregation of one real SKU
(and, for M5, one real store) from a publicly-available open dataset. No
synthetic demand curves.

This document names each source, explains what transformation was applied,
and links to the upstream license or competition rules. **This repository is
provided for educational and portfolio-demonstration use.** If you want to
build on any of the derived scenarios below, please review the linked
upstream terms first.

## Scenarios and provenance

| Scenario id | Upstream dataset | Upstream terms | Character |
| --- | --- | --- | --- |
| `walmart_pantry_m5` | [Kaggle M5 Forecasting - Accuracy](https://www.kaggle.com/competitions/m5-forecasting-accuracy) (`FOODS_1_218` × `CA_3`) | [Competition rules](https://www.kaggle.com/competitions/m5-forecasting-accuracy/rules) | Steady mid-volume Walmart pantry item |
| `walmart_hobbies_sparse_m5` | Kaggle M5 Forecasting - Accuracy (`HOBBIES_2_017` × `CA_3`) | Competition rules | Very sparse intermittent demand |
| `retail_online_uk` | [UCI Online Retail II](https://doi.org/10.24432/C5CG6D) (StockCode `85123A`) | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | Heavy-tailed UK gift-shop item |

## What transformation was applied

For every scenario, the reproducible fetch pipeline at
[`scripts/fetch_open_datasets.py`](scripts/fetch_open_datasets.py):

1. Downloads the raw upstream dataset into a **gitignored** cache
   (`backend/data/scenarios/_raw/`).
2. Filters to a single SKU (and single store for M5 / Favorita).
3. Aggregates transaction-level or SKU-day rows to a single time series of
   daily unit demand.
4. Writes three small files per scenario into the repo:
   - `demand.csv` (~200 KB, columns `date` and `demand_units`)
   - `costs.yaml` (illustrative starting costs derived from median observed
     price; user-editable in the UI)
   - `lead_time.yaml` (illustrative lead-time distribution)

The derived per-SKU-day CSVs bundled here are **substantially transformed**
summaries of the upstream data (a single time series per scenario, no
transaction-level records, no other SKUs, no store metadata) and are shipped
to make the demo runnable offline. They are not intended as, and are not, a
redistribution of the underlying competition data.

## What is real vs illustrative

- **`demand.csv`** contains real per-day POS demand aggregated from the
  underlying dataset. It is not synthetic.
- **`costs.yaml`** values (unit cost, holding cost per day, stockout penalty,
  fixed order cost, variable order cost, starting inventory) are
  *illustrative starting values* derived from median observed prices and
  reasonable domain assumptions. They are not audited cost data from any
  retailer and can be edited freely in the UI.
- **`lead_time.yaml`** parameters are illustrative and can be edited in the
  UI. Real lead-time data is rarely public.

## If you want to reuse this data downstream

- **UCI Online Retail II** is released under **CC BY 4.0**, so you can reuse
  the derived UK scenario freely with attribution to the original UCI
  Machine Learning Repository entry above.
- **Kaggle M5 and Favorita** are governed by the linked competition rules,
  which restrict redistribution of the raw competition data. The derived
  aggregated scenarios in this repo are intended for local, educational
  demonstration. If you plan to build a downstream product or dataset on
  top of them, download the original data directly from Kaggle and review
  the rules. Please don't treat this repo as your data source of record.

## Rebuilding the scenarios from scratch

The full pipeline is deterministic and reproducible. See the [README](README.md)
section "Fetching / refreshing the data" for commands. The UCI scenarios
require no credentials; the Kaggle scenarios require a Kaggle API token and a
one-time acceptance of each competition's rules.

## Contact

If you are a data owner and have concerns about how a derived scenario is
presented here, please open an issue on the repository or contact the
maintainer, and I will remove or rework it.
