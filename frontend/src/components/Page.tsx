/**
 * The layout vocabulary every app view is built from.
 *
 * The old views stacked bordered, tinted cards: each section was a box, and a
 * report was eight boxes in a column. That chrome cost a lot of contrast and
 * bought no structure, because when everything is boxed the boxes stop meaning
 * anything. Here structure comes from a heading, a hairline and space, and a
 * border is kept for the two things that genuinely sit on top of the page: a
 * form you fill in, and a row you can click into.
 */
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Skeleton } from '@/components/ui/skeleton'

/** The title block at the top of a view. */
export function PageHeader({
  title,
  description,
  actions,
  className,
}: {
  title: ReactNode
  description?: ReactNode
  actions?: ReactNode
  className?: string
}) {
  return (
    <div className={cn('flex flex-wrap items-start justify-between gap-x-6 gap-y-4', className)}>
      <div className="min-w-0 flex-1">
        <h1 className="text-[26px] leading-tight font-semibold tracking-[-0.03em] text-balance">
          {title}
        </h1>
        {description ? (
          <p className="mt-2 max-w-[58ch] text-[14.5px] leading-relaxed text-muted-foreground text-pretty">
            {description}
          </p>
        ) : null}
      </div>
      {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
    </div>
  )
}

/**
 * One band of a view: a heading, an optional note on the right, a rule, content.
 * Sections are spaced apart generously so the rule reads as a divider rather
 * than as the top edge of yet another box.
 */
export function Section({
  title,
  meta,
  children,
  className,
  headingId,
}: {
  title: ReactNode
  meta?: ReactNode
  children: ReactNode
  className?: string
  headingId?: string
}) {
  return (
    <section className={cn('mt-14 first:mt-0', className)} aria-labelledby={headingId}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h2
          id={headingId}
          className="text-[15px] font-semibold tracking-[-0.01em]"
        >
          {title}
        </h2>
        {meta ? (
          <span className="text-[13px] text-muted-foreground">{meta}</span>
        ) : null}
      </div>
      <div className="mt-3 h-px w-full bg-border" />
      <div className="mt-6">{children}</div>
    </section>
  )
}

/**
 * A bordered surface, for the places elevation still means something: a form,
 * or a panel that is a distinct object on the page rather than a run of content.
 */
export function Panel({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <div className={cn('rounded-xl border border-border bg-surface p-5 sm:p-6', className)}>
      {children}
    </div>
  )
}

/** A measured reading: small label above, number below, numerals aligned. */
export function Stat({
  label,
  value,
  tone,
}: {
  label: ReactNode
  value: ReactNode
  tone?: string
}) {
  return (
    <div>
      <dt className="text-[11px] font-semibold tracking-[0.06em] text-muted-foreground uppercase">
        {label}
      </dt>
      <dd
        className={cn(
          'mt-1 text-[19px] leading-none font-semibold tabular-nums tracking-[-0.025em]',
          tone,
        )}
      >
        {value}
      </dd>
    </div>
  )
}

export function StatGrid({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <dl
      className={cn(
        'grid grid-cols-2 gap-x-6 gap-y-6 sm:grid-cols-4 lg:grid-cols-7',
        className,
      )}
    >
      {children}
    </dl>
  )
}

/** Nothing to show yet, and what to do about it. */
export function EmptyState({
  icon,
  title,
  children,
  action,
}: {
  icon?: ReactNode
  title: ReactNode
  children?: ReactNode
  action?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center rounded-xl border border-dashed border-border-strong px-6 py-14 text-center">
      {icon ? (
        <div className="mb-4 grid size-10 place-items-center rounded-full bg-surface-2 text-muted-foreground">
          {icon}
        </div>
      ) : null}
      <h3 className="text-[15px] font-semibold">{title}</h3>
      {children ? (
        <p className="mt-1.5 max-w-[42ch] text-[13.5px] text-muted-foreground text-pretty">
          {children}
        </p>
      ) : null}
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  )
}

/** A link back up the hierarchy, sized to sit above a page title. */
export function BackLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link
      to={to}
      className="group -ml-1 inline-flex items-center gap-1.5 rounded-md px-1 py-1 text-[13px] text-muted-foreground transition-colors hover:text-foreground"
    >
      <ArrowLeft className="size-3.5 transition-transform duration-200 group-hover:-translate-x-0.5" />
      {children}
    </Link>
  )
}

/**
 * Placeholder rows standing in for a table that has not arrived.
 *
 * Hidden from assistive tech: the shapes mean nothing read aloud, and the view
 * announces its real loading state in copy alongside this.
 */
export function TableSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-3" aria-hidden="true">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="flex items-center gap-4 border-b border-border pb-3">
          <div className="flex-1 space-y-1.5">
            <Skeleton className="h-3.5 w-1/3" />
            <Skeleton className="h-3 w-1/2" />
          </div>
          <Skeleton className="h-5 w-16 rounded-full" />
          <Skeleton className="h-3.5 w-8" />
        </div>
      ))}
    </div>
  )
}
