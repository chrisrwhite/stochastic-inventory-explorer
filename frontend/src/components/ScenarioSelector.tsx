import { ExternalLink } from "lucide-react";
import { useEffect, useState } from "react";
import { fetchScenarioDetail, fetchScenarios } from "../api/client";
import type {
  CostAssumptions,
  LeadTimeModel,
  ScenarioSummary,
} from "../api/types";
import { cn } from "../lib/utils";
import { useAppState } from "../state/AppState";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/Card";

interface Provenance {
  label: string;
  href: string;
}

const PROVENANCE: Record<string, Provenance> = {
  m5_walmart: {
    label: "Walmart · Kaggle M5",
    href: "https://www.kaggle.com/competitions/m5-forecasting-accuracy",
  },
  favorita_ecuador: {
    label: "Corporación Favorita · Kaggle",
    href: "https://www.kaggle.com/competitions/favorita-grocery-sales-forecasting",
  },
  uci_online_retail_ii: {
    label: "UCI Online Retail II",
    href: "https://doi.org/10.24432/C5CG6D",
  },
};

function coerceCosts(raw: Record<string, number>, fallback: CostAssumptions): CostAssumptions {
  return {
    unit_cost: Number(raw.unit_cost ?? fallback.unit_cost),
    holding_cost_per_unit_per_day: Number(
      raw.holding_cost_per_unit_per_day ?? fallback.holding_cost_per_unit_per_day,
    ),
    stockout_cost_per_unit: Number(raw.stockout_cost_per_unit ?? fallback.stockout_cost_per_unit),
    fixed_order_cost: Number(raw.fixed_order_cost ?? fallback.fixed_order_cost),
    variable_order_cost_per_unit: Number(
      raw.variable_order_cost_per_unit ?? fallback.variable_order_cost_per_unit,
    ),
    starting_inventory: Number(raw.starting_inventory ?? fallback.starting_inventory),
    review_period_days: Number(raw.review_period_days ?? fallback.review_period_days),
  };
}

function coerceLeadTime(raw: Record<string, unknown>, fallback: LeadTimeModel): LeadTimeModel {
  const dist = String(raw.distribution ?? fallback.distribution) as LeadTimeModel["distribution"];
  const num = (v: unknown): number | undefined =>
    v == null ? undefined : Number(v);
  return {
    distribution: dist,
    days: num(raw.days),
    min_days: num(raw.min_days),
    mode_days: num(raw.mode_days),
    max_days: num(raw.max_days),
    mean_days: num(raw.mean_days),
    std_days: num(raw.std_days),
  };
}

function Sparkline({
  values,
  className,
}: {
  values: number[];
  className?: string;
}): JSX.Element {
  const width = 200;
  const height = 40;
  if (values.length < 2) {
    return (
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className={cn("w-full h-10", className)}
        preserveAspectRatio="none"
        role="img"
        aria-label="No demand data"
      />
    );
  }
  const max = Math.max(...values, 1);
  const step = width / (values.length - 1);
  const points = values
    .map(
      (v, i) =>
        `${(i * step).toFixed(1)},${(height - (v / max) * (height - 2) - 1).toFixed(1)}`,
    )
    .join(" ");
  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      className={cn("w-full h-10", className)}
      role="img"
      aria-label={`Last ${values.length} days of demand`}
    >
      <polyline
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        vectorEffect="non-scaling-stroke"
        points={points}
      />
    </svg>
  );
}

function scenarioStats(s: ScenarioSummary): {
  mean: number;
  zeroPct: number;
  yearsCovered: number;
} {
  const spark = s.sparkline;
  const mean = spark.length ? spark.reduce((a, b) => a + b, 0) / spark.length : 0;
  const zeroPct = spark.length ? spark.filter((v) => v === 0).length / spark.length : 0;
  const yearsCovered = s.history_days / 365;
  return { mean, zeroPct, yearsCovered };
}

function formatMean(n: number): string {
  if (n === 0) return "0/day";
  if (n < 1) return `${n.toFixed(2)}/day`;
  if (n < 10) return `${n.toFixed(1)}/day`;
  return `${Math.round(n)}/day`;
}

export function ScenarioSelector(): JSX.Element {
  const { config, dispatch } = useAppState();
  const [scenarios, setScenarios] = useState<ScenarioSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    fetchScenarios(controller.signal)
      .then(setScenarios)
      .catch((err: unknown) => {
        if (!controller.signal.aborted) {
          setError(err instanceof Error ? err.message : String(err));
        }
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!config.scenarioId) return;
    const controller = new AbortController();
    fetchScenarioDetail(config.scenarioId, controller.signal)
      .then((detail) => {
        dispatch({
          type: "hydrate_from_scenario",
          costs: coerceCosts(detail.costs, config.costs),
          leadTime: coerceLeadTime(detail.lead_time, config.leadTime),
        });
      })
      .catch((err: unknown) => {
        if (!controller.signal.aborted) {
          setError(err instanceof Error ? err.message : String(err));
        }
      });
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [config.scenarioId]);

  const selected = scenarios.find((s) => s.scenario_id === config.scenarioId);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Scenario</CardTitle>
        <CardDescription>
          Pick one of the bundled real-world POS scenarios. Each card previews the last 90 days of
          demand from the underlying dataset.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3">
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
          {scenarios.map((s) => {
            const isActive = config.scenarioId === s.scenario_id;
            const stats = scenarioStats(s);
            const prov = PROVENANCE[s.source];
            return (
              <button
                key={s.scenario_id}
                type="button"
                onClick={() =>
                  dispatch({ type: "set_scenario", scenarioId: s.scenario_id })
                }
                className={cn(
                  "group grid gap-2 rounded-lg border bg-background p-3 text-left transition-colors hover:bg-accent/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  isActive && "border-primary ring-2 ring-primary/40 bg-accent/30",
                )}
                aria-pressed={isActive}
              >
                <div className="text-sm font-medium leading-snug">{s.title}</div>
                <Sparkline
                  values={s.sparkline}
                  className={cn(
                    isActive
                      ? "text-primary"
                      : "text-muted-foreground/60 group-hover:text-primary/80",
                  )}
                />
                <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground tabular-nums">
                  <span>{formatMean(stats.mean)}</span>
                  <span aria-hidden>·</span>
                  <span>{(stats.zeroPct * 100).toFixed(0)}% zero-days</span>
                  <span aria-hidden>·</span>
                  <span>{stats.yearsCovered.toFixed(1)} yrs</span>
                </div>
                {prov && (
                  <a
                    href={prov.href}
                    target="_blank"
                    rel="noreferrer"
                    onClick={(e) => e.stopPropagation()}
                    className="inline-flex w-fit items-center gap-1 rounded-full border bg-muted/50 px-2 py-0.5 text-[10px] uppercase tracking-wide text-muted-foreground hover:text-foreground"
                  >
                    {prov.label}
                    <ExternalLink className="h-2.5 w-2.5" />
                  </a>
                )}
              </button>
            );
          })}
        </div>
        {selected && (
          <p className="text-sm text-muted-foreground border-t pt-3">{selected.description}</p>
        )}
        {error && <p className="text-sm text-destructive">{error}</p>}
      </CardContent>
    </Card>
  );
}
