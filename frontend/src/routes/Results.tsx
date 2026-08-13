import { Link, useSearchParams } from "react-router-dom";
import { InventoryPathFanChart } from "../components/InventoryPathFanChart";
import { OptimizeProgress } from "../components/OptimizeProgress";
import { PolicyFrontierChart } from "../components/PolicyFrontierChart";
import { PolicyStoryLine } from "../components/PolicyStoryLine";
import { PolicySummaryCards } from "../components/PolicySummaryCards";
import { ScenarioCompare } from "../components/ScenarioCompare";
import { ServiceLevelSlider } from "../components/ServiceLevelSlider";
import { StaleResultsBanner } from "../components/StaleResultsBanner";
import { Button } from "../components/ui/Button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/Tabs";
import { WhyThisPolicyPanel } from "../components/WhyThisPolicyPanel";
import { useOptimize } from "../state/useOptimize";

const TAB_KEY = "tab";
const TAB_VALUES = ["tradeoff", "futures", "alternatives"] as const;
type TabValue = (typeof TAB_VALUES)[number];

function ComputedStamp(): JSX.Element | null {
  const { lastElapsedMs, data, isLoading } = useOptimize();
  if (isLoading) return null;
  if (!data || lastElapsedMs === null) return null;
  return (
    <span className="text-xs text-muted-foreground tabular-nums">
      Computed in {(lastElapsedMs / 1000).toFixed(2)}s · {data.metrics.n_sims.toLocaleString()} simulations · {data.metrics.horizon_days} days
    </span>
  );
}

export function Results(): JSX.Element {
  const { data, hasValidConfig, hasRun, isLoading, error, run } = useOptimize();
  const [searchParams, setSearchParams] = useSearchParams();

  const rawTab = searchParams.get(TAB_KEY);
  const active: TabValue = TAB_VALUES.includes(rawTab as TabValue)
    ? (rawTab as TabValue)
    : "tradeoff";

  function setTab(next: string): void {
    const params = new URLSearchParams(searchParams);
    params.set(TAB_KEY, next);
    setSearchParams(params, { replace: true });
  }

  if (!hasValidConfig) {
    return (
      <div className="rounded-md border bg-card p-6 text-sm text-muted-foreground">
        Pick a scenario on the <Link to="/setup" className="underline">Set up</Link> page before
        viewing results.
      </div>
    );
  }

  if (!hasRun && !error) {
    if (isLoading) {
      return (
        <div className="grid gap-3 rounded-md border bg-card p-6">
          <div className="text-sm font-medium text-foreground">Running your first optimization…</div>
          <OptimizeProgress />
        </div>
      );
    }
    return (
      <div className="flex flex-col gap-3 rounded-md border bg-card p-6 text-sm text-muted-foreground">
        <p>
          You haven't run the optimization yet. Optimization only runs when you click the button -
          nothing happens automatically as you tweak inputs.
        </p>
        <div className="flex gap-2">
          <Button onClick={run}>Optimize now</Button>
          <Link
            to="/setup"
            className="inline-flex h-9 items-center justify-center rounded-md border border-border bg-transparent px-4 text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground"
          >
            Back to Set up
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="grid gap-4">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">Results</h2>
          <ComputedStamp />
        </div>
      </div>
      <StaleResultsBanner />
      <ServiceLevelSlider />
      {data && (
        <>
          <PolicyStoryLine
            policy={data.recommended_policy}
            metrics={data.metrics}
            serviceLevelTarget={data.explanation.service_level_target}
          />
          <PolicySummaryCards policy={data.recommended_policy} metrics={data.metrics} />
          <Tabs value={active} onValueChange={setTab}>
            <TabsList>
              <TabsTrigger value="tradeoff">Cost vs reliability</TabsTrigger>
              <TabsTrigger value="futures">Possible futures</TabsTrigger>
              <TabsTrigger value="alternatives">Alternatives</TabsTrigger>
            </TabsList>
            <TabsContent value="tradeoff">
              <div className="grid gap-4 lg:grid-cols-2">
                <PolicyFrontierChart
                  frontier={data.frontier}
                  comparisons={data.comparison_policies}
                  serviceLevelTarget={data.explanation.service_level_target}
                />
                <WhyThisPolicyPanel explanation={data.explanation} />
              </div>
            </TabsContent>
            <TabsContent value="futures">
              <InventoryPathFanChart
                simulation={data.simulation}
                recommended={data.recommended_policy}
              />
            </TabsContent>
            <TabsContent value="alternatives">
              <ScenarioCompare
                comparisons={data.comparison_policies}
                recommended={data.recommended_policy}
                recommendedMetrics={data.metrics}
              />
            </TabsContent>
          </Tabs>
        </>
      )}
    </div>
  );
}
