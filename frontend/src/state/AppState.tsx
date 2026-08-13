import {
  createContext,
  useContext,
  useMemo,
  useReducer,
  type Dispatch,
  type ReactNode,
} from "react";
import type {
  CostAssumptions,
  DemandModel,
  LeadTimeModel,
  OptimizationMode,
  PolicyFamily,
} from "../api/types";
import { defaultCosts, defaultLeadTime, initialConfig } from "./defaults";

export interface AppConfig {
  scenarioId: string | null;
  policyFamily: PolicyFamily;
  demandModel: DemandModel;
  leadTime: LeadTimeModel;
  costs: CostAssumptions;
  mode: OptimizationMode;
  targetServiceLevel: number;
  maxStockoutRisk: number;
  cvarStockoutBudget: number;
  nSimulations: number;
  horizonDays: number;
  randomSeed: number;
}

export type AppAction =
  | { type: "set_scenario"; scenarioId: string | null }
  | { type: "set_policy_family"; family: PolicyFamily }
  | { type: "set_demand_model"; model: DemandModel }
  | { type: "set_lead_time"; leadTime: LeadTimeModel }
  | { type: "set_costs"; costs: CostAssumptions }
  | { type: "set_mode"; mode: OptimizationMode }
  | { type: "set_target_service_level"; value: number }
  | { type: "set_max_stockout_risk"; value: number }
  | { type: "set_cvar_budget"; value: number }
  | { type: "set_horizon_days"; value: number }
  | { type: "set_n_simulations"; value: number }
  | { type: "reset"; config: AppConfig }
  | { type: "hydrate_from_scenario"; costs: CostAssumptions; leadTime: LeadTimeModel };

function reducer(state: AppConfig, action: AppAction): AppConfig {
  switch (action.type) {
    case "set_scenario":
      return { ...state, scenarioId: action.scenarioId };
    case "set_policy_family":
      return { ...state, policyFamily: action.family };
    case "set_demand_model":
      return { ...state, demandModel: action.model };
    case "set_lead_time":
      return { ...state, leadTime: action.leadTime };
    case "set_costs":
      return { ...state, costs: action.costs };
    case "set_mode":
      return { ...state, mode: action.mode };
    case "set_target_service_level":
      return { ...state, targetServiceLevel: action.value };
    case "set_max_stockout_risk":
      return { ...state, maxStockoutRisk: action.value };
    case "set_cvar_budget":
      return { ...state, cvarStockoutBudget: action.value };
    case "set_horizon_days":
      return { ...state, horizonDays: action.value };
    case "set_n_simulations":
      return { ...state, nSimulations: action.value };
    case "reset":
      return action.config;
    case "hydrate_from_scenario":
      return {
        ...state,
        costs: action.costs,
        leadTime: action.leadTime,
      };
    default:
      return state;
  }
}

interface AppStateValue {
  config: AppConfig;
  dispatch: Dispatch<AppAction>;
}

const AppStateContext = createContext<AppStateValue | null>(null);

export function AppStateProvider({
  children,
  initial,
}: {
  children: ReactNode;
  initial?: AppConfig;
}): JSX.Element {
  const [config, dispatch] = useReducer(reducer, initial ?? initialConfig);
  const value = useMemo(() => ({ config, dispatch }), [config]);
  return <AppStateContext.Provider value={value}>{children}</AppStateContext.Provider>;
}

export function useAppState(): AppStateValue {
  const ctx = useContext(AppStateContext);
  if (!ctx) {
    throw new Error("useAppState must be used within AppStateProvider");
  }
  return ctx;
}

export { defaultCosts, defaultLeadTime };
