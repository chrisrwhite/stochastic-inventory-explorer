export type PolicyFamily = "r_Q" | "s_S";

export type DemandModel =
  | "empirical_bootstrap"
  | "seasonal_bootstrap"
  | "poisson"
  | "negative_binomial";

export type LeadTimeDistribution =
  | "fixed"
  | "empirical"
  | "empirical_discrete"
  | "triangular"
  | "lognormal"
  | "poisson_shifted";

export type OptimizationMode = "service_level" | "stockout_risk" | "cvar_budget";

export interface LeadTimeModel {
  distribution: LeadTimeDistribution;
  days?: number;
  min_days?: number;
  mode_days?: number;
  max_days?: number;
  mean_days?: number;
  std_days?: number;
  samples?: number[];
}

export interface CostAssumptions {
  unit_cost: number;
  holding_cost_per_unit_per_day: number;
  stockout_cost_per_unit: number;
  fixed_order_cost: number;
  variable_order_cost_per_unit: number;
  starting_inventory: number;
  review_period_days: number;
}

export interface OptimizeRequest {
  scenario_id?: string | null;
  policy_family: PolicyFamily;
  demand_model: DemandModel;
  lead_time_model: LeadTimeModel;
  mode: OptimizationMode;
  target_service_level?: number | null;
  max_stockout_risk?: number | null;
  cvar_stockout_budget?: number | null;
  costs?: CostAssumptions | null;
  n_simulations: number;
  horizon_days: number;
  random_seed: number;
}

export interface PolicyOut {
  policy_family: PolicyFamily;
  reorder_point: number;
  order_quantity?: number | null;
  order_up_to?: number | null;
  safety_stock?: number | null;
}

export interface MetricSummary {
  expected_total_cost: number;
  expected_holding_cost: number;
  expected_ordering_cost: number;
  expected_stockout_cost: number;
  cycle_service_level: number;
  fill_rate: number;
  average_on_hand: number;
  average_orders_per_month: number;
  stockout_probability: number;
  cvar_stockout_cost: number;
  cvar_stockout_units: number;
  expected_stockout_units: number;
  horizon_days: number;
  n_sims: number;
}

export interface FrontierPoint {
  policy: PolicyOut;
  expected_total_cost: number;
  cycle_service_level: number;
  stockout_probability: number;
  fill_rate: number;
  average_on_hand: number;
  cvar_stockout_cost: number;
  is_recommended: boolean;
}

export interface ComparisonPolicy {
  label: string;
  policy: PolicyOut;
  metrics: MetricSummary;
  cost_delta: number;
  service_level_delta: number;
  stockout_probability_delta: number;
  average_on_hand_delta: number;
}

export interface SimulationPath {
  percentile: number;
  on_hand: number[];
  demand: number[];
  receipts: number[];
  orders_placed: number[];
}

export interface SimulationSummary {
  horizon_days: number;
  paths: SimulationPath[];
}

export interface PolicyExplanation {
  reorder_point: number;
  order_up_to: number | null;
  order_quantity: number | null;
  expected_lead_time_demand: number;
  safety_stock: number;
  service_level_target: number | null;
  dominant_cost_driver: string;
  narrative: string;
}

export interface OptimizeResponse {
  status: string;
  scenario_id: string | null;
  recommended_policy: PolicyOut;
  metrics: MetricSummary;
  frontier: FrontierPoint[];
  comparison_policies: ComparisonPolicy[];
  simulation: SimulationSummary;
  explanation: PolicyExplanation;
}

export interface ScenarioSummary {
  scenario_id: string;
  title: string;
  description: string;
  domain: string;
  sku_id: string;
  history_days: number;
  source: string;
  start_date: string;
  sparkline: number[];
}
