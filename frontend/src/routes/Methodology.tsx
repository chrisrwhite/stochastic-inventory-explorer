import "katex/dist/katex.min.css";
import { BlockMath, InlineMath } from "react-katex";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/Card";

export function Methodology(): JSX.Element {
  return (
    <div className="grid gap-4 max-w-3xl">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">How it works</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          The stochastic-optimization pipeline behind the recommended policy, with the equations,
          not just the words.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>The optimization problem</CardTitle>
        </CardHeader>
        <CardContent className="text-sm space-y-3 leading-relaxed">
          <p>
            The optimizer minimizes the expected total cost across simulated futures, subject to a
            reliability constraint you pick:
          </p>
          <div className="overflow-x-auto py-1">
            <BlockMath math={String.raw`\min_{\text{policy}\;\pi} \; \mathbb{E}\bigl[C_{\text{hold}}(\pi) + C_{\text{order}}(\pi) + C_{\text{stockout}}(\pi)\bigr]`} />
          </div>
          <div className="overflow-x-auto py-1">
            <BlockMath math={String.raw`\text{s.t.} \quad \Pr(\text{stockout on any day} \mid \pi) \le 1 - \alpha`} />
          </div>
          <p>
            where <InlineMath math={String.raw`\alpha`} /> is your target service level. The
            expectation <InlineMath math={String.raw`\mathbb{E}[\cdot]`} /> is approximated as the
            sample mean over <InlineMath math={String.raw`N = 2{,}000`} /> independent Monte-Carlo
            trajectories, a textbook <em>Sample Average Approximation</em>:
          </p>
          <div className="overflow-x-auto py-1">
            <BlockMath math={String.raw`\hat{\mathbb{E}}[C(\pi)] \; = \; \frac{1}{N} \sum_{k=1}^{N} C^{(k)}(\pi)`} />
          </div>
          <p className="text-xs text-muted-foreground">
            Instead of continuous optimization, we discretize: build a grid of ~240 candidate
            policies (sized from lead-time demand quantiles), score each with the sample mean above,
            and keep the cheapest one that satisfies the constraint.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Reorder point and safety stock</CardTitle>
        </CardHeader>
        <CardContent className="text-sm space-y-3 leading-relaxed">
          <p>
            A reorder point is the on-hand + on-order inventory level below which we place a
            replenishment order. It has two ingredients: the expected demand while we wait for the
            replenishment (the <em>expected lead-time demand</em>), and a buffer to absorb the
            uncertainty in that demand and in the lead time itself (the <em>safety stock</em>):
          </p>
          <div className="overflow-x-auto py-1">
            <BlockMath math={String.raw`r \; = \; \underbrace{\mathbb{E}[D \cdot L]}_{\text{expected lead-time demand}} \; + \; \underbrace{SS}_{\text{safety stock}}`} />
          </div>
          <p>
            Classical textbook formulas assume <InlineMath math={String.raw`D`} /> and{" "}
            <InlineMath math={String.raw`L`} /> are Normal and set{" "}
            <InlineMath math={String.raw`SS = z_\alpha \cdot \sigma_{DL}`} />. This app instead
            estimates the buffer <em>directly from simulation</em>, so it works cleanly on the
            sparse, bursty, and heavy-tailed demand you get from real POS data.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Policies</CardTitle>
        </CardHeader>
        <CardContent className="text-sm space-y-3 leading-relaxed">
          <p>
            <strong>Fixed order size (r, Q):</strong> whenever the inventory position falls to or
            below <InlineMath math={String.raw`r`} />, place an order of{" "}
            <InlineMath math={String.raw`Q`} /> units. Simple and popular with fixed pack sizes.
          </p>
          <p>
            <strong>Order up to target (s, S):</strong> whenever the inventory position falls to or
            below <InlineMath math={String.raw`s`} />, order enough to bring it up to{" "}
            <InlineMath math={String.raw`S`} />. Slightly more responsive to spikes.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Demand and lead-time uncertainty</CardTitle>
        </CardHeader>
        <CardContent className="text-sm space-y-3 leading-relaxed">
          <p>
            Each simulated future draws a random demand sequence and a random lead time for every
            order. Demand can be sampled by <em>empirical bootstrap</em> (uniform resample of real
            history, recommended), <em>seasonal bootstrap</em> (resample within day-of-week
            buckets), <em>Poisson</em>, or <em>negative binomial</em> (for bursty, overdispersed
            demand where variance exceeds the mean).
          </p>
          <p>
            Lead times can be <em>fixed</em>, <em>empirical</em> (resample from provided samples),
            <em>triangular</em>, <em>lognormal</em>, or <em>shifted Poisson</em>.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Metrics</CardTitle>
        </CardHeader>
        <CardContent className="text-sm space-y-3 leading-relaxed">
          <p>
            <strong>Cycle service level</strong> is the probability of finishing a day without a
            stockout, <InlineMath math={String.raw`1 - \Pr(\text{any stockout day})`} />.{" "}
            <strong>Fill rate</strong> is the fraction of demand fulfilled from stock on hand. Fill
            rate is usually higher than cycle service level because a stockout day still fulfills
            most of that day's demand.
          </p>
          <p>
            <strong>CVaR of stockout cost</strong> is the average cost across the worst{" "}
            <InlineMath math={String.raw`(1-\alpha)`} /> tail of simulations. It's a risk metric
            that captures rare but expensive stockouts a plain expected-cost objective would miss:
          </p>
          <div className="overflow-x-auto py-1">
            <BlockMath math={String.raw`\mathrm{CVaR}_\alpha(L) \; = \; \mathbb{E}\bigl[\, L \mid L \ge \mathrm{VaR}_\alpha(L)\,\bigr]`} />
          </div>
          <p className="text-xs text-muted-foreground">
            We use <InlineMath math={String.raw`\alpha = 0.95`} />, so this is the mean of the
            worst 5% of simulated per-scenario stockout costs.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Selection under a constraint</CardTitle>
        </CardHeader>
        <CardContent className="text-sm space-y-3 leading-relaxed">
          <p>
            After every candidate policy has been scored, we return the one that minimizes expected
            total cost subject to the chosen constraint (service level, stockout risk, or CVaR
            budget). If no policy is feasible under your target, the app falls back to the policy
            that gets closest, a compromise you should notice in the results text.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
