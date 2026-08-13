import { ArrowDown } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AdvancedPanel } from "../components/AdvancedPanel";
import { CostAssumptionEditor } from "../components/CostAssumptionEditor";
import { CostBreakdownPreview } from "../components/CostBreakdownPreview";
import { CostSummary } from "../components/CostSummary";
import { DemandHistoryChart } from "../components/DemandHistoryChart";
import { DemandModelSelector } from "../components/DemandModelSelector";
import { Explain } from "../components/Explain";
import { HowItWorksPanel } from "../components/HowItWorksPanel";
import { LeadTimeDistributionChart } from "../components/LeadTimeDistributionChart";
import { LeadTimeEditor } from "../components/LeadTimeEditor";
import { OptimizeProgress } from "../components/OptimizeProgress";
import { ScenarioSelector } from "../components/ScenarioSelector";
import { ServiceLevelSlider } from "../components/ServiceLevelSlider";
import { StepIndicator, type Step } from "../components/StepIndicator";
import { Button } from "../components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/Card";
import { cn } from "../lib/utils";
import { useAppState } from "../state/AppState";
import { useOptimize } from "../state/useOptimize";

const STEPS: Step[] = [
  { n: 1, label: "Pick a scenario", anchor: "step-scenario" },
  { n: 2, label: "Lead time", anchor: "step-lead-time" },
  { n: 3, label: "Costs", anchor: "step-costs" },
  { n: 4, label: "Reliability target", anchor: "step-target" },
];

function useActiveAnchor(anchors: string[]): string | null {
  const [active, setActive] = useState<string | null>(anchors[0] ?? null);
  useEffect(() => {
    const observers: IntersectionObserver[] = [];
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
        if (visible) setActive(visible.target.id);
      },
      { rootMargin: "-30% 0px -50% 0px", threshold: 0.05 },
    );
    for (const id of anchors) {
      const el = document.getElementById(id);
      if (el) observer.observe(el);
    }
    observers.push(observer);
    return () => {
      for (const o of observers) o.disconnect();
    };
  }, [anchors]);
  return active;
}

function Hero(): JSX.Element {
  return (
    <Card>
      <CardHeader>
        <div className="text-xs font-semibold uppercase tracking-wide text-primary">
          Stochastic optimization · Monte Carlo · SAA
        </div>
        <CardTitle className="text-xl">
          Optimize an inventory policy across thousands of possible futures.
        </CardTitle>
      </CardHeader>
      <CardContent className="grid gap-4 text-sm leading-relaxed">
        <p>
          Instead of picking a reorder policy from a single demand forecast, this app defines the
          problem <em>over thousands of simulated futures</em> and returns the policy with the best
          expected outcome across all of them. That's the core idea behind stochastic optimization.
        </p>
        <div className="grid gap-2">
          <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            What you'll learn by playing with it
          </div>
          <ul className="grid gap-1.5 text-sm">
            <li className="flex gap-2">
              <span aria-hidden className="text-primary">→</span>
              <span>
                <span className="font-medium">What "service level" actually costs.</span> Pushing
                from 95% to 99% reliability rarely costs just a little more. Usually it costs a
                lot more inventory.
              </span>
            </li>
            <li className="flex gap-2">
              <span aria-hidden className="text-primary">→</span>
              <span>
                <span className="font-medium">Why safety stock exists.</span> Variability in
                lead time drives stockout risk more than average demand does.
              </span>
            </li>
            <li className="flex gap-2">
              <span aria-hidden className="text-primary">→</span>
              <span>
                <span className="font-medium">How to trust a model's output.</span> Every input has
                an inline visualization; every result comes with an alternative-policies table.
              </span>
            </li>
          </ul>
        </div>
        <div className="flex flex-wrap items-center gap-3 border-t pt-3">
          <a
            href="#how-it-works"
            className="inline-flex items-center gap-1.5 text-sm font-medium text-primary hover:underline underline-offset-4"
          >
            New here? See how it works
            <ArrowDown className="h-3.5 w-3.5" />
          </a>
          <span className="text-xs text-muted-foreground">
            3 real POS scenarios drawn from Walmart (M5) and UCI Online Retail (UK).
          </span>
        </div>
        <p className="text-xs text-muted-foreground border-t pt-3">
          <span className="font-medium text-foreground">Demand histories are real.</span>{" "}
          Cost assumptions are illustrative starting values, and each scenario prefills sensible
          defaults you can edit.
        </p>
      </CardContent>
    </Card>
  );
}

