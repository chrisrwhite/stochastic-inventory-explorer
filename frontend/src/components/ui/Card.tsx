import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "../../lib/utils";

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
}

export function Card({ className, children, ...rest }: CardProps): JSX.Element {
  return (
    <div
      className={cn(
        "rounded-lg border bg-card text-card-foreground shadow-sm",
        className,
      )}
      {...rest}
    >
      {children}
    </div>
  );
}

export function CardHeader({ className, children, ...rest }: CardProps): JSX.Element {
  return (
    <div className={cn("p-5 pb-3", className)} {...rest}>
      {children}
    </div>
  );
}

export function CardTitle({ className, children, ...rest }: CardProps): JSX.Element {
  return (
    <h3 className={cn("text-lg font-semibold tracking-tight", className)} {...rest}>
      {children}
    </h3>
  );
}

export function CardDescription({ className, children, ...rest }: CardProps): JSX.Element {
  return (
    <p className={cn("text-sm text-muted-foreground mt-1", className)} {...rest}>
      {children}
    </p>
  );
}

export function CardContent({ className, children, ...rest }: CardProps): JSX.Element {
  return (
    <div className={cn("px-5 pb-5", className)} {...rest}>
      {children}
    </div>
  );
}
