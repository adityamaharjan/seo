import * as React from "react"
import { cn } from "@/lib/utils"

/**
 * A loading placeholder shaped like the content it stands in for.
 *
 * The sweep is a child rather than a background animation so it can be dropped
 * for anyone who has asked their system to reduce motion, leaving a plain
 * resting block instead of a pulsing one.
 */
function Skeleton({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="skeleton"
      className={cn(
        "relative overflow-hidden rounded-md bg-surface-2",
        className
      )}
      {...props}
    >
      <span
        aria-hidden="true"
        className="absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-black/[0.045] to-transparent motion-safe:animate-[shimmer_1.6s_infinite] dark:via-white/[0.06]"
      />
    </div>
  )
}

export { Skeleton }
