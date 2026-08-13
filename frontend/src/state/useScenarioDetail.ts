import { useEffect, useState } from "react";
import { fetchScenarioDetail } from "../api/client";

export interface ScenarioDetail {
  scenario_id: string;
  demand_history: number[];
  weekday: number[];
  costs: Record<string, number>;
  lead_time: Record<string, unknown>;
  history_days: number;
  sku_id: string;
  title: string;
  description: string;
  domain: string;
  source: string;
  start_date: string;
}

export function useScenarioDetail(scenarioId: string | null): {
  detail: ScenarioDetail | null;
  isLoading: boolean;
  error: string | null;
} {
  const [detail, setDetail] = useState<ScenarioDetail | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!scenarioId) {
      setDetail(null);
      return;
    }
    const controller = new AbortController();
    setIsLoading(true);
    setError(null);
    fetchScenarioDetail(scenarioId, controller.signal)
      .then((d) => {
        setDetail(d as ScenarioDetail);
        setIsLoading(false);
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setError(err instanceof Error ? err.message : String(err));
        setIsLoading(false);
      });
    return () => controller.abort();
  }, [scenarioId]);

  return { detail, isLoading, error };
}
