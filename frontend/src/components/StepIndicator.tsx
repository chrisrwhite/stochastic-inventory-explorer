import { cn } from "../lib/utils";

export interface Step {
  n: number;
  label: string;
  anchor: string;
}

export function StepIndicator({
  steps,
  activeAnchor,
}: {
  steps: Step[];
  activeAnchor: string | null;
}): JSX.Element {
  return (
    <ol className="grid gap-2">
      {steps.map((step) => {
        const active = step.anchor === activeAnchor;
        return (
          <li key={step.anchor}>
            <a
              href={`#${step.anchor}`}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
                active
                  ? "bg-primary/10 text-foreground"
                  : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
              )}
            >
              <span
                className={cn(
                  "flex h-6 w-6 items-center justify-center rounded-full border text-xs font-medium tabular-nums",
                  active
                    ? "border-primary bg-primary text-primary-foreground"
                    : "border-muted-foreground/30 text-muted-foreground",
                )}
              >
                {step.n}
              </span>
              <span>{step.label}</span>
            </a>
          </li>
        );
      })}
    </ol>
  );
}
