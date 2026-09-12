import type { CheckStatus, ReportStatus } from '../api/types'

const ANIMATED: ReportStatus[] = ['pending', 'running']

export function StatusPill({ status }: { status: ReportStatus | CheckStatus }) {
  const animated = ANIMATED.includes(status as ReportStatus)
  return (
    <span className={`pill ${status}`}>
      {animated ? <span className="blip" /> : null}
      {status}
    </span>
  )
}
