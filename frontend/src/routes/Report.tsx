/** Single-page report: polls until the worker finishes, then renders it. */
import { useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { analysesApi } from '../api/endpoints'
import type { ReportDetail } from '../api/types'
import { Notice } from '../components/Notice'
import { ReportBody } from '../components/ReportBody'
import { StatusPill } from '../components/StatusPill'
import { BackLink } from '../components/Page'
import { CenterNote, FailedPanel, PendingPanel } from '../components/ReportStates'

/** Roughly two minutes of polling before we stop and let the user retry. */
const MAX_POLLS = 50

function pollDelay(attempt: number): number {
  if (attempt < 4) return 1000
  if (attempt < 12) return 2000
  return 3000
}

export function Report() {
  const params = useParams<{ id: string }>()
  const id = Number(params.id)

  const [report, setReport] = useState<ReportDetail | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [timedOut, setTimedOut] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)
  const timer = useRef<number | undefined>(undefined)

  useEffect(() => {
    if (!Number.isInteger(id) || id <= 0) {
      setError(new Error('That report id is not valid.'))
      return
    }

    const controller = new AbortController()
    let cancelled = false
    let attempts = 0
    setTimedOut(false)

    async function tick() {
      try {
        const data = await analysesApi.get(id, controller.signal)
        if (cancelled) return
        setReport(data)
        setError(null)

        if (data.status === 'pending' || data.status === 'running') {
          attempts += 1
          if (attempts > MAX_POLLS) {
            setTimedOut(true)
            return
          }
          timer.current = window.setTimeout(tick, pollDelay(attempts))
        }
      } catch (caught) {
        if (cancelled || (caught as Error)?.name === 'AbortError') return
        setError(caught)
      }
    }

    tick()
    return () => {
      cancelled = true
      controller.abort()
      window.clearTimeout(timer.current)
    }
  }, [id, reloadKey])

  const back = <BackLink to="/app">Back to page audit</BackLink>

  if (error) {
    return (
      <>
        {back}
        <Notice error={error} className="mt-4" />
      </>
    )
  }

  if (!report) {
    return <CenterNote>Loading report…</CenterNote>
  }

  const results = report.results
  const waiting = report.status === 'pending' || report.status === 'running'

  return (
    <>
      {back}

      {waiting ? (
        <PendingPanel
          title={report.title || report.url}
          url={report.url}
          status={report.status}
          timedOut={timedOut}
          onRetry={() => setReloadKey((k) => k + 1)}
          stalledNoun="Still running."
        >
          Fetching the page and running every check. This usually takes a few
          seconds.
        </PendingPanel>
      ) : null}

      {report.status === 'failed' ? (
        <FailedPanel
          title="Analysis failed"
          url={report.url}
          status={report.status}
          error={report.error}
          fallback="The page could not be analyzed."
        />
      ) : null}

      {results && report.status === 'done' ? (
        <div className="mt-6">
          <ReportBody
            results={results}
            targetKeywords={report.target_keywords}
            badge={<StatusPill status={report.status} />}
          />
        </div>
      ) : null}
    </>
  )
}
