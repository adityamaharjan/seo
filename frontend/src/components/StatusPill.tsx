import type { CheckStatus, ReportStatus } from '../api/types'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

/** Work that has not settled yet, so its dot keeps moving. */
const ANIMATED: ReportStatus[] = ['pending', 'running']

const VARIANT: Record<string, 'good' | 'warning' | 'critical' | 'info' | 'neutral'> = {
  good: 'good',
  done: 'good',
  warning: 'warning',
  critical: 'critical',
  failed: 'critical',
  info: 'info',
  pending: 'neutral',
  running: 'info',
}

/**
 * One word saying where something stands.
 *
 * Every status gets a dot as well as a tint, because the tint is the only thing
 * separating "warning" from "critical" otherwise and hue alone is not a signal
 * everyone receives. Running work pulses; finished work does not.
 */
export function StatusPill({
  status,
  className,
}: {
  status: ReportStatus | CheckStatus
  className?: string
}) {
  const animated = ANIMATED.includes(status as ReportStatus)
  return (
    <Badge
      variant={VARIANT[status] ?? 'neutral'}
      className={cn('gap-1.5 px-2 py-0.5 text-[11.5px] font-semibold capitalize', className)}
    >
      <span
        aria-hidden="true"
        className={cn(
          'size-1.5 rounded-full bg-current',
          animated && 'motion-safe:animate-[pulse-dot_1.4s_ease-in-out_infinite]',
        )}
      />
      {status}
    </Badge>
  )
}
