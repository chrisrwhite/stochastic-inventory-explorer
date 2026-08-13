import type {
  CostAssumptions,
  LeadTimeModel,
} from "../api/types";
import type { AppConfig } from "./AppState";

export const defaultCosts: CostAssumptions = {
  unit_cost: 10.0,
  holding_cost_per_unit_per_day: 0.05,
  stockout_cost_per_unit: 8.0,
  fixed_order_cost: 5.0,
  variable_order_cost_per_unit: 0.0,
  starting_inventory: 20.0,
  review_period_days: 1,
};

export const defaultLeadTime: LeadTimeModel = {
  distribution: "triangular",
  min_days: 2,
  mode_days: 4,
  max_days: 8,
};

export const initialConfig: AppConfig = {
  scenarioId: "walmart_pantry_m5",
  policyFamily: "s_S",
  demandModel: "empirical_bootstrap",
  leadTime: defaultLeadTime,
  costs: defaultCosts,
  mode: "service_level",
  targetServiceLevel: 0.95,
  maxStockoutRisk: 0.05,
  cvarStockoutBudget: 100,
  // 1000, not 2000. Cost is linear in trajectory count and Cloud Run's vCPU is
  // ~3.6x slower than a laptop core for this workload -- 2000 put the default
  // run at ~52 s in production, which is too long to sit through. Halving it
  // roughly halves the wait; the price is Monte Carlo standard error widening
  // by sqrt(2), which shows up as a slightly noisier cost-vs-reliability
  // scatter. Raise it here (up to MAX_N_SIMULATIONS) if the frontier ever
  // looks too ragged to read.
  nSimulations: 1000,
  horizonDays: 180,
  randomSeed: 42,
};
