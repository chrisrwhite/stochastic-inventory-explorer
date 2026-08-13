import { ChevronDown } from "lucide-react";
import { useState, type ReactNode } from "react";
import { cn } from "../lib/utils";

interface AdvancedPanelProps {
  label?: string;
  description?: string;
  defaultOpen?: boolean;
  className?: string;
  children: ReactNode;
}

/**
 * Collapsible progressive-disclosure section. Used to keep power-user knobs
 * (demand model choice, exotic lead-time distributions, raw cost fields,
 * advanced metrics) reachable without cluttering the default happy path.
 */
export function AdvancedPanel({
  label = "Advanced",
  description,
  defaultOpen = false,
  className,
  children,
}: AdvancedPanelProps): JSX.Element {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className={cn("rounded-md border bg-card/50", className)}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        aria-expanded={open}
      >
        <span className="flex flex-col">
          <span className="font-medium">{label}</span>
          {description && (
            <span className="text-xs text-muted-foreground/80">{description}</span>
          )}
        </span>
        <ChevronDown
          className={cn(
            "h-4 w-4 shrink-0 transition-transform",
            open && "rotate-180",
          )}
        />
      </button>
      {open && <div className="border-t px-3 py-3">{children}</div>}
    </div>
  );
}
