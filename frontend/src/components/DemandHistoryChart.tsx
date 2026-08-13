import { useMemo } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { formatNumber } from "../lib/utils";
import { useAppState } from "../state/AppState";
import { useScenarioDetail } from "../state/useScenarioDetail";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/Card";

const WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const RECENT_DAYS = 120;

function computeStats(history: number[]): {
  mean: number;
  std: number;
  max: number;
  zeroPct: number;
} {
  if (history.length === 0) return { mean: 0, std: 0, max: 0, zeroPct: 0 };
  const mean = history.reduce((s, v) => s + v, 0) / history.length;
  const variance =
    history.reduce((s, v) => s + (v - mean) * (v - mean), 0) / Math.max(history.length - 1, 1);
  return {
    mean,
    std: Math.sqrt(variance),
    max: Math.max(...history),
    zeroPct: history.filter((v) => v === 0).length / history.length,
  };
}

function computeWeekdayMeans(history: number[], weekday: number[]): number[] {
  const sums = Array(7).fill(0);
  const counts = Array(7).fill(0);
  for (let i = 0; i < history.length; i++) {
    const w = weekday[i] ?? i % 7;
    sums[w] += history[i];
    counts[w] += 1;
  }
  return sums.map((s, i) => (counts[i] > 0 ? s / counts[i] : 0));
}

export function DemandHistoryChart(): JSX.Element {
  const { config } = useAppState();
  const { detail, isLoading, error } = useScenarioDetail(config.scenarioId);

  const source = useMemo(() => {
    if (detail) {
      return {
        history: detail.demand_history,
        weekday: detail.weekday,
        label: detail.title,
      };
    }
    return null;
  }, [detail]);

  const chartData = useMemo(() => {
    if (!source) return [];
    const history = source.history;
    const start = Math.max(0, history.length - RECENT_DAYS);
    return history.slice(start).map((v, i) => ({ day: start + i, demand: v }));
  }, [source]);

  const stats = useMemo(
    () => (source ? computeStats(source.history) : null),
    [source],
  );

  const weekdayMeans = useMemo(
    () => (source ? computeWeekdayMeans(source.history, source.weekday) : null),
    [source],
  );
  const maxWeekday = weekdayMeans ? Math.max(...weekdayMeans, 0.0001) : 0.0001;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Demand history preview</CardTitle>
        <CardDescription>
          {source
            ? `The last ${Math.min(RECENT_DAYS, source.history.length)} days of ${source.label}.`
            : "Pick a scenario to preview its real demand history."}
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3">
        {isLoading && (
          <p className="text-sm text-muted-foreground">Loading scenario data…</p>
        )}
        {error && <p className="text-sm text-destructive">{error}</p>}
        {source && chartData.length > 0 && (
          <>
            <div className="h-40 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.25} vertical={false} />
                  <XAxis dataKey="day" hide />
                  <YAxis tick={{ fontSize: 11 }} width={30} />
                  <Tooltip
                    formatter={(v) => [String(v), "units"]}
                    labelFormatter={(day) => `day ${day}`}
                  />
                  <Bar dataKey="demand" fill="hsl(215 80% 55%)" isAnimationActive={false} />
                </BarChart>
              </ResponsiveContainer>
            </div>
            {stats && (
              <dl className="grid grid-cols-2 sm:grid-cols-4 gap-x-4 gap-y-2 text-xs">
                <div>
                  <dt className="text-muted-foreground">Avg per day</dt>
                  <dd className="font-medium tabular-nums">{formatNumber(stats.mean)}</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Std</dt>
                  <dd className="font-medium tabular-nums">{formatNumber(stats.std)}</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Max day</dt>
                  <dd className="font-medium tabular-nums">{stats.max}</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Zero days</dt>
                  <dd className="font-medium tabular-nums">
                    {(stats.zeroPct * 100).toFixed(0)}%
                  </dd>
                </div>
              </dl>
            )}
            {weekdayMeans && (
              <div>
                <div className="text-xs text-muted-foreground mb-1">Weekday pattern</div>
                <div className="flex gap-1">
                  {weekdayMeans.map((m, i) => (
                    <div key={i} className="flex-1 text-center">
                      <div
                        className="mx-auto rounded-sm bg-primary/70"
                        style={{
                          height: `${Math.max(4, Math.round((m / maxWeekday) * 32))}px`,
                          width: "100%",
                        }}
                        title={`${WEEKDAY_LABELS[i]}: ${m.toFixed(2)}`}
                      />
                      <div className="mt-1 text-[10px] text-muted-foreground">
                        {WEEKDAY_LABELS[i]}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
            <p className="text-xs text-muted-foreground border-t pt-2">
              Real POS data. See the scenario card for its source dataset.
            </p>
          </>
        )}
      </CardContent>
    </Card>
  );
}
