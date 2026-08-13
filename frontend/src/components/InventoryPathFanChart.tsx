import { useMemo } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Label as RechartsLabel,
  Legend,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { PolicyOut, SimulationSummary } from "../api/types";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/Card";

interface FanRow {
  day: number;
  median: number;
  band_5_95: [number, number];
  band_25_75: [number, number];
  order_placed?: number;
  order_received?: number;
}

function percentileAt(sorted: number[], q: number): number {
  if (sorted.length === 0) return 0;
  const idx = Math.min(sorted.length - 1, Math.max(0, Math.floor(q * (sorted.length - 1))));
  return sorted[idx];
}

function buildFan(summary: SimulationSummary): FanRow[] {
  const horizon = summary.horizon_days;
  const rows: FanRow[] = [];

  const medianPath =
    summary.paths[Math.floor(summary.paths.length / 2)] ??
    summary.paths[0];

  for (let day = 0; day < horizon; day++) {
    const values = summary.paths
      .map((p) => p.on_hand[day] ?? 0)
      .sort((a, b) => a - b);
    const p5 = percentileAt(values, 0.05);
    const p25 = percentileAt(values, 0.25);
    const p50 = percentileAt(values, 0.5);
    const p75 = percentileAt(values, 0.75);
    const p95 = percentileAt(values, 0.95);

    const placed = medianPath?.orders_placed[day] ?? 0;
    const received = medianPath?.receipts[day] ?? 0;

    rows.push({
      day,
      median: p50,
      band_5_95: [p5, p95],
      band_25_75: [p25, p75],
      order_placed: placed > 0 ? p50 : undefined,
      order_received: received > 0 ? p50 : undefined,
    });
  }
  return rows;
}

export function InventoryPathFanChart({
  simulation,
  recommended,
}: {
  simulation: SimulationSummary;
  recommended: PolicyOut;
}): JSX.Element {
  const rows = useMemo(() => buildFan(simulation), [simulation]);
  const stockoutDaysFraction = useMemo(() => {
    if (simulation.paths.length === 0) return 0;
    const total = simulation.paths.reduce(
      (acc, p) => acc + p.on_hand.filter((v) => v <= 0).length,
      0,
    );
    return total / (simulation.paths.length * Math.max(simulation.horizon_days, 1));
  }, [simulation]);

  const orderS = recommended.order_up_to ?? null;
  const orderR = recommended.reorder_point ?? null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Possible futures</CardTitle>
        <CardDescription>
          Inventory on hand across {simulation.paths.length} simulated trajectories. Shaded bands
          are 5-95% and 25-75% percentile ranges. Orange = reorder point (r), green = order-up-to (S).
          Diamonds on the median trace mark days a replenishment order was placed; circles mark
          days a shipment arrived.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="h-80 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={rows} margin={{ top: 12, right: 24, bottom: 8, left: 8 }}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.35} />
              <XAxis dataKey="day">
                <RechartsLabel value="Day" position="insideBottom" offset={-4} fontSize={11} />
              </XAxis>
              <YAxis>
                <RechartsLabel
                  value="Units on hand"
                  angle={-90}
                  position="insideLeft"
                  fontSize={11}
                />
              </YAxis>
              <Tooltip
                formatter={(value, name) => {
                  if (Array.isArray(value)) {
                    const [lo, hi] = value as [number, number];
                    return [`${lo.toFixed(0)} to ${hi.toFixed(0)}`, name];
                  }
                  return [Number(value).toFixed(0), name];
                }}
              />
              <Legend />
              {orderR !== null && (
                <ReferenceLine
                  y={orderR}
                  stroke="hsl(30 90% 45%)"
                  strokeDasharray="4 3"
                  label={{ value: `r = ${orderR}`, position: "right", fontSize: 10 }}
                />
              )}
              {orderS !== null && (
                <ReferenceLine
                  y={orderS}
                  stroke="hsl(160 84% 32%)"
                  strokeDasharray="4 3"
                  label={{ value: `S = ${orderS}`, position: "right", fontSize: 10 }}
                />
              )}
              <ReferenceLine y={0} stroke="hsl(0 84% 55%)" strokeDasharray="2 4" />
              <Area
                dataKey="band_5_95"
                stroke="none"
                fill="hsl(215 80% 55%)"
                fillOpacity={0.15}
                name="5-95%"
                isAnimationActive={false}
              />
              <Area
                dataKey="band_25_75"
                stroke="none"
                fill="hsl(215 80% 55%)"
                fillOpacity={0.3}
                name="25-75%"
                isAnimationActive={false}
              />
              <Line
                dataKey="median"
                stroke="hsl(215 80% 40%)"
                dot={false}
                strokeWidth={2}
                name="Median"
                isAnimationActive={false}
              />
              <Scatter
                dataKey="order_placed"
                fill="hsl(30 90% 45%)"
                shape="diamond"
                name="Order placed"
                isAnimationActive={false}
              />
              <Scatter
                dataKey="order_received"
                fill="hsl(160 84% 32%)"
                shape="circle"
                name="Order received"
                isAnimationActive={false}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
        <p className="text-xs text-muted-foreground mt-2">
          Across every day of every simulation, on-hand hit or dropped below zero{" "}
          <span className="font-medium">{(stockoutDaysFraction * 100).toFixed(1)}%</span> of the
          time.
        </p>
      </CardContent>
    </Card>
  );
}
