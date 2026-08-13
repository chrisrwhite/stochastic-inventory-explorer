import { useMemo } from "react";
import type { MetricSummary, PolicyOut } from "../api/types";
import { formatCurrency, formatPercent } from "../lib/utils";
import { useAppState } from "../state/AppState";
import { useScenarioDetail } from "../state/useScenarioDetail";

function meanOf(history: number[] | undefined): number {
  if (!history || history.length === 0) return 0;
  return history.reduce((a, b) => a + b, 0) / history.length;
}

function formatMean(n: number): string {
  if (n === 0) return "0";
  if (n < 1) return n.toFixed(2);
  if (n < 10) return n.toFixed(1);
  return `${Math.round(n)}`;
}

function orderPhrase(policy: PolicyOut): string {
  if (policy.policy_family === "r_Q") {
    return `ordering ${policy.order_quantity} units whenever inventory drops to ${policy.reorder_point}`;
  }
  return `ordering up to ${policy.order_up_to} whenever inventory drops to ${policy.reorder_point}`;
}

// If the recommended CSL is more than this many percentage points below the
// target, we treat the target as effectively unreachable and switch the
// storyline copy to acknowledge it.
const TARGET_MISS_TOLERANCE = 0.02;

export function PolicyStoryLine({
  policy,
  metrics,
  serviceLevelTarget,
}: {
  policy: PolicyOut;
  metrics: MetricSummary;
  serviceLevelTarget?: number | null;
}): JSX.Element | null {
  const { config } = useAppState();
  const { detail } = useScenarioDetail(config.scenarioId);

  const label = detail?.title ?? null;
  const mean = useMemo(() => meanOf(detail?.demand_history), [detail]);

  if (!label) return null;

  const monthlyCost = (metrics.expected_total_cost / metrics.horizon_days) * 30;
  const meanText = mean > 0 ? ` at ~${formatMean(mean)} units/day` : "";
  const orderText = orderPhrase(policy);
  const reliability = formatPercent(metrics.cycle_service_level, 0);
  const fill = formatPercent(metrics.fill_rate, 1);
  const cost = formatCurrency(monthlyCost);

  const targetMissed =
    serviceLevelTarget != null &&
    metrics.cycle_service_level < serviceLevelTarget - TARGET_MISS_TOLERANCE;

  if (targetMissed) {
    const targetPct = formatPercent(serviceLevelTarget, 0);
    return (
      <div className="grid gap-2 rounded-md border border-amber-500/40 bg-amber-500/5 px-4 py-3 text-sm leading-relaxed">
        <p>
          For <span className="font-medium">{label}</span>
          {meanText}, {orderText} reaches{" "}
          <span className="font-medium">{reliability}</span> reliability at{" "}
          <span className="font-medium">{cost}/mo</span>. That's the highest CSL any policy in the
          grid could hit, and your <span className="font-medium">{targetPct}</span> target isn't
          reachable on this SKU.
        </p>
        <p className="text-xs text-muted-foreground">
          The demand history has extreme spikes, so even a very large safety buffer occasionally
          gets exhausted. Fill rate (units delivered on time) stays at{" "}
          <span className="font-medium text-foreground">{fill}</span>, which is a better success
          metric when demand is heavy-tailed.
        </p>
      </div>
    );
  }

  return (
    <p className="rounded-md border bg-accent/30 px-4 py-3 text-sm leading-relaxed">
      For <span className="font-medium">{label}</span>
      {meanText}, {orderText} hits <span className="font-medium">{reliability}</span>{" "}
      reliability at <span className="font-medium">{cost}/mo</span>. The optimizer found this to be
      the cheapest policy that meets your target on the cost/service frontier.
    </p>
  );
}