function StepSection({
  id,
  index,
  title,
  subtitle,
  children,
}: {
  id: string;
  index: number;
  title: string;
  subtitle: string;
  children: React.ReactNode;
}): JSX.Element {
  return (
    <section id={id} className="scroll-mt-24 grid gap-3">
      <div className="flex items-baseline gap-3">
        <span className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-primary-foreground text-sm font-semibold tabular-nums">
          {index}
        </span>
        <div>
          <h3 className="text-lg font-semibold tracking-tight">{title}</h3>
          <p className="text-sm text-muted-foreground">{subtitle}</p>
        </div>
      </div>
      <div className="pl-11">{children}</div>
    </section>
  );
}

export function Setup(): JSX.Element {
  const navigate = useNavigate();
  const { config } = useAppState();
  const { hasValidConfig, hasRun, isStale, isLoading, run } = useOptimize();
  const activeAnchor = useActiveAnchor(STEPS.map((s) => s.anchor));

  const needsRun = !hasRun || isStale;
  const cta = isLoading
    ? "Optimizing…"
    : !hasRun
      ? "Optimize policy →"
      : isStale
        ? "Re-optimize →"
        : "See results →";

  function handleCta(): void {
    if (!hasValidConfig || isLoading) return;
    if (needsRun) run();
    navigate("/results");
  }

  return (
    <div className="grid gap-6 md:grid-cols-[220px,1fr]">
      <aside className="hidden md:block">
        <div className="sticky top-24">
          <StepIndicator steps={STEPS} activeAnchor={activeAnchor} />
        </div>
      </aside>

      <div className="grid gap-6 min-w-0">
        <Hero />

        <HowItWorksPanel />

        <StepSection
          id="step-scenario"
          index={1}
          title="Pick a scenario"
          subtitle="Three real POS scenarios, each from an open retail dataset. Each card shows a live sparkline."
        >
          <div className="grid gap-4">
            <ScenarioSelector />
            <DemandHistoryChart />
            <DemandModelSelector />
          </div>
        </StepSection>

        <StepSection
          id="step-lead-time"
          index={2}
          title="Lead time"
          subtitle="How long between placing and receiving an order. Pick a preset or go Custom."
        >
          <div className="grid gap-4 lg:grid-cols-2">
            <LeadTimeEditor />
            <LeadTimeDistributionChart />
          </div>
        </StepSection>

        <StepSection
          id="step-costs"
          index={3}
          title="Costs"
          subtitle="What you pay to hold inventory, place orders, and miss demand."
        >
          <div className="grid gap-4">
            <div className="grid gap-4 lg:grid-cols-2">
              <CostSummary />
              <CostBreakdownPreview />
            </div>
            <AdvancedPanel
              label="Edit cost assumptions"
              description="Change any of the 6 cost inputs. Prefilled from the scenario."
            >
              <CostAssumptionEditor />
            </AdvancedPanel>
          </div>
        </StepSection>

        <StepSection
          id="step-target"
          index={4}
          title="Reliability target"
          subtitle="How often are you willing to run out? The optimizer picks the cheapest policy that hits this bar."
        >
          <ServiceLevelSlider />
        </StepSection>

        <div
          className={cn(
            "sticky bottom-4 z-20 flex items-center gap-3 rounded-lg border bg-card/95 px-4 py-3 shadow-lg backdrop-blur",
          )}
        >
          <div className="min-w-0 flex-1 text-sm">
            {isLoading ? (
              <OptimizeProgress compact />
            ) : (
              <span className="inline-flex items-center gap-1 text-muted-foreground">
                {!hasValidConfig && "Pick a scenario above to enable optimization."}
                {hasValidConfig && !hasRun && "Ready to optimize. Nothing runs until you click."}
                {hasRun && isStale && "Inputs changed. Click Re-optimize to refresh results."}
                {hasRun && !isStale && "Results are up to date for these inputs."}
                <Explain label="What does Optimize do?">
                  <strong>Simulation-based grid search.</strong> The app builds ~96 candidate
                  policies (varying reorder point × order-up-to), runs {" "}
                  {config.nSimulations.toLocaleString()} Monte Carlo simulations of {" "}
                  {config.horizonDays} days for each, then picks the cheapest one whose simulated
                  reliability meets your target. It's an optimization solved by brute-force
                  enumeration plus Monte Carlo, no gradient solver.
                </Explain>
              </span>
            )}
          </div>
          <Button
            size="lg"
            disabled={!hasValidConfig || isLoading}
            onClick={handleCta}
            className={cn(hasRun && isStale && !isLoading && "animate-pulse-subtle")}
          >
            {cta}
          </Button>
        </div>
      </div>
    </div>
  );
}
