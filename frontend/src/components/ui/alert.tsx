import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

/**
 * An inline message about the thing the user just did.
 *
 * Tone carries meaning, so each variant pairs its tint with a matching left
 * spine and icon colour rather than relying on the tint alone, which at 12%
 * opacity is not a reliable signal on its own and carries nothing at all for
 * anyone who cannot distinguish the hues.
 */
const alertVariants = cva(
  "relative grid w-full grid-cols-[auto_1fr] items-start gap-x-3 rounded-lg border border-l-[3px] px-3.5 py-3 text-[13.5px] leading-relaxed has-[>svg]:gap-x-3 [&>svg]:mt-[3px] [&>svg]:size-4 [&>svg]:shrink-0",
  {
    variants: {
      variant: {
        info: "border-primary/25 border-l-primary bg-accent-soft text-foreground [&>svg]:text-accent-on-tint",
        error:
          "border-crit/30 border-l-crit bg-crit-soft text-foreground [&>svg]:text-crit",
        warning:
          "border-warn/35 border-l-warn bg-warn-soft text-foreground [&>svg]:text-warn",
        success:
          "border-good/30 border-l-good bg-good-soft text-foreground [&>svg]:text-good",
      },
    },
    defaultVariants: { variant: "info" },
  }
)

function Alert({
  className,
  variant,
  ...props
}: React.ComponentProps<"div"> & VariantProps<typeof alertVariants>) {
  return (
    <div
      data-slot="alert"
      data-variant={variant}
      className={cn(alertVariants({ variant }), className)}
      {...props}
    />
  )
}

function AlertTitle({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="alert-title"
      className={cn("col-start-2 font-semibold", className)}
      {...props}
    />
  )
}

function AlertDescription({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="alert-description"
      className={cn("col-start-2 [&_p]:leading-relaxed", className)}
      {...props}
    />
  )
}

export { Alert, AlertTitle, AlertDescription, alertVariants }
