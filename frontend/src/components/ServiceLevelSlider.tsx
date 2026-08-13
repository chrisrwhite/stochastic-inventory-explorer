import { useAppState } from "../state/AppState";
import type { OptimizationMode, PolicyFamily } from "../api/types";
import { formatPercent } from "../lib/utils";
import { useOptimize } from "../state/useOptimize";
import { Button } from "./ui/Button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/Card";
import { Select } from "./ui/Select";
import { Slider } from "./ui/Slider";

const MODES: { value: OptimizationMode; label: string }[] = [
  { value: "service_level", label: "Target service level" },
  { value: "stockout_risk", label: "Max stockout risk" },
  { value: "cvar_budget", label: "CVaR budget" },
];

const POLICY_FAMILIES: { value: PolicyFamily; label: string }[] = [
  { value: "s_S", label: "Order up to target" },
  { value: "r_Q", label: "Fixed order size" },
];

export function ServiceLevelSlider(): JSX.Element {
  const { config, dispatch } = useAppState();
  const { hasRun, isStale, isLoading, run } = useOptimize();
  const showRerunButton = hasRun && isStale;

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle>Policy target</CardTitle>
            <CardDescription>
              Adjust family, mode, or the target, then re-optimize to see the new frontier.
            </CardDescription>
          </div>
          {showRerunButton && (
            <Button
              size="sm"
              onClick={run}
              disabled={isLoading}
              className="animate-pulse-subtle"
            >
              {isLoading ? "Re-optimizing…" : "Re-optimize →"}
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent className="grid gap-4">
        <div className="grid grid-cols-2 gap-3">
          <div className="grid gap-1.5">
            <span className="text-sm font-medium">Policy family</span>
            <Select
              value={config.policyFamily}
              onChange={(e) =>
                dispatch({ type: "set_policy_family", family: e.target.value as PolicyFamily })
              }
            >
              {POLICY_FAMILIES.map((f) => (
                <option key={f.value} value={f.value}>
                  {f.label}
                </option>
              ))}
            </Select>
          </div>
          <div className="grid gap-1.5">
            <span className="text-sm font-medium">Optimization mode</span>
            <Select
              value={config.mode}
              onChange={(e) => dispatch({ type: "set_mode", mode: e.target.value as OptimizationMode })}
            >
              {MODES.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </Select>
          </div>
        </div>

        {config.mode === "service_level" && (
          <div className="grid gap-2">
            <div className="flex items-center justify-between text-sm">
              <span>Target service level</span>
              <span className="font-medium tabular-nums">
                {formatPercent(config.targetServiceLevel)}
              </span>
            </div>
            <Slider
              min={0.5}
              max={0.999}
              step={0.005}
              value={[config.targetServiceLevel]}
              onValueChange={([v]) =>
                dispatch({ type: "set_target_service_level", value: Number(v.toFixed(3)) })
              }
            />
          </div>
        )}

        {config.mode === "stockout_risk" && (
          <div className="grid gap-2">
            <div className="flex items-center justify-between text-sm">
              <span>Maximum stockout probability</span>
              <span className="font-medium tabular-nums">
                {formatPercent(config.maxStockoutRisk)}
              </span>
            </div>
            <Slider
              min={0.001}
              max={0.5}
              step={0.005}
              value={[config.maxStockoutRisk]}
              onValueChange={([v]) =>
                dispatch({ type: "set_max_stockout_risk", value: Number(v.toFixed(3)) })
              }
            />
          </div>
        )}

        {config.mode === "cvar_budget" && (
          <div className="grid gap-2">
            <div className="flex items-center justify-between text-sm">
              <span>CVaR budget ($)</span>
              <span className="font-medium tabular-nums">
                ${config.cvarStockoutBudget.toFixed(0)}
              </span>
            </div>
            <Slider
              min={0}
              max={2000}
              step={5}
              value={[config.cvarStockoutBudget]}
              onValueChange={([v]) => dispatch({ type: "set_cvar_budget", value: v })}
            />
          </div>
        )}
      </CardContent>
    </Card>
  );
}
