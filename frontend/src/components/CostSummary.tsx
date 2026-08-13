import { useAppState } from "../state/AppState";
import { formatCurrency, formatNumber } from "../lib/utils";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/Card";

interface Row {
  label: string;
  value: string;
  hint?: string;
}

export function CostSummary(): JSX.Element {
  const { config } = useAppState();
  const c = config.costs;
  const rows: Row[] = [
    { label: "Unit cost", value: formatCurrency(c.unit_cost) },
    {
      label: "Holding cost / day",
      value: formatCurrency(c.holding_cost_per_unit_per_day),
      hint: "per unit",
    },
    {
      label: "Stockout cost",
      value: formatCurrency(c.stockout_cost_per_unit),
      hint: "per missed unit",
    },
    {
      label: "Fixed order cost",
      value: formatCurrency(c.fixed_order_cost),
      hint: "per order placed",
    },
    {
      label: "Variable order cost",
      value: formatCurrency(c.variable_order_cost_per_unit),
      hint: "per unit ordered",
    },
    {
      label: "Starting inventory",
      value: `${formatNumber(c.starting_inventory, 0)} units`,
    },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Cost assumptions</CardTitle>
        <CardDescription>
          Prefilled from the selected scenario. Edit them via the Advanced panel below.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-3 text-sm">
          {rows.map((r) => (
            <div key={r.label} className="grid gap-0.5">
              <dt className="text-xs text-muted-foreground">{r.label}</dt>
              <dd className="font-medium tabular-nums">
                {r.value}
                {r.hint && (
                  <span className="ml-1 text-xs font-normal text-muted-foreground">
                    {r.hint}
                  </span>
                )}
              </dd>
            </div>
          ))}
        </dl>
      </CardContent>
    </Card>
  );
}
