import type { ComparisonPolicy, MetricSummary, PolicyOut } from "../api/types";
import { cn, formatCurrency, formatPercent } from "../lib/utils";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/Card";

const LABELS: Record<string, string> = {
  lean: "Lean",
  conservative: "Conservative",
  order_when_empty: "Order when empty",
  average_demand: "Average demand",
};

interface Row {
  key: string;
  label: string;
  isPicked: boolean;
  policy: PolicyOut;
  metrics: MetricSummary;
  costDelta: number;
  serviceDelta: number;
  stockoutDelta: number;
  inventoryDelta: number;
}

function policyString(p: PolicyOut): string {
  return p.policy_family === "r_Q"
    ? `r=${p.reorder_point}, Q=${p.order_quantity}`
    : `r=${p.reorder_point}, S=${p.order_up_to}`;
}

function deltaClass(value: number, betterWhen: "lower" | "higher"): string {
  if (Math.abs(value) < 1e-6) return "text-muted-foreground";
  const better = betterWhen === "lower" ? value < 0 : value > 0;
  return better ? "text-emerald-600 dark:text-emerald-400" : "text-red-600 dark:text-red-400";
}

function fmtDelta(value: number, kind: "currency" | "percent"): string {
  if (Math.abs(value) < 1e-6) return "-";
  const sign = value > 0 ? "+" : "";
  if (kind === "currency") return `${sign}${formatCurrency(value)}`;
  return `${sign}${(value * 100).toFixed(1)}%`;
}

export function ScenarioCompare({
  comparisons,
  recommended,
  recommendedMetrics,
}: {
  comparisons: ComparisonPolicy[];
  recommended: PolicyOut;
  recommendedMetrics: MetricSummary;
}): JSX.Element {
  const rows: Row[] = [
    {
      key: "__picked",
      label: "Recommended",
      isPicked: true,
      policy: recommended,
      metrics: recommendedMetrics,
      costDelta: 0,
      serviceDelta: 0,
      stockoutDelta: 0,
      inventoryDelta: 0,
    },
    ...comparisons.map((c) => ({
      key: c.label,
      label: LABELS[c.label] ?? c.label,
      isPicked: false,
      policy: c.policy,
      metrics: c.metrics,
      costDelta: c.metrics.expected_total_cost - recommendedMetrics.expected_total_cost,
      serviceDelta: c.metrics.cycle_service_level - recommendedMetrics.cycle_service_level,
      stockoutDelta: c.metrics.stockout_probability - recommendedMetrics.stockout_probability,
      inventoryDelta: c.metrics.average_on_hand - recommendedMetrics.average_on_hand,
    })),
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Alternatives</CardTitle>
        <CardDescription>
          Reference policies simulated on the same demand and lead-time draws. Green cells beat the
          recommendation on that metric; red cells lose.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-xs uppercase text-muted-foreground">
              <tr className="border-b">
                <th className="py-2 pr-4 text-left font-medium">Policy</th>
                <th className="py-2 pr-4 text-right font-medium">Cost</th>
                <th className="py-2 pr-4 text-right font-medium">Service level</th>
                <th className="py-2 pr-4 text-right font-medium">Stockout prob.</th>
                <th className="py-2 pr-4 text-right font-medium">Avg on-hand</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr
                  key={r.key}
                  className={cn(
                    "border-b last:border-none",
                    r.isPicked && "bg-primary/5",
                  )}
                >
                  <td className="py-2 pr-4">
                    <div className="flex items-center gap-2">
                      {r.isPicked && (
                        <span className="rounded bg-primary px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-primary-foreground">
                          Picked
                        </span>
                      )}
                      <div>
                        <div className="font-medium">{r.label}</div>
                        <div className="text-xs text-muted-foreground">{policyString(r.policy)}</div>
                      </div>
                    </div>
                  </td>
                  <td className="py-2 pr-4 text-right tabular-nums">
                    <div>{formatCurrency(r.metrics.expected_total_cost)}</div>
                    {!r.isPicked && (
                      <div className={cn("text-xs", deltaClass(r.costDelta, "lower"))}>
                        {fmtDelta(r.costDelta, "currency")}
                      </div>
                    )}
                  </td>
                  <td className="py-2 pr-4 text-right tabular-nums">
                    <div>{formatPercent(r.metrics.cycle_service_level)}</div>
                    {!r.isPicked && (
                      <div className={cn("text-xs", deltaClass(r.serviceDelta, "higher"))}>
                        {fmtDelta(r.serviceDelta, "percent")}
                      </div>
                    )}
                  </td>
                  <td className="py-2 pr-4 text-right tabular-nums">
                    <div>{formatPercent(r.metrics.stockout_probability)}</div>
                    {!r.isPicked && (
                      <div className={cn("text-xs", deltaClass(r.stockoutDelta, "lower"))}>
                        {fmtDelta(r.stockoutDelta, "percent")}
                      </div>
                    )}
                  </td>
                  <td className="py-2 pr-4 text-right tabular-nums">
                    <div>{r.metrics.average_on_hand.toFixed(1)}</div>
                    {!r.isPicked && (
                      <div className={cn("text-xs", deltaClass(r.inventoryDelta, "lower"))}>
                        {r.inventoryDelta > 0 ? "+" : ""}
                        {r.inventoryDelta.toFixed(1)}
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}
