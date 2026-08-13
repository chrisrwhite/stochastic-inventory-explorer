import { HelpCircle } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { cn } from "../lib/utils";

interface ExplainProps {
  label: string;
  children: ReactNode;
  className?: string;
}

/**
 * Inline info-icon that opens a small popover with a plain-language
 * explanation of a jargon term. Click to toggle, escape or click-away to
 * close.
 */
export function Explain({ label, children, className }: ExplainProps): JSX.Element {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent): void => {
      if (!containerRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent): void => {
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("mousedown", onClick);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("mousedown", onClick);
      window.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <span ref={containerRef} className={cn("relative inline-flex align-middle", className)}>
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          setOpen((o) => !o);
        }}
        className="inline-flex h-4 w-4 items-center justify-center rounded-full text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        aria-label={`What is ${label}?`}
        aria-expanded={open}
      >
        <HelpCircle className="h-3.5 w-3.5" />
      </button>
      {open && (
        <span
          role="tooltip"
          className="absolute left-full top-full z-40 mt-1 ml-1 w-64 rounded-md border bg-card p-3 text-xs leading-relaxed text-card-foreground shadow-lg"
        >
          <span className="mb-1 block text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
            {label}
          </span>
          <span className="block">{children}</span>
        </span>
      )}
    </span>
  );
}
