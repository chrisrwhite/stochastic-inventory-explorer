import * as SliderPrimitive from "@radix-ui/react-slider";
import { forwardRef, type ComponentPropsWithoutRef } from "react";
import { cn } from "../../lib/utils";

type SliderProps = ComponentPropsWithoutRef<typeof SliderPrimitive.Root>;

export const Slider = forwardRef<HTMLSpanElement, SliderProps>(
  ({ className, ...props }, ref) => (
    <SliderPrimitive.Root
      ref={ref}
      className={cn("relative flex w-full touch-none select-none items-center", className)}
      {...props}
    >
      <SliderPrimitive.Track className="relative h-2 w-full grow overflow-hidden rounded-full bg-secondary">
        <SliderPrimitive.Range className="absolute h-full bg-primary" />
      </SliderPrimitive.Track>
      <SliderPrimitive.Thumb className="block h-4 w-4 rounded-full border border-primary/50 bg-background shadow transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring" />
    </SliderPrimitive.Root>
  ),
);
Slider.displayName = "Slider";
