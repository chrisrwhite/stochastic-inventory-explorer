"""Fetch open-source retail-demand datasets and derive single-SKU scenarios.

Produces the same ``demand.csv`` / ``costs.yaml`` / ``lead_time.yaml`` layout as
the app expects and upserts entries into ``MANIFEST.json``.

Data sources
------------

``uci``       UCI Online Retail II (CC BY 4.0, https://doi.org/10.24432/C5CG6D).
              Aggregates transactions for a single StockCode into daily units.
              Public download; no auth required.

``m5``        M5 Forecasting Accuracy competition on Kaggle. Filters
              ``sales_train_evaluation.csv`` to specific ``item_id`` x
              ``store_id`` picks and joins ``calendar.csv``. Requires a Kaggle
              account, the competition rules accepted, and any one of:
              ``KAGGLE_API_TOKEN=KGAT_...`` env var, ``~/.kaggle/access_token``,
              or legacy ``~/.kaggle/kaggle.json``.

``favorita``  Corporación Favorita Grocery Sales Forecasting competition on
              Kaggle. Chunked-scans ``train.csv`` (~5 GB uncompressed) for
              specific ``item_nbr`` x ``store_nbr`` picks. Same Kaggle auth
              as M5; distributed as ``.7z`` archives which we extract with
              ``py7zr``.

``iowa``      Iowa Liquor Sales (state-published, CC0, no auth).
              Pulls a specific item_no from the Socrata Open Data API and
              aggregates state-total daily bottle demand.

Each source ships with a list of *picks* (see ``UCI_PICKS`` / ``M5_PICKS`` /
``IOWA_PICKS`` below) that fully describe the SKUs to derive, cost tuning, and
lead-time assumptions. Add a new scenario by appending to a picks list.

Usage
-----

    # everything (all real scenarios across all sources)
    poetry run python scripts/fetch_open_datasets.py --dataset all

    # one source at a time
    poetry run python scripts/fetch_open_datasets.py --dataset uci
    poetry run python scripts/fetch_open_datasets.py --dataset m5
    poetry run python scripts/fetch_open_datasets.py --dataset favorita
    poetry run python scripts/fetch_open_datasets.py --dataset iowa

    # a single scenario (useful while iterating on tuning)
    poetry run python scripts/fetch_open_datasets.py --only walmart_pantry_m5

Raw downloads are cached under ``backend/data/scenarios/_raw/`` (gitignored) so
reruns are idempotent. Note that if you enable a Favorita pick the raw dataset
is ~460 MB zipped and ~5 GB when uncompressed to ``train.csv`` - plan disk
space accordingly.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SCENARIOS_ROOT = REPO_ROOT / "backend" / "data" / "scenarios"
CACHE_ROOT = SCENARIOS_ROOT / "_raw"
MANIFEST_PATH = SCENARIOS_ROOT / "MANIFEST.json"

# Common system CA bundle locations. Networks with a corporate MITM proxy
# (Zscaler, Netskope, etc.) inject a self-signed root that is typically only
# present in the system trust store - Python's bundled ``certifi`` doesn't know
# about it and ``requests``-based clients like the Kaggle CLI fail with
# "self-signed certificate in certificate chain". Point them at the system
# bundle instead when one is available.
_SYSTEM_CA_CANDIDATES = (
    "/opt/homebrew/etc/openssl@3/cert.pem",   # macOS Homebrew (arm64)
    "/usr/local/etc/openssl@3/cert.pem",       # macOS Homebrew (Intel)
    "/etc/ssl/cert.pem",                        # macOS system / Alpine
    "/etc/ssl/certs/ca-certificates.crt",       # Debian / Ubuntu
    "/etc/pki/tls/certs/ca-bundle.crt",         # RHEL / CentOS / Fedora
)


def _configure_ssl_env() -> None:
    """If no CA bundle is configured, fall back to the system one when present.

    Idempotent: existing ``SSL_CERT_FILE`` / ``REQUESTS_CA_BUNDLE`` are honored.
    Sets both variables so ``ssl`` (used by ``urllib``) and ``requests``
    (used by the Kaggle CLI subprocess) pick it up.
    """

    if os.environ.get("SSL_CERT_FILE") and os.environ.get("REQUESTS_CA_BUNDLE"):
        return
    for candidate in _SYSTEM_CA_CANDIDATES:
        if Path(candidate).is_file():
            os.environ.setdefault("SSL_CERT_FILE", candidate)
            os.environ.setdefault("REQUESTS_CA_BUNDLE", candidate)
            return


_configure_ssl_env()


# ---------------------------------------------------------------------------
# Pick definitions
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UciPick:
    """One SKU x time-window pick from UCI Online Retail II."""

    stockcode: str
    scenario_id: str
    title: str
    description: str
    domain: str
    # unit_cost is derived as ``median_observed_price * unit_cost_ratio``.
    unit_cost_ratio: float
    # annual holding rate used to derive holding_cost_per_unit_per_day.
    holding_annual_rate: float
    fixed_order_cost: float
    variable_order_cost_per_unit: float
    starting_inventory_days: float
    lead_time: dict[str, Any]


@dataclass(frozen=True)
class M5Pick:
    """One SKU x store pick from the M5 Forecasting Accuracy competition."""

    item_id: str
    store_id: str
    scenario_id: str
    title: str
    description: str
    domain: str
    unit_cost_ratio: float
    holding_annual_rate: float
    fixed_order_cost: float
    variable_order_cost_per_unit: float
    starting_inventory_days: float
    lead_time: dict[str, Any]


@dataclass(frozen=True)
class FavoritaPick:
    """One item_nbr x store_nbr pick from the Favorita Kaggle competition.

    Favorita's ``train.csv`` does not carry a sell-price column, so we take
    ``retail_price_usd`` explicitly per-pick and use it the same way
    ``median_price`` is derived-from-data in the M5 / UCI branches.
    ``unit_sales`` is a float (deli/produce are sold by weight) - we round to
    integer units when writing the demand CSV.
    """

    item_nbr: int
    store_nbr: int
    scenario_id: str
    title: str
    description: str
    domain: str
    retail_price_usd: float
    unit_cost_ratio: float
    holding_annual_rate: float
    fixed_order_cost: float
    variable_order_cost_per_unit: float
    starting_inventory_days: float
    lead_time: dict[str, Any]


@dataclass(frozen=True)
class IowaPick:
    """One item_no pick from Iowa Liquor Sales (SODA API)."""

    item_no: str
    scenario_id: str
    title: str
    description: str
    domain: str
    unit_cost_ratio: float
    holding_annual_rate: float
    fixed_order_cost: float
    variable_order_cost_per_unit: float
    starting_inventory_days: float
    lead_time: dict[str, Any]
    # date range to pull (inclusive). Iowa dataset goes back to 2012.
    start_date: str = "2020-01-01"
    end_date: str = "2023-12-31"
    # SODA API pagination.
    soda_limit: int = 50000
    soda_app_token: str | None = field(
        default_factory=lambda: os.environ.get("SODA_APP_TOKEN")
    )


# --- UCI Online Retail II picks (real UK e-commerce data) ------------------

# Standard UK e-commerce assumptions: ~25% annual holding rate on wholesale
# cost, 7-day lognormal lead time from a supplier, £25 order overhead.
UCI_PICKS: tuple[UciPick, ...] = (
    UciPick(
        stockcode="85123A",
        scenario_id="retail_online_uk",
        title="UK online retail - heart decorations",
        description=(
            "Daily unit demand for StockCode 85123A (WHITE HANGING HEART "
            "T-LIGHT HOLDER) from the UCI Online Retail II dataset. Real UK "
            "e-commerce demand, 2009-2011. Heavy-tailed: median ~88/day but "
            "occasional 4,000-unit gift-shop spikes - a good example of why "
            "cycle service level can be misleading on real retail data (try "
            "fill-rate)."
        ),
        domain="ecommerce",
        unit_cost_ratio=0.5,
        holding_annual_rate=0.25,
        fixed_order_cost=25.0,
        variable_order_cost_per_unit=0.0,
        starting_inventory_days=14.0,
        lead_time={
            "distribution": "lognormal",
            "mean_days": 7.0,
            "std_days": 2.0,
            "min_days": 3,
            "max_days": 21,
        },
    ),
)


# --- Kaggle M5 picks (real Walmart POS data) -------------------------------

# Standard grocery/big-box assumptions: ~25% annual holding rate, small $0.05
# per-unit variable order cost (case-picking), $40 fixed order cost.
M5_PICKS: tuple[M5Pick, ...] = (
    M5Pick(
        item_id="FOODS_1_218",
        store_id="CA_3",
        scenario_id="walmart_pantry_m5",
        title="Walmart pantry item (M5)",
        description=(
            "Daily unit sales for item_id=FOODS_1_218 at store_id=CA_3 from "
            "Kaggle M5. Steady mid-volume pantry item - ~12/day, ~5% "
            "zero-days. Good default demo scenario: enough volume for "
            "clean statistics but small enough that reorder policy really "
            "matters."
        ),
        domain="retail_chain",
        unit_cost_ratio=0.55,
        holding_annual_rate=0.25,
        fixed_order_cost=30.0,
        variable_order_cost_per_unit=0.04,
        starting_inventory_days=7.0,
        lead_time={
            "distribution": "triangular",
            "min_days": 1,
            "mode_days": 2,
            "max_days": 4,
            "mean_days": 2.3,
            "std_days": 0.7,
        },
    ),
    M5Pick(
        item_id="HOBBIES_2_017",
        store_id="CA_3",
        scenario_id="walmart_hobbies_sparse_m5",
        title="Walmart hobbies - sparse slow-mover (M5)",
        description=(
            "Daily unit sales for item_id=HOBBIES_2_017 at store_id=CA_3 "
            "from Kaggle M5. Very sparse: ~85% zero-days, mean ~0.2/day. "
            "Real intermittent-demand test case where cycle service level "
            "and fill rate diverge sharply."
        ),
        domain="retail_chain",
        unit_cost_ratio=0.55,
        holding_annual_rate=0.25,
        fixed_order_cost=40.0,
        variable_order_cost_per_unit=0.05,
        starting_inventory_days=45.0,
        lead_time={
            "distribution": "triangular",
            "min_days": 3,
            "mode_days": 7,
            "max_days": 14,
            "mean_days": 7.7,
            "std_days": 2.2,
        },
    ),
)


# --- Corporación Favorita picks (real Ecuadorian grocery POS data) ---------

# No Favorita picks are currently bundled. The fetch pipeline and Kaggle
# credentials stay wired up so a future contributor can drop a
# ``FavoritaPick`` into this tuple and rerun ``make fetch-open-data`` to
# regenerate a scenario without touching the fetcher itself.
FAVORITA_PICKS: tuple[FavoritaPick, ...] = ()


# --- Iowa Liquor Sales picks (disabled: platform migration in progress) ----

# As of mid-2026 the Iowa Data Hub is transitioning off the Socrata SODA API
# to a new Next.js-based portal + Google BigQuery public dataset
# (``bigquery-public-data.iowa_liquor_sales.sales``). The legacy
# ``/resource/{id}.csv`` and new ``/api/v3/views/{id}/query.json`` endpoints
# both currently return 404. Fetching from BigQuery would require the
# ``google-cloud-bigquery`` package plus GCP credentials, which is a heavier
# lift than fits alongside the ``kaggle`` / ``urllib`` pipeline here.
#
# The dataclass and fetcher below are left in place so a future contributor
# can drop in a new endpoint (or a BigQuery-based ``_iowa_soda_query``) and
# append picks to this tuple without further refactoring.
IOWA_PICKS: tuple[IowaPick, ...] = ()


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScenarioMeta:
    scenario_id: str
    title: str
    description: str
    domain: str
    sku_id: str
    source: str
    downloaded_at: str
    start_date: str


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _write_yaml(payload: dict[str, Any], path: Path) -> None:
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )


def _write_demand_csv(
    dates: pd.Series,
    demand: np.ndarray,
    sku_id: str,
    path: Path,
) -> None:
    lines = ["date,sku_id,demand_units,weekday"]
    for d, units in zip(dates, demand, strict=True):
        day = pd.Timestamp(d).date().isoformat()
        weekday = pd.Timestamp(d).strftime("%a")
        lines.append(f"{day},{sku_id},{int(units)},{weekday}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _load_manifest() -> list[dict[str, Any]]:
    if MANIFEST_PATH.exists():
        current = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        return list(current.get("scenarios", []))
    return []


def _save_manifest(scenarios: list[dict[str, Any]]) -> None:
    scenarios = sorted(scenarios, key=lambda s: (s.get("source", ""), s["scenario_id"]))
    MANIFEST_PATH.write_text(
        json.dumps({"scenarios": scenarios}, indent=2) + "\n",
        encoding="utf-8",
    )


def _upsert_manifest(entry: dict[str, Any]) -> None:
    scenarios = _load_manifest()
    scenarios = [s for s in scenarios if s.get("scenario_id") != entry["scenario_id"]]
    scenarios.append(entry)
    _save_manifest(scenarios)


def _derive_costs(
    median_price: float,
    demand_mean: float,
    unit_cost_ratio: float,
    holding_annual_rate: float,
    fixed_order_cost: float,
    variable_order_cost_per_unit: float,
    starting_inventory_days: float,
) -> dict[str, float | int]:
    unit_cost = round(median_price * unit_cost_ratio, 2)
    return {
        "unit_cost": unit_cost,
        "holding_cost_per_unit_per_day": round(unit_cost * holding_annual_rate / 365, 4),
        "stockout_cost_per_unit": round(median_price, 2),
        "fixed_order_cost": fixed_order_cost,
        "variable_order_cost_per_unit": variable_order_cost_per_unit,
        "starting_inventory": float(round(max(demand_mean, 0.1) * starting_inventory_days)),
        "review_period_days": 1,
    }


def _finalize_scenario(
    meta: ScenarioMeta,
    dates: pd.Series,
    demand: np.ndarray,
    costs: dict[str, float | int],
    lead_time: dict[str, Any],
) -> None:
    target = SCENARIOS_ROOT / meta.scenario_id
    target.mkdir(parents=True, exist_ok=True)

    demand_path = target / "demand.csv"
    costs_path = target / "costs.yaml"
    lead_path = target / "lead_time.yaml"

    _write_demand_csv(dates, demand, meta.sku_id, demand_path)
    _write_yaml(dict(costs), costs_path)
    _write_yaml(dict(lead_time), lead_path)

    entry = {
        "scenario_id": meta.scenario_id,
        "title": meta.title,
        "description": meta.description,
        "domain": meta.domain,
        "sku_id": meta.sku_id,
        "source": meta.source,
        "downloaded_at": meta.downloaded_at,
        "history_days": int(len(demand)),
        "start_date": meta.start_date,
        "files": {
            "demand": {"path": f"{meta.scenario_id}/demand.csv", "sha256": _sha256(demand_path)},
            "costs": {"path": f"{meta.scenario_id}/costs.yaml", "sha256": _sha256(costs_path)},
            "lead_time": {
                "path": f"{meta.scenario_id}/lead_time.yaml",
                "sha256": _sha256(lead_path),
            },
        },
    }
    _upsert_manifest(entry)
    zero_days_pct = float((demand == 0).mean()) * 100
    print(
        f"[{meta.scenario_id}] wrote {len(demand)} days ({meta.start_date} -> "
        f"{pd.Timestamp(dates.iloc[-1]).date().isoformat()}); "
        f"mean={demand.mean():.2f}, max={int(demand.max())}, zero-days={zero_days_pct:.0f}%"
    )


# ---------------------------------------------------------------------------
# UCI Online Retail II
# ---------------------------------------------------------------------------


UCI_URL = (
    "https://archive.ics.uci.edu/ml/machine-learning-databases/00502/online_retail_II.xlsx"
)


def _download_uci() -> Path:
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    target = CACHE_ROOT / "online_retail_II.xlsx"
    if target.exists() and target.stat().st_size > 10_000_000:
        return target
    print(f"downloading {UCI_URL} -> {target} (~44MB) ...")
    with urllib.request.urlopen(UCI_URL) as resp, target.open("wb") as fh:
        shutil.copyfileobj(resp, fh)
    return target


_UCI_RAW_CACHE: pd.DataFrame | None = None


def _load_uci_raw() -> pd.DataFrame:
    """Read + concatenate both UCI sheets once per process (60s+ operation)."""

    global _UCI_RAW_CACHE
    if _UCI_RAW_CACHE is not None:
        return _UCI_RAW_CACHE
    xlsx = _download_uci()
    print(f"reading {xlsx.name} (both sheets) ...")
    frames = []
    for sheet in ("Year 2009-2010", "Year 2010-2011"):
        df = pd.read_excel(xlsx, sheet_name=sheet)
        df.columns = [c.strip() for c in df.columns]
        df = df.rename(columns={"Customer ID": "CustomerID", "Price": "UnitPrice"})
        frames.append(df)
    raw = pd.concat(frames, ignore_index=True)
    raw["Quantity"] = raw["Quantity"].fillna(0).astype(int)
    raw = raw[raw["Quantity"] > 0].copy()
    raw["date"] = pd.to_datetime(raw["InvoiceDate"]).dt.floor("D")
    raw["StockCode"] = raw["StockCode"].astype(str).str.upper()
    _UCI_RAW_CACHE = raw
    return raw


def _fetch_uci_pick(raw: pd.DataFrame, pick: UciPick) -> None:
    filt = raw[raw["StockCode"] == pick.stockcode.upper()].copy()
    if filt.empty:
        raise RuntimeError(f"UCI: no rows for StockCode={pick.stockcode}")

    daily = (
        filt.groupby("date")["Quantity"]
        .sum()
        .rename("demand_units")
        .reset_index()
        .sort_values("date")
    )
    full_range = pd.date_range(daily["date"].min(), daily["date"].max(), freq="D")
    daily = (
        daily.set_index("date")
        .reindex(full_range, fill_value=0)
        .rename_axis("date")
        .reset_index()
    )
    demand = daily["demand_units"].to_numpy(dtype=np.int64)

    median_price = (
        float(np.median(filt["UnitPrice"].dropna()))
        if "UnitPrice" in filt.columns and not filt["UnitPrice"].dropna().empty
        else 2.5
    )

    meta = ScenarioMeta(
        scenario_id=pick.scenario_id,
        title=pick.title,
        description=pick.description,
        domain=pick.domain,
        sku_id=f"UCI-{pick.stockcode}",
        source="uci_online_retail_ii",
        downloaded_at=date.today().isoformat(),
        start_date=daily["date"].min().date().isoformat(),
    )
    costs = _derive_costs(
        median_price=median_price,
        demand_mean=float(demand.mean()),
        unit_cost_ratio=pick.unit_cost_ratio,
        holding_annual_rate=pick.holding_annual_rate,
        fixed_order_cost=pick.fixed_order_cost,
        variable_order_cost_per_unit=pick.variable_order_cost_per_unit,
        starting_inventory_days=pick.starting_inventory_days,
    )
    _finalize_scenario(meta, daily["date"], demand, costs, pick.lead_time)


def fetch_uci(picks: list[UciPick]) -> None:
    if not picks:
        return
    raw = _load_uci_raw()
    for pick in picks:
        _fetch_uci_pick(raw, pick)


# ---------------------------------------------------------------------------
# M5 Forecasting Accuracy (Kaggle competition)
# ---------------------------------------------------------------------------


M5_COMPETITION = "m5-forecasting-accuracy"


def _kaggle_download_m5() -> Path:
    target_dir = CACHE_ROOT / "m5"
    if (target_dir / "sales_train_evaluation.csv").exists():
        return target_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    print(f"downloading Kaggle competition '{M5_COMPETITION}' (~90MB zipped) ...")
    try:
        subprocess.run(
            [
                "kaggle",
                "competitions",
                "download",
                "-c",
                M5_COMPETITION,
                "-p",
                str(target_dir),
                "-q",
            ],
            check=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "The 'kaggle' CLI was not found. Install with `poetry install --with data` "
            "(it does not need to be on your shell PATH - this script invokes it "
            "via the Poetry-managed venv). Auth options (any one works):\n"
            "  1. KAGGLE_API_TOKEN=KGAT_... env var (new-style access token)\n"
            "  2. ~/.kaggle/access_token file containing a KGAT_... token\n"
            "  3. legacy ~/.kaggle/kaggle.json (username + key)\n"
            "See https://www.kaggle.com/docs/api."
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            "Kaggle CLI failed. Common causes:\n"
            f"  - competition rules not yet accepted at https://www.kaggle.com/competitions/{M5_COMPETITION}/rules\n"
            "  - KAGGLE_API_TOKEN / ~/.kaggle/access_token / ~/.kaggle/kaggle.json missing or invalid\n"
            "  - kaggle package pinned below 1.8.3 (older versions ignore KGAT_* tokens)\n"
            "  - SSL: 'self-signed certificate in certificate chain' means a corporate "
            "MITM proxy is present; export SSL_CERT_FILE / REQUESTS_CA_BUNDLE pointing at "
            "your system CA bundle (e.g. /opt/homebrew/etc/openssl@3/cert.pem on macOS)."
        ) from exc

    zip_path = target_dir / f"{M5_COMPETITION}.zip"
    if zip_path.exists():
        print(f"extracting {zip_path.name} ...")
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(target_dir)
        zip_path.unlink()
    return target_dir


_M5_CACHE: dict[str, pd.DataFrame] | None = None


def _load_m5() -> dict[str, pd.DataFrame]:
    global _M5_CACHE
    if _M5_CACHE is not None:
        return _M5_CACHE
    m5_dir = _kaggle_download_m5()
    print("loading M5 CSVs (sales, calendar, prices) ...")
    _M5_CACHE = {
        "sales": pd.read_csv(m5_dir / "sales_train_evaluation.csv"),
        "calendar": pd.read_csv(m5_dir / "calendar.csv"),
        "prices": pd.read_csv(m5_dir / "sell_prices.csv"),
    }
    return _M5_CACHE


def _fetch_m5_pick(m5: dict[str, pd.DataFrame], pick: M5Pick) -> None:
    sales, calendar, prices = m5["sales"], m5["calendar"], m5["prices"]

    row = sales[(sales["item_id"] == pick.item_id) & (sales["store_id"] == pick.store_id)]
    if row.empty:
        raise RuntimeError(
            f"M5: no row for item_id={pick.item_id}, store_id={pick.store_id}"
        )
    day_cols = [c for c in row.columns if c.startswith("d_")]
    series = row.iloc[0][day_cols].astype(int).values
    day_to_date = dict(zip(calendar["d"], pd.to_datetime(calendar["date"]), strict=False))
    dates = pd.Series([day_to_date[d] for d in day_cols])

    price_subset = prices[
        (prices["item_id"] == pick.item_id) & (prices["store_id"] == pick.store_id)
    ]
    median_price = (
        float(price_subset["sell_price"].median()) if not price_subset.empty else 3.5
    )

    meta = ScenarioMeta(
        scenario_id=pick.scenario_id,
        title=pick.title,
        description=pick.description,
        domain=pick.domain,
        sku_id=f"M5-{pick.item_id}-{pick.store_id}",
        source="m5_walmart",
        downloaded_at=date.today().isoformat(),
        start_date=dates.iloc[0].date().isoformat(),
    )
    costs = _derive_costs(
        median_price=median_price,
        demand_mean=float(series.mean()),
        unit_cost_ratio=pick.unit_cost_ratio,
        holding_annual_rate=pick.holding_annual_rate,
        fixed_order_cost=pick.fixed_order_cost,
        variable_order_cost_per_unit=pick.variable_order_cost_per_unit,
        starting_inventory_days=pick.starting_inventory_days,
    )
    _finalize_scenario(meta, dates, series.astype(np.int64), costs, pick.lead_time)


def fetch_m5(picks: list[M5Pick]) -> None:
    if not picks:
        return
    m5 = _load_m5()
    for pick in picks:
        _fetch_m5_pick(m5, pick)


# ---------------------------------------------------------------------------
# Corporación Favorita (Kaggle competition)
# ---------------------------------------------------------------------------


FAVORITA_COMPETITION = "favorita-grocery-sales-forecasting"
_FAVORITA_CHUNKSIZE = 5_000_000


def _kaggle_download_favorita() -> Path:
    """Download + extract the Favorita zip + nested .7z archives.

    The outer archive is a normal ``.zip`` containing per-file ``.7z``
    archives (Kaggle's chosen packaging). ``train.csv.7z`` decompresses to
    ~5 GB, so we always extract into the cache dir (never in-memory).
    """

    target_dir = CACHE_ROOT / "favorita"
    if (target_dir / "train.csv").exists() and (target_dir / "items.csv").exists():
        return target_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    outer_zip = target_dir / f"{FAVORITA_COMPETITION}.zip"

    if not outer_zip.exists():
        print(f"downloading Kaggle competition '{FAVORITA_COMPETITION}' (~460 MB zipped) ...")
        try:
            subprocess.run(
                [
                    "kaggle",
                    "competitions",
                    "download",
                    "-c",
                    FAVORITA_COMPETITION,
                    "-p",
                    str(target_dir),
                    "-q",
                ],
                check=True,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                "The 'kaggle' CLI was not found. Install with "
                "`poetry install --with data` and see the M5 auth notes above."
            ) from exc
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(
                "Kaggle CLI failed for Favorita. Common causes:\n"
                f"  - competition rules not yet accepted at https://www.kaggle.com/competitions/{FAVORITA_COMPETITION}/rules\n"
                "  - KAGGLE_API_TOKEN / ~/.kaggle/access_token / ~/.kaggle/kaggle.json missing or invalid\n"
                "  - SSL: corporate MITM proxy (see M5 notes for the SSL_CERT_FILE / REQUESTS_CA_BUNDLE workaround)."
            ) from exc

    if outer_zip.exists():
        print(f"extracting {outer_zip.name} ...")
        with zipfile.ZipFile(outer_zip) as zf:
            zf.extractall(target_dir)
        outer_zip.unlink()

    # Extract the inner .7z archives (Favorita ships CSVs individually
    # 7z-ed). Import ``py7zr`` lazily so ``uci``-only runs don't require it.
    import py7zr

    for archive in sorted(target_dir.glob("*.7z")):
        extracted = target_dir / archive.name.removesuffix(".7z")
        if extracted.exists():
            continue
        print(f"decompressing {archive.name} (may be slow for train.csv.7z) ...")
        with py7zr.SevenZipFile(archive, mode="r") as z:
            z.extractall(path=target_dir)
    return target_dir


def _favorita_daily_series(
    train_csv: Path,
    item_nbr: int,
    store_nbr: int,
) -> pd.DataFrame:
    """Chunked scan of Favorita ``train.csv`` for one item_nbr x store_nbr.

    Returns a DataFrame with columns ``date`` (datetime) and ``demand_units``
    (float, non-negative, unit_sales clipped at 0 to drop return rows). The
    caller is responsible for reindexing to a full calendar range and
    integer-rounding.
    """

    print(
        f"scanning train.csv for item_nbr={item_nbr}, store_nbr={store_nbr} "
        f"(chunksize={_FAVORITA_CHUNKSIZE:,}) ..."
    )
    parts: list[pd.DataFrame] = []
    for chunk in pd.read_csv(
        train_csv,
        usecols=["date", "store_nbr", "item_nbr", "unit_sales"],
        dtype={"store_nbr": "int32", "item_nbr": "int32", "unit_sales": "float32"},
        chunksize=_FAVORITA_CHUNKSIZE,
    ):
        sub = chunk[(chunk["store_nbr"] == store_nbr) & (chunk["item_nbr"] == item_nbr)]
        if sub.empty:
            continue
        sub = sub[["date", "unit_sales"]].copy()
        sub["unit_sales"] = sub["unit_sales"].clip(lower=0)
        parts.append(sub)
    if not parts:
        raise RuntimeError(
            f"Favorita: no rows for item_nbr={item_nbr}, store_nbr={store_nbr}. "
            "Check the picks against items.csv / stores.csv."
        )
    df = pd.concat(parts, ignore_index=True)
    df["date"] = pd.to_datetime(df["date"])
    daily = (
        df.groupby("date", as_index=False)["unit_sales"]
        .sum()
        .rename(columns={"unit_sales": "demand_units"})
        .sort_values("date")
    )
    return daily


def _fetch_favorita_pick(train_csv: Path, pick: FavoritaPick) -> None:
    daily = _favorita_daily_series(train_csv, pick.item_nbr, pick.store_nbr)
    full_range = pd.date_range(daily["date"].min(), daily["date"].max(), freq="D")
    daily = (
        daily.set_index("date")
        .reindex(full_range, fill_value=0)
        .rename_axis("date")
        .reset_index()
    )
    demand = np.rint(daily["demand_units"].to_numpy(dtype=np.float64)).astype(np.int64)

    meta = ScenarioMeta(
        scenario_id=pick.scenario_id,
        title=pick.title,
        description=pick.description,
        domain=pick.domain,
        sku_id=f"FAVORITA-{pick.item_nbr}-store{pick.store_nbr}",
        source="favorita_ecuador",
        downloaded_at=date.today().isoformat(),
        start_date=daily["date"].min().date().isoformat(),
    )
    costs = _derive_costs(
        median_price=pick.retail_price_usd,
        demand_mean=float(demand.mean()),
        unit_cost_ratio=pick.unit_cost_ratio,
        holding_annual_rate=pick.holding_annual_rate,
        fixed_order_cost=pick.fixed_order_cost,
        variable_order_cost_per_unit=pick.variable_order_cost_per_unit,
        starting_inventory_days=pick.starting_inventory_days,
    )
    _finalize_scenario(meta, daily["date"], demand, costs, pick.lead_time)


def fetch_favorita(picks: list[FavoritaPick]) -> None:
    if not picks:
        return
    fav_dir = _kaggle_download_favorita()
    train_csv = fav_dir / "train.csv"
    if not train_csv.exists():
        raise RuntimeError(f"expected extracted train.csv at {train_csv}")
    for pick in picks:
        _fetch_favorita_pick(train_csv, pick)


# ---------------------------------------------------------------------------
# Iowa Liquor Sales (Socrata Open Data API)
# ---------------------------------------------------------------------------


IOWA_SODA_ENDPOINT = "https://data.iowa.gov/resource/m3tr-qhgy.csv"


def _iowa_soda_query(pick: IowaPick) -> Path:
    """Download filtered rows for one item_no as a cached CSV.

    We ask the server to aggregate to daily totals for us via SoQL, so the
    response stays small (<< 5000 rows).
    """

    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    target_dir = CACHE_ROOT / "iowa_liquor"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{pick.item_no}_{pick.start_date}_{pick.end_date}.csv"
    if target.exists() and target.stat().st_size > 500:
        return target

    where = (
        f"itemno='{pick.item_no}' AND "
        f"date >= '{pick.start_date}T00:00:00' AND "
        f"date < '{pick.end_date}T00:00:00'"
    )
    params = {
        "$select": (
            "date_trunc_ymd(date) AS day, "
            "sum(bottles_sold) AS bottles, "
            "sum(sale_dollars) AS dollars"
        ),
        "$where": where,
        "$group": "day",
        "$order": "day",
        "$limit": str(pick.soda_limit),
    }
    if pick.soda_app_token:
        params["$$app_token"] = pick.soda_app_token
    url = f"{IOWA_SODA_ENDPOINT}?{urllib.parse.urlencode(params)}"
    print(
        f"downloading Iowa Liquor item_no={pick.item_no} "
        f"({pick.start_date}..{pick.end_date}) via SODA ..."
    )
    req = urllib.request.Request(url, headers={"User-Agent": "stochastic-inventory-reorder/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp, target.open("wb") as fh:
        shutil.copyfileobj(resp, fh)
    if target.stat().st_size < 500:
        raise RuntimeError(
            f"Iowa SODA returned an empty/tiny CSV for item_no={pick.item_no}. "
            "The item may not have sales in the requested window."
        )
    return target


def _fetch_iowa_pick(pick: IowaPick) -> None:
    csv_path = _iowa_soda_query(pick)
    df = pd.read_csv(csv_path)
    if df.empty:
        raise RuntimeError(f"Iowa Liquor: no rows for item_no={pick.item_no}")

    df["day"] = pd.to_datetime(df["day"]).dt.floor("D")
    df["bottles"] = df["bottles"].fillna(0).astype(int)
    df["dollars"] = df["dollars"].fillna(0).astype(float)
    df = df.sort_values("day").reset_index(drop=True)

    full_range = pd.date_range(df["day"].min(), df["day"].max(), freq="D")
    daily = (
        df.set_index("day")
        .reindex(full_range, fill_value=0)
        .rename_axis("day")
        .reset_index()
    )
    demand = daily["bottles"].to_numpy(dtype=np.int64)

    # Approximate wholesale bottle price = state receipts / bottles delivered.
    total_bottles = daily["bottles"].sum()
    total_dollars = daily["dollars"].sum()
    median_price = float(total_dollars / total_bottles) if total_bottles > 0 else 10.0

    meta = ScenarioMeta(
        scenario_id=pick.scenario_id,
        title=pick.title,
        description=pick.description,
        domain=pick.domain,
        sku_id=f"IOWA-{pick.item_no}",
        source="iowa_liquor_sales",
        downloaded_at=date.today().isoformat(),
        start_date=daily["day"].min().date().isoformat(),
    )
    costs = _derive_costs(
        median_price=median_price,
        demand_mean=float(demand.mean()),
        unit_cost_ratio=pick.unit_cost_ratio,
        holding_annual_rate=pick.holding_annual_rate,
        fixed_order_cost=pick.fixed_order_cost,
        variable_order_cost_per_unit=pick.variable_order_cost_per_unit,
        starting_inventory_days=pick.starting_inventory_days,
    )
    _finalize_scenario(meta, daily["day"], demand, costs, pick.lead_time)


def fetch_iowa(picks: list[IowaPick]) -> None:
    for pick in picks:
        _fetch_iowa_pick(pick)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _all_pick_ids() -> list[str]:
    ids: list[str] = []
    ids.extend(p.scenario_id for p in UCI_PICKS)
    ids.extend(p.scenario_id for p in M5_PICKS)
    ids.extend(p.scenario_id for p in FAVORITA_PICKS)
    ids.extend(p.scenario_id for p in IOWA_PICKS)
    return ids


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--dataset",
        choices=("uci", "m5", "favorita", "iowa", "all"),
        default="all",
        help="Which data source(s) to fetch.",
    )
    parser.add_argument(
        "--only",
        default=None,
        help=(
            "Fetch a single scenario_id (must appear in one of the *_PICKS "
            "lists). Overrides --dataset."
        ),
    )
    args = parser.parse_args(argv)

    SCENARIOS_ROOT.mkdir(parents=True, exist_ok=True)
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)

    if args.only is not None:
        known = _all_pick_ids()
        if args.only not in known:
            parser.error(
                f"unknown scenario_id {args.only!r}. Known: {', '.join(sorted(known))}"
            )
        uci_picks = [p for p in UCI_PICKS if p.scenario_id == args.only]
        m5_picks = [p for p in M5_PICKS if p.scenario_id == args.only]
        favorita_picks = [p for p in FAVORITA_PICKS if p.scenario_id == args.only]
        iowa_picks = [p for p in IOWA_PICKS if p.scenario_id == args.only]
    else:
        want_uci = args.dataset in ("uci", "all")
        want_m5 = args.dataset in ("m5", "all")
        want_favorita = args.dataset in ("favorita", "all")
        want_iowa = args.dataset in ("iowa", "all")
        uci_picks = list(UCI_PICKS) if want_uci else []
        m5_picks = list(M5_PICKS) if want_m5 else []
        favorita_picks = list(FAVORITA_PICKS) if want_favorita else []
        iowa_picks = list(IOWA_PICKS) if want_iowa else []

    ran_any = False
    if uci_picks:
        fetch_uci(uci_picks)
        ran_any = True
    if m5_picks:
        fetch_m5(m5_picks)
        ran_any = True
    if favorita_picks:
        fetch_favorita(favorita_picks)
        ran_any = True
    if iowa_picks:
        fetch_iowa(iowa_picks)
        ran_any = True
    if not ran_any:
        parser.error("no dataset selected")
    return 0


if __name__ == "__main__":
    sys.exit(main())
