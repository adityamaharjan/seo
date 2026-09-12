/** Single-page report: polls until the worker finishes, then renders it. */
import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { analysesApi } from '../api/endpoints'
import type { ReportDetail } from '../api/types'
import { Notice } from '../components/Notice'
import { ReportBody } from '../components/ReportBody'
import { StatusPill } from '../components/StatusPill'

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

  const results = report?.results ?? null

  if (error) {
    return (
      <>
        <Link to="/app" className="back-link">
          ← Back to page audit
        </Link>
        <Notice error={error} />
      </>
    )
  }

  if (!report) {
    return (
      <div className="center-note">
        <span className="spinner" />
        <span>Loading report…</span>
      </div>
    )
  }

  const waiting = report.status === 'pending' || report.status === 'running'

  return (
    <>
      <Link to="/app" className="back-link">
        ← Back to page audit
      </Link>

      {waiting ? (
        <div className="card">
          <div className="report-head">
            <div className="meta">
              <h1>{report.title || report.url}</h1>
              <div className="url">{report.url}</div>
              <div style={{ marginTop: 12 }}>
                <StatusPill status={report.status} />
              </div>
            </div>
          </div>
          {timedOut ? (
            <Notice tone="warning">
              <strong>Still running.</strong> This is taking longer than expected. The
              worker may be busy or stopped.{' '}
              <button
                type="button"
                className="btn ghost"
                onClick={() => setReloadKey((k) => k + 1)}
              >
                Check again
              </button>
            </Notice>
          ) : (
            <p className="card-sub" style={{ marginTop: 18, marginBottom: 0 }}>
              <span className="spinner" /> Fetching the page and running every check.
              This usually takes a few seconds.
            </p>
          )}
        </div>
      ) : null}

      {report.status === 'failed' ? (
        <div className="card">
          <div className="report-head">
            <div className="meta">
              <h1>Analysis failed</h1>
              <div className="url">{report.url}</div>
              <div style={{ marginTop: 12 }}>
                <StatusPill status={report.status} />
              </div>
            </div>
          </div>
          <Notice tone="error">
            {report.error || 'The page could not be analyzed.'}
          </Notice>
          <p className="card-sub" style={{ marginBottom: 0 }}>
            Your daily quota unit was refunded, so this attempt cost you nothing.
          </p>
        </div>
      ) : null}

      {results && report.status === 'done' ? (
        <ReportBody
          results={results}
          targetKeywords={report.target_keywords}
          badge={<StatusPill status={report.status} />}
        />
      ) : null}
    </>
  )
}
