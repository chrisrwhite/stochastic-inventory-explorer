import { useMemo } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  histogram,
  sampleLeadTimes,
  summarizeLeadTimeSamples,
} from "../lib/leadTimeSamplers";
import { useAppState } from "../state/AppState";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/Card";

const N_SAMPLES = 5000;

export function LeadTimeDistributionChart(): JSX.Element {
  const { config } = useAppState();

  const { bins, stats } = useMemo(() => {
    const samples = sampleLeadTimes(config.leadTime, N_SAMPLES, 12345);
    return {
      bins: histogram(samples),
      stats: summarizeLeadTimeSamples(samples),
    };
  }, [config.leadTime]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Lead-time distribution</CardTitle>
        <CardDescription>
          Simulated shipment durations under your current setting. Vertical marks show mean and 95th percentile.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3">
        <div className="h-40 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={bins} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.25} vertical={false} />
              <XAxis dataKey="day" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} width={30} />
              <Tooltip
                formatter={(v) => [String(v), "trials"]}
                labelFormatter={(day) => `${day} day${day === 1 ? "" : "s"}`}
              />
              <ReferenceLine
                x={stats.mean}
                stroke="hsl(160 84% 32%)"
                strokeDasharray="4 2"
                label={{ value: "mean", position: "top", fontSize: 10 }}
              />
              <ReferenceLine
                x={stats.p95}
                stroke="hsl(0 84% 55%)"
                strokeDasharray="4 2"
                label={{ value: "p95", position: "top", fontSize: 10 }}
              />
              <Bar dataKey="count" fill="hsl(215 80% 55%)" isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <dl className="grid grid-cols-2 sm:grid-cols-4 gap-x-4 gap-y-2 text-xs">
          <div>
            <dt className="text-muted-foreground">Mean</dt>
            <dd className="font-medium tabular-nums">{stats.mean.toFixed(1)} days</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Median</dt>
            <dd className="font-medium tabular-nums">{stats.median} days</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">p95</dt>
            <dd className="font-medium tabular-nums">{stats.p95} days</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Range</dt>
            <dd className="font-medium tabular-nums">
              {stats.min}–{stats.max}
            </dd>
          </div>
        </dl>
      </CardContent>
    </Card>
  );
}
