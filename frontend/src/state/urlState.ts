/**
 * The URL is the session.
 *
 * The backend holds no per-visitor state: every request carries its full
 * configuration in the body and gets its whole result back inline. That is
 * what lets the service scale out freely, but it also means the *client* is
 * solely responsible for remembering what the visitor set up. If a knob is not
 * in the URL, it does not survive a reload and it does not travel when someone
 * shares a link.
 *
 * So the whole `AppConfig` round-trips through the query string, not just the
 * headline knobs. Anything omitted would silently fall back to a default, and
 * the recipient of a shared link would run a *different* scenario than the
 * sender saw while both pages showed the same URL.
 *
 * Only values that differ from `initialConfig` are written, which keeps the
 * common case short (`?s=walmart_pantry_m5&p=s_S&m=service_level&sl=0.950`)
 * while still making a heavily customised setup fully shareable.
 */

import { useEffect, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import type {
  CostAssumptions,
  DemandModel,
  LeadTimeDistribution,
  LeadTimeModel,
  OptimizationMode,
  PolicyFamily,
} from "../api/types";
import { useAppState, type AppConfig } from "./AppState";
import { initialConfig } from "./defaults";

const KEYS = {
  scenario: "s",
  policyFamily: "p",
  mode: "m",
  target: "sl",
  stockout: "sr",
  cvar: "cvar",
  demandModel: "dm",
  leadTime: "lt",
  costs: "c",
  nSimulations: "n",
  horizonDays: "h",
  seed: "seed",
} as const;

const VALID_POLICY_FAMILIES: PolicyFamily[] = ["r_Q", "s_S"];
const VALID_MODES: OptimizationMode[] = ["service_level", "stockout_risk", "cvar_budget"];
const VALID_DEMAND_MODELS: DemandModel[] = [
  "empirical_bootstrap",
  "seasonal_bootstrap",
  "poisson",
  "negative_binomial",
];
const VALID_LEAD_TIME_DISTRIBUTIONS: LeadTimeDistribution[] = [
  "fixed",
  "empirical",
  "empirical_discrete",
  "triangular",
  "lognormal",
  "poisson_shifted",
];

/**
 * Cost fields in a fixed order, so the seven of them ride in one compact
 * `c=10,0.05,8,5,0,20,1` parameter instead of seven separate ones.
 */
const COST_FIELDS: readonly (keyof CostAssumptions)[] = [
  "unit_cost",
  "holding_cost_per_unit_per_day",
  "stockout_cost_per_unit",
  "fixed_order_cost",
  "variable_order_cost_per_unit",
  "starting_inventory",
  "review_period_days",
];

/**
 * Numeric lead-time fields, encoded as `distribution:key=value,...`. Which of
 * them apply depends on the distribution, so they are all optional and only
 * the ones actually set get written.
 */
type LeadTimeNumericField =
  | "days"
  | "min_days"
  | "mode_days"
  | "max_days"
  | "mean_days"
  | "std_days";

const LEAD_TIME_FIELDS: readonly LeadTimeNumericField[] = [
  "days",
  "min_days",
  "mode_days",
  "max_days",
  "mean_days",
  "std_days",
];

function num(raw: string | null, lo: number, hi: number): number | null {
  if (raw === null) return null;
  const v = Number(raw);
  return Number.isFinite(v) && v >= lo && v <= hi ? v : null;
}

/** Trim float noise so `0.05` does not serialise as `0.05000000000000001`. */
function shortNum(v: number): string {
  return String(Math.round(v * 1e6) / 1e6);
}

function encodeCosts(costs: CostAssumptions): string {
  return COST_FIELDS.map((f) => shortNum(costs[f])).join(",");
}

function decodeCosts(raw: string | null): CostAssumptions | null {
  if (!raw) return null;
  const parts = raw.split(",");
  if (parts.length !== COST_FIELDS.length) return null;
  const out = { ...initialConfig.costs };
  for (let i = 0; i < COST_FIELDS.length; i += 1) {
    const v = Number(parts[i]);
    // Costs are all non-negative; review_period_days is additionally an int,
    // but the backend clamps that, so bounds-checking the sign is enough here.
    if (!Number.isFinite(v) || v < 0) return null;
    out[COST_FIELDS[i]] = v;
  }
  return out;
}

function encodeLeadTime(lt: LeadTimeModel): string {
  const params: string[] = [];
  for (const field of LEAD_TIME_FIELDS) {
    const value = lt[field];
    if (typeof value === "number") params.push(`${field}=${shortNum(value)}`);
  }
  return params.length ? `${lt.distribution}:${params.join(",")}` : lt.distribution;
}

function decodeLeadTime(raw: string | null): LeadTimeModel | null {
  if (!raw) return null;
  const [distribution, params] = raw.split(":");
  if (!VALID_LEAD_TIME_DISTRIBUTIONS.includes(distribution as LeadTimeDistribution)) {
    return null;
  }
  const out: LeadTimeModel = { distribution: distribution as LeadTimeDistribution };
  for (const pair of (params ?? "").split(",").filter(Boolean)) {
    const [key, value] = pair.split("=");
    const field = LEAD_TIME_FIELDS.find((f) => f === key);
    if (!field) continue;
    const v = Number(value);
    if (!Number.isFinite(v) || v < 0) return null;
    out[field] = v;
  }
  return out;
}

/** Structural comparison against the default, so unchanged values stay out of the URL. */
function isDefault(value: unknown, fallback: unknown): boolean {
  return JSON.stringify(value) === JSON.stringify(fallback);
}

export function readConfigFromSearch(search: string): AppConfig {
  const params = new URLSearchParams(search);
  const config: AppConfig = { ...initialConfig };

  const scenario = params.get(KEYS.scenario);
  if (scenario) config.scenarioId = scenario;

  const family = params.get(KEYS.policyFamily);
  if (family && VALID_POLICY_FAMILIES.includes(family as PolicyFamily)) {
    config.policyFamily = family as PolicyFamily;
  }

  const mode = params.get(KEYS.mode);
  if (mode && VALID_MODES.includes(mode as OptimizationMode)) {
    config.mode = mode as OptimizationMode;
  }

  const demandModel = params.get(KEYS.demandModel);
  if (demandModel && VALID_DEMAND_MODELS.includes(demandModel as DemandModel)) {
    config.demandModel = demandModel as DemandModel;
  }

  const target = num(params.get(KEYS.target), 0.5, 0.999);
  if (target !== null) config.targetServiceLevel = target;

  const stockout = num(params.get(KEYS.stockout), 0.001, 0.5);
  if (stockout !== null) config.maxStockoutRisk = stockout;

  const cvar = num(params.get(KEYS.cvar), 0, Number.MAX_SAFE_INTEGER);
  if (cvar !== null) config.cvarStockoutBudget = cvar;

  // Bounds mirror the backend request schema. Values outside them are dropped
  // rather than clamped: a link that would silently run something other than
  // what it says should fall back to the known default instead.
  const nSims = num(params.get(KEYS.nSimulations), 100, 10000);
  if (nSims !== null) config.nSimulations = Math.round(nSims);

  const horizon = num(params.get(KEYS.horizonDays), 14, 365);
  if (horizon !== null) config.horizonDays = Math.round(horizon);

  const seed = num(params.get(KEYS.seed), 0, 2 ** 31 - 1);
  if (seed !== null) config.randomSeed = Math.round(seed);

  const leadTime = decodeLeadTime(params.get(KEYS.leadTime));
  if (leadTime) config.leadTime = leadTime;

  const costs = decodeCosts(params.get(KEYS.costs));
  if (costs) config.costs = costs;

  return config;
}

/**
 * Serialise `config` into `search`, preserving any parameters the config does
 * not own (the Results page's `tab`, for instance).
 */
export function writeConfigToSearch(config: AppConfig, search: string): string {
  const params = new URLSearchParams(search);

  const set = (key: string, value: string | null): void => {
    if (value === null) params.delete(key);
    else params.set(key, value);
  };

  set(KEYS.scenario, config.scenarioId);
  set(KEYS.policyFamily, config.policyFamily);
  set(KEYS.mode, config.mode);

  // Only the objective actually in force -- carrying all three would put stale
  // numbers in the URL for the two modes that are not running.
  set(
    KEYS.target,
    config.mode === "service_level" ? config.targetServiceLevel.toFixed(3) : null,
  );
  set(
    KEYS.stockout,
    config.mode === "stockout_risk" ? config.maxStockoutRisk.toFixed(3) : null,
  );
  set(
    KEYS.cvar,
    config.mode === "cvar_budget" ? String(Math.round(config.cvarStockoutBudget)) : null,
  );

  // The rest appear only when customised, keeping the everyday URL short.
  set(
    KEYS.demandModel,
    isDefault(config.demandModel, initialConfig.demandModel) ? null : config.demandModel,
  );
  set(
    KEYS.leadTime,
    isDefault(config.leadTime, initialConfig.leadTime) ? null : encodeLeadTime(config.leadTime),
  );
  set(
    KEYS.costs,
    isDefault(config.costs, initialConfig.costs) ? null : encodeCosts(config.costs),
  );
  set(
    KEYS.nSimulations,
    config.nSimulations === initialConfig.nSimulations ? null : String(config.nSimulations),
  );
  set(
    KEYS.horizonDays,
    config.horizonDays === initialConfig.horizonDays ? null : String(config.horizonDays),
  );
  set(
    KEYS.seed,
    config.randomSeed === initialConfig.randomSeed ? null : String(config.randomSeed),
  );

  return params.toString();
}

export function useSyncConfigToUrl(): void {
  const { config } = useAppState();
  const navigate = useNavigate();
  const location = useLocation();
  const lastSerialized = useRef<string>("");

  useEffect(() => {
    const next = writeConfigToSearch(config, location.search);
    if (next === lastSerialized.current) return;
    lastSerialized.current = next;
    navigate({ pathname: location.pathname, search: `?${next}` }, { replace: true });
  }, [config, location.pathname, location.search, navigate]);
}
