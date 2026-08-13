import type { MetricSummary, PolicyOut } from "../api/types";
import { formatCurrency, formatNumber, formatPercent } from "../lib/utils";
import { AdvancedPanel } from "./AdvancedPanel";
import { Explain } from "./Explain";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/Card";

function policyDescription(policy: PolicyOut): string {
  if (policy.policy_family === "r_Q") {
    return `Order ${policy.order_quantity} units whenever inventory drops to ${policy.reorder_point}.`;
  }
  return `Order up to ${policy.order_up_to} units whenever inventory drops to ${policy.reorder_point}.`;
}

function BigMetric({
  label,
  value,
  sub,
  explain,
}: {
  label: string;
  value: string;
  sub?: string;
  explain?: { title: string; body: React.ReactNode };
}): JSX.Element {
  return (
    <Card>
      <CardHeader className="pb-1">
        <CardTitle className="flex items-center gap-1 text-xs uppercase tracking-wide text-muted-foreground">
          {label}
          {explain && <Explain label={explain.title}>{explain.body}</Explain>}
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-1">
        <div className="text-2xl font-semibold tabular-nums">{value}</div>
        {sub && <div className="text-xs text-muted-foreground mt-1">{sub}</div>}
      </CardContent>
    </Card>
  );
}

function AdvancedMetric({
  label,
  value,
  explanation,
  explain,
}: {
  label: string;
  value: string;
  explanation: string;
  explain?: { title: string; body: React.ReactNode };
}): JSX.Element {
  return (
    <div className="grid gap-1 rounded-md border bg-background/50 p-3">
      <div className="flex items-baseline justify-between gap-2">
        <span className="flex items-center gap-1 text-xs uppercase tracking-wide text-muted-foreground">
          {label}
          {explain && <Explain label={explain.title}>{explain.body}</Explain>}
        </span>
        <span className="text-lg font-semibold tabular-nums">{value}</span>
      </div>
      <p className="text-xs text-muted-foreground">{explanation}</p>
    </div>
  );
}

export function PolicySummaryCards({
  policy,
  metrics,
}: {
  policy: PolicyOut;
  metrics: MetricSummary;
}): JSX.Element {
  const monthlyCost = (metrics.expected_total_cost / metrics.horizon_days) * 30;

  return (
    <div className="grid gap-3">
      <Card>
        <CardHeader className="pb-1">
          <CardTitle className="flex items-center gap-1 text-xs uppercase tracking-wide text-muted-foreground">
            Recommended policy
            <Explain label="Reorder point">
              The reorder point is the on-hand + on-order level at which we place a new order.
              It is roughly the expected demand during the lead time plus a safety-stock buffer
              sized for the reliability target you picked.
            </Explain>
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-1 text-sm">{policyDescription(policy)}</CardContent>
      </Card>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <BigMetric
          label="Monthly cost"
          value={formatCurrency(monthlyCost)}
          sub={`${formatCurrency(metrics.expected_total_cost)} over ${metrics.horizon_days} days`}
        />
        <BigMetric
          label="Reliability"
          value={formatPercent(metrics.cycle_service_level)}
          sub="Fraction of days without a stockout"
          explain={{
            title: "Reliability (cycle service level)",
            body: (
              <>
                The probability that a given day ends without a stockout. Also called cycle
                service level. Higher reliability requires more safety stock, which raises
                holding cost.
              </>
            ),
          }}
        />
        <BigMetric
          label="Avg on-hand"
          value={`${formatNumber(metrics.average_on_hand)} units`}
          sub={`${metrics.average_orders_per_month.toFixed(1)} orders/mo`}
        />
      </div>

      <AdvancedPanel
        label="Show all metrics"
        description="Fill rate, stockout probability, and tail-risk (CVaR)."
      >
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <AdvancedMetric
            label="Fill rate"
            value={formatPercent(metrics.fill_rate)}
            explanation="Fraction of demanded units served from stock. Usually higher than reliability because a stockout day still fulfills most units."
            explain={{
              title: "Fill rate",
              body: (
                <>
                  The fraction of demanded units that are shipped from on-hand inventory. A
                  fill rate of 98% means we shipped 98 of every 100 units customers wanted.
                </>
              ),
            }}
          />
          <AdvancedMetric
            label="Stockout probability"
            value={formatPercent(metrics.stockout_probability)}
            explanation="Chance any given day runs out. 1 − Reliability."
          />
          <AdvancedMetric
            label="CVaR stockout cost (95%)"
            value={formatCurrency(metrics.cvar_stockout_cost)}
            explanation="Average stockout cost across the worst 5% of simulated futures. Captures the rare, expensive tails."
            explain={{
              title: "CVaR",
              body: (
                <>
                  Conditional Value-at-Risk. The average stockout cost across only the worst
                  5% of the simulated futures. This is a tail-risk metric that catches rare but
                  expensive stockouts a plain average would miss.
                </>
              ),
            }}
          />
        </div>
      </AdvancedPanel>
    </div>
  );
}
