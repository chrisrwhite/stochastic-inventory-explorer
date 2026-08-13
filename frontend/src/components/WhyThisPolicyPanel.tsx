import "katex/dist/katex.min.css";
import { InlineMath } from "react-katex";
import { Link } from "react-router-dom";
import type { PolicyExplanation } from "../api/types";
import { formatNumber, formatPercent } from "../lib/utils";
import { Explain } from "./Explain";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/Card";

export function WhyThisPolicyPanel({
  explanation,
}: {
  explanation: PolicyExplanation;
}): JSX.Element {
  const reorderPoint =
    Math.round(explanation.expected_lead_time_demand) + explanation.safety_stock;
  return (
    <Card>
      <CardHeader>
        <CardTitle>Why this policy?</CardTitle>
        <CardDescription>
          Breakdown of the recommendation and dominant cost driver.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3">
        <p className="text-sm leading-relaxed">{explanation.narrative}</p>
        <div className="rounded-md border bg-muted/30 px-3 py-2 text-sm">
          <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
            Reorder point decomposition
          </div>
          <div className="overflow-x-auto py-0.5">
            <InlineMath
              math={String.raw`r \; = \; \underbrace{${Math.round(
                explanation.expected_lead_time_demand,
              )}}_{\mathbb{E}[D \cdot L]} \; + \; \underbrace{${explanation.safety_stock}}_{\text{safety stock}} \; = \; ${reorderPoint}`}
            />
          </div>
        </div>
        <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
          <div>
            <dt className="flex items-center gap-1 text-muted-foreground">
              Expected lead-time demand
              <Explain label="Expected lead-time demand">
                The average number of units we expect customers to buy in the days
                between placing an order and receiving it. Sets the base level of the
                reorder point before safety stock is added.
              </Explain>
            </dt>
            <dd className="font-medium tabular-nums">
              {formatNumber(explanation.expected_lead_time_demand)} units
            </dd>
          </div>
          <div>
            <dt className="flex items-center gap-1 text-muted-foreground">
              Safety stock
              <Explain label="Safety stock">
                Extra buffer inventory above the expected lead-time demand. Sized to
                absorb demand and lead-time noise so we hit the reliability target.
                More safety stock = higher reliability but higher holding cost.
              </Explain>
            </dt>
            <dd className="font-medium tabular-nums">{explanation.safety_stock} units</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Dominant cost driver</dt>
            <dd className="font-medium capitalize">{explanation.dominant_cost_driver}</dd>
          </div>
          {explanation.service_level_target != null && (
            <div>
              <dt className="text-muted-foreground">Service-level target</dt>
              <dd className="font-medium tabular-nums">
                {formatPercent(explanation.service_level_target)}
              </dd>
            </div>
          )}
        </dl>
        <p className="text-xs text-muted-foreground border-t pt-2">
          Want the full derivation?{" "}
          <Link to="/methodology" className="text-primary underline underline-offset-2">
            See how it works
          </Link>
          .
        </p>
      </CardContent>
    </Card>
  );
}
