import { useMemo } from "react";
import { formatCurrency } from "../lib/utils";
import { useAppState } from "../state/AppState";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/Card";

interface Row {
  label: string;
  amount: number;
  description: string;
}

export function CostBreakdownPreview(): JSX.Element {
  const { config } = useAppState();
  const c = config.costs;

  const rows = useMemo<Row[]>(() => {
    return [
      {
        label: "Hold 1 unit for a week",
        amount: c.holding_cost_per_unit_per_day * 7,
        description: `${formatCurrency(c.holding_cost_per_unit_per_day)}/day × 7 days`,
      },
      {
        label: "Place 1 order",
        amount: c.fixed_order_cost,
        description: `Fixed cost per replenishment`,
      },
      {
        label: "Miss 1 unit of demand",
        amount: c.stockout_cost_per_unit,
        description: `Penalty per unit not fulfilled`,
      },
    ];
  }, [c.holding_cost_per_unit_per_day, c.fixed_order_cost, c.stockout_cost_per_unit]);

  const max = Math.max(...rows.map((r) => r.amount), 0.001);

  return (
    <Card>
      <CardHeader>
        <CardTitle>What each cost means</CardTitle>
        <CardDescription>
          Concrete dollar impact of your current cost inputs, before the optimizer runs.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3">
        {rows.map((r) => (
          <div key={r.label} className="grid gap-1">
            <div className="flex items-baseline justify-between text-sm">
              <span>{r.label}</span>
              <span className="font-medium tabular-nums">{formatCurrency(r.amount)}</span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded bg-secondary">
              <div
                className="h-full bg-primary"
                style={{ width: `${(r.amount / max) * 100}%` }}
              />
            </div>
            <div className="text-xs text-muted-foreground">{r.description}</div>
          </div>
        ))}
        <p className="text-xs text-muted-foreground border-t pt-2">
          The optimizer minimizes the expected sum of these three costs across simulated futures,
          subject to your reliability target.
        </p>
      </CardContent>
    </Card>
  );
}
