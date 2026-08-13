import { ArrowRight, ChevronDown, Dice5, LineChart, Target, Trophy } from "lucide-react";
import { useEffect, useState } from "react";
import "katex/dist/katex.min.css";
import { BlockMath } from "react-katex";
import { cn } from "../lib/utils";

const STORAGE_KEY = "howItWorks.open.v1";

const STEPS = [
  {
    icon: Target,
    title: "Propose policies",
    body: "Build a grid of candidate reorder rules. Each pair of (reorder point, order quantity) is one policy that tells us when and how much to order.",
  },
  {
    icon: Dice5,
    title: "Simulate futures",
    body: "For each candidate policy, roll 2,000 random 180-day futures. Demand is resampled from real history; lead times are drawn from their distribution.",
  },
  {
    icon: LineChart,
    title: "Score every policy",
    body: "Average the total cost across all 2,000 futures. Also compute reliability and the worst-case tail (CVaR) so we know what could go wrong.",
  },
  {
    icon: Trophy,
    title: "Pick the winner",
    body: "Keep the cheapest policy that still meets your reliability target. The full tradeoff surface (the frontier) is returned too.",
  },
] as const;

const CONCEPT_CARDS = [
  {
    term: "Policy",
    plain: "A rule: 'when inventory drops to r, order Q more' or 'top up to S.' The optimizer searches over ~240 candidate policies.",
  },
  {
    term: "Simulation",
    plain: "One 'what could happen' story: random demand + random lead times unrolling day by day. We run 2,000 of them per policy.",
  },
  {
    term: "Frontier",
    plain: "The scatter of every candidate on a cost vs reliability plot. Its edge is the best you can do, and anything below it is strictly worse.",
  },
] as const;

export function HowItWorksPanel(): JSX.Element {
  const [open, setOpen] = useState<boolean>(() => {
    if (typeof window === "undefined") return true;
    return window.localStorage.getItem(STORAGE_KEY) !== "closed";
  });

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(STORAGE_KEY, open ? "open" : "closed");
  }, [open]);

  return (
    <section
      id="how-it-works"
      className="scroll-mt-24 rounded-lg border bg-card text-card-foreground shadow-sm"
    >
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-3 px-5 py-4 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-lg"
      >
        <div>
          <h3 className="text-lg font-semibold tracking-tight">How it works</h3>
          <p className="text-sm text-muted-foreground mt-1">
            The four-step loop the optimizer runs behind the scenes. About a 60-second read.
          </p>
        </div>
        <ChevronDown
          className={cn(
            "h-5 w-5 shrink-0 text-muted-foreground transition-transform",
            open && "rotate-180",
          )}
        />
      </button>

      {open && (
        <div className="grid gap-6 border-t px-5 py-5">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 lg:gap-2">
            {STEPS.map((step, i) => (
              <div key={step.title} className="relative">
                <div className="grid gap-2 rounded-md border bg-card/60 p-3 h-full">
                  <div className="flex items-center gap-2">
                    <span className="flex h-7 w-7 items-center justify-center rounded-full bg-primary/10 text-primary">
                      <step.icon className="h-4 w-4" />
                    </span>
                    <span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground tabular-nums">
                      Step {i + 1}
                    </span>
                  </div>
                  <div className="text-sm font-medium leading-tight">{step.title}</div>
                  <p className="text-xs text-muted-foreground leading-relaxed">{step.body}</p>
                </div>
                {i < STEPS.length - 1 && (
                  <ArrowRight
                    aria-hidden
                    className="hidden lg:block absolute top-1/2 -right-2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
                  />
                )}
              </div>
            ))}
          </div>

          <div className="grid gap-3 rounded-md border bg-muted/30 p-4">
            <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              The objective, in one line
            </div>
            <div className="overflow-x-auto text-sm">
              <BlockMath math={String.raw`\min_{\text{policy}} \; \mathbb{E}\bigl[C_{\text{hold}} + C_{\text{order}} + C_{\text{stockout}}\bigr] \quad \text{s.t.} \quad \Pr(\text{stockout day}) \le 1 - \alpha`} />
            </div>
            <p className="text-xs text-muted-foreground leading-relaxed">
              Minimize the <em>expected</em> total cost across all simulated futures, subject to your
              reliability target <span className="whitespace-nowrap">α</span>. The expectation
              <span className="whitespace-nowrap"> 𝔼[·]</span> is approximated as the sample mean
              across 2,000 Monte-Carlo trajectories, a technique called{" "}
              <em>Sample Average Approximation</em>.
            </p>
          </div>

          <div className="grid gap-3 sm:grid-cols-3">
            {CONCEPT_CARDS.map((c) => (
              <div key={c.term} className="grid gap-1.5 rounded-md border p-3">
                <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  {c.term}
                </div>
                <p className="text-xs leading-relaxed">{c.plain}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
