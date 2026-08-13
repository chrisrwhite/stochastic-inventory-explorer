import type { DemandModel } from "../api/types";
import { useAppState } from "../state/AppState";
import { Explain } from "./Explain";
import { Select } from "./ui/Select";

const OPTIONS: { value: DemandModel; label: string; description: string }[] = [
  {
    value: "empirical_bootstrap",
    label: "Empirical bootstrap",
    description:
      "Sample days uniformly from history. Preserves realistic spikes. (Recommended default.)",
  },
  {
    value: "seasonal_bootstrap",
    label: "Seasonal bootstrap",
    description: "Bootstrap by day-of-week to preserve weekly seasonality.",
  },
  {
    value: "poisson",
    label: "Poisson",
    description: "Independent Poisson daily demand with mean fitted from history.",
  },
  {
    value: "negative_binomial",
    label: "Negative binomial",
    description: "For bursty demand where the variance exceeds the mean.",
  },
];

export function DemandModelSelector(): JSX.Element {
  const { config, dispatch } = useAppState();
  const description = OPTIONS.find((o) => o.value === config.demandModel)?.description;
  return (
    <div className="grid gap-2">
      <div className="grid gap-1.5">
        <label className="flex items-center gap-1 text-sm font-medium">
          Demand model
          <Explain label="Demand model">
            How the Monte-Carlo simulation generates future daily demand from your history.
            Bootstrap methods resample real observed days (preserving realistic spikes and
            zero-days). Parametric methods (Poisson, Negative binomial) fit a distribution
            and sample from it, which is cleaner but sensitive to model misfit.
          </Explain>
        </label>
        <Select
          value={config.demandModel}
          onChange={(e) =>
            dispatch({ type: "set_demand_model", model: e.target.value as DemandModel })
          }
        >
          {OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </Select>
      </div>
      {description && (
        <p className="text-sm text-muted-foreground">{description}</p>
      )}
    </div>
  );
}
