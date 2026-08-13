declare module "react-katex" {
  import type { CSSProperties, ReactNode } from "react";

  interface MathProps {
    math: string;
    children?: ReactNode;
    errorColor?: string;
    renderError?: (error: Error) => ReactNode;
    settings?: Record<string, unknown>;
    as?: string;
    className?: string;
    style?: CSSProperties;
  }

  export const InlineMath: (props: MathProps) => JSX.Element;
  export const BlockMath: (props: MathProps) => JSX.Element;
}
