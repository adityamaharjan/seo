import type { Quota } from '../api/types'
import { untilReset } from '../lib/format'
import { Progress } from '@/components/ui/progress'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

/**
 * How much of today's allowance is left.
 *
 * The number leads and the bar follows, rather than the other way round: people
 * want the count, and the bar is there to make "nearly out" visible at a glance.
 * It turns red only when the allowance is actually spent, so the colour means
 * one thing.
 */
export function QuotaBar({ quota, className }: { quota: Quota | null; className?: string }) {
  if (!quota) {
    return (
      <div className={cn('flex items-center gap-3', className)}>
        <Skeleton className="h-1.5 flex-1 rounded-full" />
        <Skeleton className="h-4 w-40" />
      </div>
    )
  }

  const used = Math.min(quota.used_today, quota.daily_limit)
  const percent = quota.daily_limit > 0 ? (used / quota.daily_limit) * 100 : 0
  const spent = quota.remaining_today <= 0
  const resetsAt = `${quota.day_reset_date}T00:00:00Z`

  return (
    <div className={cn('flex flex-wrap items-center gap-x-4 gap-y-2', className)}>
      <Progress
        value={percent}
        aria-label={`${used} of ${quota.daily_limit} daily analyses used`}
        className="min-w-[150px] flex-1"
        indicatorClassName={spent ? 'bg-crit' : undefined}
      />
      <p className="text-[13px] whitespace-nowrap text-muted-foreground">
        <span className="font-semibold tabular-nums text-foreground">
          {quota.remaining_today}
        </span>{' '}
        of <span className="tabular-nums">{quota.daily_limit}</span> analyses left today
        {spent ? ` · resets ${untilReset(resetsAt)}` : ''}
      </p>
    </div>
  )
}
