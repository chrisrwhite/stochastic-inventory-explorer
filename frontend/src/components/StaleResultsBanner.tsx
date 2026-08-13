import { useOptimize } from "../state/useOptimize";
import { OptimizeProgress } from "./OptimizeProgress";
import { Button } from "./ui/Button";

export function StaleResultsBanner(): JSX.Element | null {
  const { isStale, isLoading, error, run } = useOptimize();

  if (isLoading) {
    return (
      <div className="grid gap-2 rounded-md border border-primary/40 bg-primary/5 px-3 py-3">
        <OptimizeProgress compact />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
        <span>Optimization failed: {error}</span>
        <Button size="sm" variant="outline" onClick={run}>
          Retry
        </Button>
      </div>
    );
  }

  if (isStale) {
    return (
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-sm text-amber-800 dark:text-amber-200">
        <span>
          Inputs changed since the last optimization. Results below reflect the previous run.
        </span>
        <Button size="sm" onClick={run}>
          Re-optimize
        </Button>
      </div>
    );
  }

  return null;
}
