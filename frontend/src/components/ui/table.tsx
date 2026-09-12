import * as React from "react"
import { cn } from "@/lib/utils"

/**
 * A quiet data table.
 *
 * The header is a row of small-caps labels over a hairline rather than a filled
 * band: in a view that is mostly table, a tinted header stripe competes with
 * the data for attention and the data is the point. The horizontal scroll lives
 * on a wrapper so a wide table scrolls inside its own bounds instead of pushing
 * the page sideways on a phone.
 */
function Table({ className, ...props }: React.ComponentProps<"table">) {
  return (
    <div
      data-slot="table-container"
      className="relative w-full overflow-x-auto overscroll-x-contain"
    >
      <table
        data-slot="table"
        className={cn("w-full caption-bottom border-collapse text-[14px]", className)}
        {...props}
      />
    </div>
  )
}

function TableHeader({ className, ...props }: React.ComponentProps<"thead">) {
  return <thead data-slot="table-header" className={cn(className)} {...props} />
}

function TableBody({ className, ...props }: React.ComponentProps<"tbody">) {
  return <tbody data-slot="table-body" className={cn(className)} {...props} />
}

function TableRow({ className, ...props }: React.ComponentProps<"tr">) {
  return (
    <tr
      data-slot="table-row"
      className={cn(
        "border-b border-border transition-colors last:border-0 hover:bg-surface data-[state=selected]:bg-surface",
        className
      )}
      {...props}
    />
  )
}

function TableHead({ className, ...props }: React.ComponentProps<"th">) {
  return (
    <th
      data-slot="table-head"
      className={cn(
        "border-b border-border-strong px-3 py-2.5 text-left align-middle text-[11px] font-semibold tracking-[0.06em] whitespace-nowrap text-muted-foreground uppercase first:pl-0 last:pr-0",
        className
      )}
      {...props}
    />
  )
}

function TableCell({ className, ...props }: React.ComponentProps<"td">) {
  return (
    <td
      data-slot="table-cell"
      className={cn(
        "px-3 py-3 align-middle first:pl-0 last:pr-0",
        className
      )}
      {...props}
    />
  )
}

function TableCaption({ className, ...props }: React.ComponentProps<"caption">) {
  return (
    <caption
      data-slot="table-caption"
      className={cn("mt-4 text-[13px] text-muted-foreground", className)}
      {...props}
    />
  )
}

export {
  Table,
  TableHeader,
  TableBody,
  TableHead,
  TableRow,
  TableCell,
  TableCaption,
}
