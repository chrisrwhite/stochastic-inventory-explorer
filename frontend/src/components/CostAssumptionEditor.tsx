import type { CostAssumptions } from "../api/types";
import { useAppState } from "../state/AppState";
import { Input } from "./ui/Input";
import { Label } from "./ui/Label";

const FIELDS: { key: keyof CostAssumptions; label: string; step?: number; min?: number }[] = [
  { key: "holding_cost_per_unit_per_day", label: "Holding cost / unit / day ($)", step: 0.01, min: 0 },
  { key: "stockout_cost_per_unit", label: "Stockout cost / unit ($)", step: 0.5, min: 0 },
  { key: "fixed_order_cost", label: "Fixed order cost ($)", step: 0.5, min: 0 },
  { key: "variable_order_cost_per_unit", label: "Variable order cost / unit ($)", step: 0.05, min: 0 },
  { key: "starting_inventory", label: "Starting inventory (units)", step: 1, min: 0 },
];

/**
 * Raw cost-assumption editor. Renders as a plain grid without a Card wrapper
 * so it embeds cleanly inside `<AdvancedPanel>`. Wrap it yourself if you need
 * card chrome.
 */
export function CostAssumptionEditor(): JSX.Element {
  const { config, dispatch } = useAppState();
  const costs = config.costs;

  function update(key: keyof CostAssumptions, raw: string): void {
    const v = raw === "" ? NaN : Number(raw);
    if (Number.isNaN(v)) return;
    dispatch({ type: "set_costs", costs: { ...costs, [key]: v } });
  }

  return (
    <div className="grid gap-3">
      <p className="text-xs text-muted-foreground">
        Prefilled from the selected scenario. Edit any field to see the impact on cost and policy.
        Unit cost is shown in the summary above for context but is not charged in the objective -
        for a fixed horizon and lost-sales assumption, total purchase cost is roughly constant
        across policies and does not change the optimum.
      </p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {FIELDS.map((f) => (
          <div key={f.key} className="grid gap-1.5">
            <Label>{f.label}</Label>
            <Input
              type="number"
              step={f.step ?? 0.1}
              min={f.min ?? 0}
              value={costs[f.key] as number}
              onChange={(e) => update(f.key, e.target.value)}
            />
          </div>
        ))}
      </div>
    </div>
  );
}
