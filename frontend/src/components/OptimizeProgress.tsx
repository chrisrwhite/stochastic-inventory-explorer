import { Check, Loader2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { cn } from "../lib/utils";
import { useAppState } from "../state/AppState";

/**
 * Client-side per-stage progress indicator for the optimize call.
 *
 * The backend still returns a single JSON response, so we don't have real
 * per-phase progress. Instead each stage animates over its expected share of
 * the total wall-clock time. Stages appear on new lines as they start,
 * previous stages stay visible with a checkmark, the active stage animates.
 * When the response arrives (isLoading flips false), the whole component
 * unmounts, so we never claim 100% we haven't actually achieved.
 */
interface Phase {
  label: string;
  weight: number;
}

const PHASES: Phase[] = [
  { label: "Building policy grid", weight: 0.05 },
  { label: "Simulating candidate policies", weight: 0.65 },
  { label: "Evaluating recommended policy", weight: 0.15 },
  { label: "Comparing reference policies", weight: 0.15 },
];

const EXPECTED_MS = 1400;
const EASE_K = 2.0;
const OVERALL_CAP = 0.95;

type PhaseStatus = "pending" | "active" | "complete";

interface PhaseView {
  index: number;
  label: string;
  fraction: number;
  status: PhaseStatus;
}

function computePhases(overall: number): PhaseView[] {
  const cum: number[] = [];
  let acc = 0;
  for (const p of PHASES) {
    acc += p.weight;
    cum.push(acc);
  }
  return PHASES.map((p, i) => {
    const start = i === 0 ? 0 : cum[i - 1];
    const end = cum[i];
    const raw = (overall - start) / (end - start);
    const fraction = Math.max(0, Math.min(1, raw));
    let status: PhaseStatus = "active";
    if (overall < start) status = "pending";
    else if (fraction >= 0.999) status = "complete";
    return { index: i, label: p.label, fraction, status };
  });
}

export function OptimizeProgress({
  compact = false,
  className,
}: {
  compact?: boolean;
  className?: string;
}): JSX.Element {
  const { config } = useAppState();
  const [tMs, setTMs] = useState(0);
  const startRef = useRef<number>(performance.now());

  useEffect(() => {
    startRef.current = performance.now();
    let raf = 0;
    const tick = (): void => {
      setTMs(performance.now() - startRef.current);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);

  const raw = tMs / EXPECTED_MS;
  const overall = Math.min(1 - Math.exp(-raw * EASE_K), OVERALL_CAP);
  const phases = computePhases(overall).filter((p) => p.status !== "pending");

  return (
    <div className={cn("grid w-full", compact ? "gap-1.5" : "gap-2", className)}>
      {phases.map((p) => (
        <PhaseRow key={p.index} phase={p} compact={compact} />
      ))}
      {!compact && (
        <p className="mt-1 text-[10px] text-muted-foreground tabular-nums">
          Grid search: ~96 candidate policies × {config.nSimulations.toLocaleString()} Monte Carlo
          runs × {config.horizonDays} days
        </p>
      )}
    </div>
  );
}

function PhaseRow({ phase, compact }: { phase: PhaseView; compact: boolean }): JSX.Element {
  const pct = Math.round(phase.fraction * 100);
  const isDone = phase.status === "complete";
  return (
    <div
      className={cn(
        "grid w-full gap-1 motion-safe:animate-fade-slide-in",
        compact ? "text-[11px]" : "text-xs",
      )}
    >
      <div className="flex items-baseline justify-between gap-3">
        <span className="flex items-center gap-1.5 truncate">
          {isDone ? (
            <Check className="h-3.5 w-3.5 flex-shrink-0 text-primary" aria-hidden />
          ) : (
            <Loader2
              className="h-3.5 w-3.5 flex-shrink-0 animate-spin text-primary"
              aria-hidden
            />
          )}
          <span
            className={cn(
              "truncate",
              isDone ? "text-muted-foreground" : "font-medium text-foreground",
            )}
          >
            {phase.label}
            {isDone ? "" : "…"}
          </span>
        </span>
        <span className="tabular-nums text-muted-foreground">{pct}%</span>
      </div>
      <div
        className="h-1 w-full overflow-hidden rounded-full bg-secondary"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct}
        aria-label={phase.label}
      >
        <div
          className={cn(
            "h-full transition-[width] duration-150 ease-out",
            isDone ? "bg-primary/50" : "bg-primary",
          )}
          style={{ width: `${phase.fraction * 100}%` }}
        />
      </div>
    </div>
  );
}
