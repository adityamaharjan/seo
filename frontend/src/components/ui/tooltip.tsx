import * as React from "react"
import { cn } from "@/lib/utils"
import { Tooltip as TooltipPrimitive } from "radix-ui"

function TooltipProvider({
  delayDuration = 250,
  ...props
}: React.ComponentProps<typeof TooltipPrimitive.Provider>) {
  return (
    <TooltipPrimitive.Provider
      data-slot="tooltip-provider"
      delayDuration={delayDuration}
      {...props}
    />
  )
}

function Tooltip(props: React.ComponentProps<typeof TooltipPrimitive.Root>) {
  return <TooltipPrimitive.Root data-slot="tooltip" {...props} />
}

function TooltipTrigger(
  props: React.ComponentProps<typeof TooltipPrimitive.Trigger>
) {
  return <TooltipPrimitive.Trigger data-slot="tooltip-trigger" {...props} />
}

function TooltipContent({
  className,
  sideOffset = 6,
  children,
  ...props
}: React.ComponentProps<typeof TooltipPrimitive.Content>) {
  return (
    <TooltipPrimitive.Portal>
      <TooltipPrimitive.Content
        data-slot="tooltip-content"
        sideOffset={sideOffset}
        className={cn(
          "z-50 max-w-[280px] rounded-lg border border-border-strong bg-popover px-2.5 py-1.5 text-[12.5px] leading-snug text-popover-foreground shadow-[var(--shadow-raised)]",
          "motion-safe:data-[state=delayed-open]:animate-[content-in_120ms_ease-out]",
          className
        )}
        {...props}
      >
        {children}
      </TooltipPrimitive.Content>
    </TooltipPrimitive.Portal>
  )
}

export { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider }
