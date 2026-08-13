import type {
  OptimizeRequest,
  OptimizeResponse,
  ScenarioSummary,
} from "./types";

const BASE_URL = "";

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function jsonFetch<T>(
  path: string,
  init?: RequestInit & { signal?: AbortSignal },
): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      // ignore body parse errors
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

export async function fetchScenarios(signal?: AbortSignal): Promise<ScenarioSummary[]> {
  const body = await jsonFetch<{ scenarios: ScenarioSummary[] }>(
    "/api/scenarios",
    { signal },
  );
  return body.scenarios;
}

export async function fetchScenarioDetail(
  scenarioId: string,
  signal?: AbortSignal,
): Promise<{
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
}> {
  return jsonFetch(`/api/scenarios/${encodeURIComponent(scenarioId)}`, { signal });
}

export async function postOptimize(
  request: OptimizeRequest,
  signal?: AbortSignal,
): Promise<OptimizeResponse> {
  return jsonFetch<OptimizeResponse>("/api/optimize", {
    method: "POST",
    body: JSON.stringify(request),
    signal,
  });
}

export { ApiError };
