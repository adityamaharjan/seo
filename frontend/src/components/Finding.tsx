/**
 * A single finding: one check on a page, or one issue repeating across a crawl.
 *
 * Status is carried by a coloured spine down the left edge rather than by
 * tinting the whole row. A tinted row makes a list of thirty checks look like a
 * heat map and makes the text on it harder to read; a spine is just as scannable
 * down a column and leaves the copy on the page's own ground. The status word
 * itself is always present as a badge, so the colour is reinforcement rather
 * than the only signal.
 */
import type { ReactNode } from 'react'
import type { CheckStatus } from '../api/types'
import { cn } from '@/lib/utils'

const SPINE: Record<CheckStatus, string> = {
  good: 'border-l-good',
  warning: 'border-l-warn',
  critical: 'border-l-crit',
  info: 'border-l-info',
}

export function FindingList({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <div className={cn('overflow-hidden rounded-xl border border-border', className)}>
      {children}
    </div>
  )
}

export function Finding({
  status,
  label,
  badges,
  message,
  trailing,
  children,
}: {
  status: CheckStatus
  label: ReactNode
  badges?: ReactNode
  message?: ReactNode
  /** The number at the right edge: a check's score, or an affected-page count. */
  trailing?: ReactNode
  children?: ReactNode
}) {
  return (
    <div
      className={cn(
        'flex items-start gap-4 border-b border-l-[3px] border-border px-4 py-3.5 last:border-b-0',
        SPINE[status],
      )}
    >
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
          <span className="text-[14px] font-semibold">{label}</span>
          {badges}
        </div>
        {message ? (
          <p className="mt-1 text-[13.5px] leading-relaxed break-words text-muted-foreground">
            {message}
          </p>
        ) : null}
        {children}
      </div>
      {trailing !== undefined && trailing !== null ? (
        <div className="shrink-0 pt-0.5 text-[13.5px] font-semibold tabular-nums whitespace-nowrap text-muted-foreground">
          {trailing}
        </div>
      ) : null}
    </div>
  )
}

/** The raw value a check looked at, shown as evidence. */
export function FindingDetail({ children }: { children: ReactNode }) {
  return (
    <p className="mt-2.5 rounded-lg border border-border bg-code px-2.5 py-1.5 font-mono text-[12px] leading-relaxed break-words text-muted-foreground">
      {children}
    </p>
  )
}

/** The specific change to make. Every finding that has one shows it. */
export function FindingFix({ children }: { children: ReactNode }) {
  return (
    <div className="mt-2.5 border-l-2 border-primary/50 pl-3">
      <span className="text-[10.5px] font-semibold tracking-[0.08em] text-accent-on-tint uppercase">
        Fix
      </span>
      <p className="mt-0.5 text-[13.5px] leading-relaxed break-words">{children}</p>
    </div>
  )
}
