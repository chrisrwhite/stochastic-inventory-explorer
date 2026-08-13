import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { postOptimize } from "../api/client";
import type { OptimizeRequest, OptimizeResponse } from "../api/types";
import { useAppState, type AppConfig } from "./AppState";

export interface OptimizeContextValue {
  data: OptimizeResponse | null;
  isLoading: boolean;
  error: string | null;
  request: OptimizeRequest | null;
  lastElapsedMs: number | null;
  hasValidConfig: boolean;
  hasRun: boolean;
  isStale: boolean;
  run: () => void;
}

const OptimizeContext = createContext<OptimizeContextValue | null>(null);

export function buildOptimizeRequest(config: AppConfig): OptimizeRequest | null {
  if (!config.scenarioId) return null;
  return {
    scenario_id: config.scenarioId,
    policy_family: config.policyFamily,
    demand_model: config.demandModel,
    lead_time_model: config.leadTime,
    mode: config.mode,
    target_service_level:
      config.mode === "service_level" ? config.targetServiceLevel : null,
    max_stockout_risk: config.mode === "stockout_risk" ? config.maxStockoutRisk : null,
    cvar_stockout_budget:
      config.mode === "cvar_budget" ? config.cvarStockoutBudget : null,
    costs: config.costs,
    n_simulations: config.nSimulations,
    horizon_days: config.horizonDays,
    random_seed: config.randomSeed,
  };
}

export function OptimizeProvider({ children }: { children: ReactNode }): JSX.Element {
  const { config } = useAppState();
  const request = buildOptimizeRequest(config);
  const key = request ? JSON.stringify(request) : null;

  const [data, setData] = useState<OptimizeResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastAppliedKey, setLastAppliedKey] = useState<string | null>(null);
  const [lastElapsedMs, setLastElapsedMs] = useState<number | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Keep the latest request/key in refs so run() is stable and always uses
  // the most recent config without re-creating on every keystroke.
  const requestRef = useRef(request);
  const keyRef = useRef(key);
  useEffect(() => {
    requestRef.current = request;
    keyRef.current = key;
  }, [request, key]);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  const run = useCallback((): void => {
    const currentRequest = requestRef.current;
    const currentKey = keyRef.current;
    if (!currentRequest || !currentKey) return;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setIsLoading(true);
    setError(null);
    const started = performance.now();
    postOptimize(currentRequest, controller.signal)
      .then((response) => {
        if (controller.signal.aborted) return;
        setData(response);
        setLastAppliedKey(currentKey);
        setLastElapsedMs(Math.round(performance.now() - started));
        setIsLoading(false);
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setError(err instanceof Error ? err.message : String(err));
        setIsLoading(false);
      });
  }, []);

  const value = useMemo<OptimizeContextValue>(() => {
    const hasValidConfig = Boolean(request);
    const hasRun = Boolean(data && lastAppliedKey);
    const isStale = hasRun && key !== lastAppliedKey;
    return {
      data,
      isLoading,
      error,
      request,
      lastElapsedMs,
      hasValidConfig,
      hasRun,
      isStale,
      run,
    };
  }, [data, isLoading, error, request, key, lastAppliedKey, lastElapsedMs, run]);

  return <OptimizeContext.Provider value={value}>{children}</OptimizeContext.Provider>;
}

export function useOptimize(): OptimizeContextValue {
  const ctx = useContext(OptimizeContext);
  if (!ctx) {
    throw new Error("useOptimize must be used within OptimizeProvider");
  }
  return ctx;
}
