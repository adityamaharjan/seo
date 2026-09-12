/**
 * The states a report passes through before there is anything to read.
 *
 * Both report views poll the same way and fail the same way, so the waiting,
 * failed and loading screens live here rather than being written twice with
 * small differences between them.
 */
import type { ReactNode } from 'react'
import type { ReportStatus } from '../api/types'
import { Notice } from './Notice'
import { StatusPill } from './StatusPill'
import { Spinner } from './Spinner'
import { Panel } from './Page'
import { CenterNote } from './CenterNote'
import { Button } from '@/components/ui/button'

export { CenterNote }

/** Work that has been accepted and is still going. */
export function PendingPanel({
  title,
  url,
  status,
  timedOut,
  onRetry,
  children,
  stalledNoun,
}: {
  title: ReactNode
  url: string
  status: ReportStatus
  timedOut: boolean
  onRetry: () => void
  /** What is happening, in one sentence. */
  children: ReactNode
  /** "Still running." / "Still crawling." */
  stalledNoun: string
}) {
  return (
    <Panel className="mt-6">
      <h1 className="text-[22px] leading-tight font-semibold tracking-[-0.025em] break-words">
        {title}
      </h1>
      <p className="mt-1.5 text-[13.5px] break-all text-muted-foreground">{url}</p>
      <div className="mt-3.5">
        <StatusPill status={status} />
      </div>

      {timedOut ? (
        <Notice tone="warning" className="mt-5">
          <strong className="font-semibold">{stalledNoun}</strong> This is taking
          longer than expected. The worker may be busy or stopped.
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={onRetry}
            className="mt-2.5 flex"
          >
            Check again
          </Button>
        </Notice>
      ) : (
        /*
          Polite rather than assertive: this updates on its own while the reader
          is doing something else, and should not cut across them mid-sentence.
        */
        <p
          className="mt-5 flex items-center gap-2.5 text-[13.5px] text-muted-foreground"
          role="status"
          aria-live="polite"
        >
          <Spinner />
          {children}
        </p>
      )}
    </Panel>
  )
}

/** Work that came back with nothing usable. */
export function FailedPanel({
  title,
  url,
  status,
  error,
  fallback,
}: {
  title: ReactNode
  url: string
  status?: ReportStatus
  error?: string | null
  fallback: string
}) {
  return (
    <Panel className="mt-6">
      <h1 className="text-[22px] leading-tight font-semibold tracking-[-0.025em]">
        {title}
      </h1>
      <p className="mt-1.5 text-[13.5px] break-all text-muted-foreground">{url}</p>
      {status ? (
        <div className="mt-3.5">
          <StatusPill status={status} />
        </div>
      ) : null}
      <Notice tone="error" className="mt-5">
        {error || fallback}
      </Notice>
      <p className="mt-4 text-[13.5px] text-muted-foreground">
        Your daily quota unit was refunded, so this attempt cost you nothing.
      </p>
    </Panel>
  )
}

/** The whole view, before the first response has landed. */
