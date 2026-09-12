import type { Quota } from '../api/types'
import { untilReset } from '../lib/format'

export function QuotaBar({ quota }: { quota: Quota | null }) {
  if (!quota) {
    return <div className="quota-text">Checking your daily allowance…</div>
  }

  const used = Math.min(quota.used_today, quota.daily_limit)
  const percent = quota.daily_limit > 0 ? (used / quota.daily_limit) * 100 : 0
  const spent = quota.remaining_today <= 0
  const resetsAt = `${quota.day_reset_date}T00:00:00Z`

  return (
    <div className="quota">
      <div className={`quota-bar${spent ? ' spent' : ''}`}>
        <span style={{ width: `${percent}%` }} />
      </div>
      <div className="quota-text">
        <strong>{quota.remaining_today}</strong> of {quota.daily_limit} analyses left today
        {spent ? ` · resets ${untilReset(resetsAt)}` : ''}
      </div>
    </div>
  )
}
