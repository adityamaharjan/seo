import * as React from "react"
import { cn } from "@/lib/utils"
import { Progress as ProgressPrimitive } from "radix-ui"

/**
 * A determinate meter.
 *
 * `indicatorClassName` exists because most meters in this app are coloured by
 * what they measure, and the colour belongs on the filled bar rather than on
 * the track the caller would otherwise be styling.
 */
function Progress({
  className,
  indicatorClassName,
  value,
  ...props
}: React.ComponentProps<typeof ProgressPrimitive.Root> & {
  indicatorClassName?: string
}) {
  return (
    <ProgressPrimitive.Root
      data-slot="progress"
      className={cn(
        "relative h-1.5 w-full overflow-hidden rounded-full bg-surface-2",
        className
      )}
      value={value}
      {...props}
    >
      <ProgressPrimitive.Indicator
        data-slot="progress-indicator"
        className={cn(
          "h-full w-full rounded-full bg-primary transition-transform duration-500 ease-out",
          indicatorClassName
        )}
        style={{ transform: `translateX(-${100 - (value ?? 0)}%)` }}
      />
    </ProgressPrimitive.Root>
  )
}

export { Progress }
