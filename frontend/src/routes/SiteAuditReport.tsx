/**
 * Site audit report.
 *
 * The useful output of a crawl is not an average score, it is *which problems
 * repeat*. One page with a short title is a task; forty pages with short titles
 * is a template bug. So issues ranked by how many pages they affect lead the
 * page, and the per-page table sits underneath for drilling in.
 */
import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { siteAuditsApi } from '../api/endpoints'
import type { SiteAuditDetail, SiteIssue } from '../api/types'
import { Notice } from '../components/Notice'
import { ScoreRing, scoreColor } from '../components/ScoreRing'
import { StatusPill } from '../components/StatusPill'
import { categoryLabel, formatDate, formatMs, shortUrl } from '../lib/format'

/** A crawl of 50 pages can run for minutes, so polling runs longer than a report's. */
const MAX_POLLS = 200

function pollDelay(attempt: number): number {
  if (attempt < 4) return 1500
  if (attempt < 20) return 3000
  return 5000
}

export function SiteAuditReport() {
  const params = useParams<{ id: string }>()
  const id = Number(params.id)

  const [audit, setAudit] = useState<SiteAuditDetail | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [timedOut, setTimedOut] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)
  const timer = useRef<number | undefined>(undefined)

  useEffect(() => {
    if (!Number.isInteger(id) || id <= 0) {
      setError(new Error('That site audit id is not valid.'))
      return
    }

    const controller = new AbortController()
    let cancelled = false
    let attempts = 0
    setTimedOut(false)

    async function tick() {
      try {
        const data = await siteAuditsApi.get(id, controller.signal)
        if (cancelled) return
        setAudit(data)
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

  if (error) {
    return (
      <>
        <Link to="/site-audit" className="back-link">
          ← Back to site audits
        </Link>
        <Notice error={error} />
      </>
    )
  }

  if (!audit) {
    return (
      <div className="center-note">
        <span className="spinner" />
        <span>Loading site audit…</span>
      </div>
    )
  }

  const results = audit.results
  const waiting = audit.status === 'pending' || audit.status === 'running'

  return (
    <>
      <Link to="/site-audit" className="back-link">
        ← Back to site audits
      </Link>

      {waiting ? (
        <div className="card">
          <div className="report-head">
            <div className="meta">
              <h1>{audit.domain || audit.start_url}</h1>
              <div className="url">{audit.start_url}</div>
              <div style={{ marginTop: 12 }}>
                <StatusPill status={audit.status} />
              </div>
            </div>
          </div>
          {timedOut ? (
            <Notice tone="warning">
              <strong>Still crawling.</strong> This is taking longer than expected.
              The worker may be busy or stopped.{' '}
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
              <span className="spinner" /> Crawling up to {audit.max_pages} pages and
              auditing each one. A large site can take a few minutes.
            </p>
          )}
        </div>
      ) : null}

      {audit.status === 'failed' ? (
        <div className="card">
          <div className="report-head">
            <div className="meta">
              <h1>Site audit failed</h1>
              <div className="url">{audit.start_url}</div>
              <div style={{ marginTop: 12 }}>
                <StatusPill status={audit.status} />
              </div>
            </div>
          </div>
          <Notice tone="error">{audit.error || 'The site could not be crawled.'}</Notice>
          <p className="card-sub" style={{ marginBottom: 0 }}>
            Your daily quota unit was refunded, so this attempt cost you nothing.
          </p>
        </div>
      ) : null}

      {results && audit.status === 'done' ? (
        <>
          <div className="card">
            <div className="report-head">
              <ScoreRing score={results.overall_score} grade={results.overall_grade} />
              <div className="meta">
                <h1>{results.domain}</h1>
                <div className="url">
                  <a href={audit.start_url} target="_blank" rel="noreferrer nofollow">
                    {audit.start_url}
                  </a>
                </div>
                <div style={{ marginTop: 10, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  <StatusPill status={audit.status} />
                  <span className="pill info">
                    {results.pages_crawled} pages via {results.discovery_source}
                  </span>
                </div>
                <div className="issue-summary">
                  <span className="issue-stat critical">
                    <span className="n">{results.issue_counts.critical}</span> critical
                  </span>
                  <span className="issue-stat warning">
                    <span className="n">{results.issue_counts.warning}</span> warnings
                  </span>
                  <span className="issue-stat good">
                    <span className="n">{results.issue_counts.good}</span> passed
                  </span>
                </div>
                <div className="url" style={{ marginTop: 10 }}>
                  Crawled {formatDate(results.generated_at)}
                </div>
              </div>
            </div>

            {results.pages_failed > 0 ? (
              <Notice tone="warning">
                <strong>
                  {results.pages_failed} page{results.pages_failed === 1 ? '' : 's'} could
                  not be fetched.
                </strong>{' '}
                They are excluded from the averages below and listed at the bottom.
              </Notice>
            ) : null}

            <div className="stat-grid">
              <div className="stat">
                <div className="label">Average score</div>
                <div className="value">{results.overall_score}</div>
              </div>
              <div className="stat">
                <div className="label">Best page</div>
                <div className="value">{results.score_spread.max}</div>
              </div>
              <div className="stat">
                <div className="label">Median</div>
                <div className="value">{results.score_spread.median}</div>
              </div>
              <div className="stat">
                <div className="label">Worst page</div>
                <div className="value">{results.score_spread.min}</div>
              </div>
              <div className="stat">
                <div className="label">Pages crawled</div>
                <div className="value">{results.pages_crawled}</div>
              </div>
              <div className="stat">
                <div className="label">Failed</div>
                <div className="value">{results.pages_failed}</div>
              </div>
            </div>
          </div>

          {results.capped_pages.length > 0 ? (
            <Notice tone="warning">
              <strong>
                {results.capped_pages.length} page
                {results.capped_pages.length === 1 ? '' : 's'} cannot be indexed.
              </strong>{' '}
              Their scores are capped, which drags the site average down. Fix those
              first: {results.capped_pages.slice(0, 3).map((p) => shortUrl(p.url)).join(', ')}
              {results.capped_pages.length > 3 ? ' and others' : ''}.
            </Notice>
          ) : null}

          <div className="card">
            <div className="section-head">
              <h2>Issues across the site</h2>
              <span className="quota-text">Ranked by pages affected</span>
            </div>
            {results.top_issues.length === 0 ? (
              <div className="empty">No warnings or critical issues on any page.</div>
            ) : (
              <div className="issue-list">
                {results.top_issues.map((issue) => (
                  <IssueRow key={issue.id} issue={issue} />
                ))}
              </div>
            )}
          </div>

          <div className="card">
            <div className="section-head">
              <h2>Category averages</h2>
              <span className="quota-text">Across {results.pages_crawled} pages</span>
            </div>
            <div className="category-grid">
              {results.category_scores.map((category) => (
                <div className="category" key={category.category}>
                  <div className="top">
                    <span className="name">{categoryLabel(category.category)}</span>
                    <span className="score" style={{ color: scoreColor(category.score) }}>
                      {category.score}
                    </span>
                  </div>
                  <div className="weight">
                    Grade {category.grade} · weight {Math.round(category.weight * 100)}%
                  </div>
                  <div className="meter">
                    <span
                      style={{
                        width: `${category.score}%`,
                        background: scoreColor(category.score),
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="card">
            <div className="section-head">
              <h2>Pages</h2>
              <span className="quota-text">Worst first</span>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Page</th>
                    <th className="right">Score</th>
                    <th className="right">Critical</th>
                    <th className="right">Warnings</th>
                    <th className="right">Load</th>
                  </tr>
                </thead>
                <tbody>
                  {[...audit.pages]
                    .sort(
                      (a, b) =>
                        (a.overall_score ?? -1) - (b.overall_score ?? -1),
                    )
                    .map((page) => (
                      <tr key={page.id}>
                        <td>
                          <Link
                            to={`/site-audit/${audit.id}/page/${page.id}`}
                            className="cell-url"
                          >
                            <span className="primary">
                              {page.title || shortUrl(page.final_url || page.url)}
                            </span>
                            <span className="secondary">
                              {shortUrl(page.final_url || page.url)}
                            </span>
                          </Link>
                        </td>
                        <td className="right">
                          {page.overall_score === null ? (
                            <span className="pill critical">failed</span>
                          ) : (
                            <strong style={{ color: scoreColor(page.overall_score) }}>
                              {page.overall_score}
                              <span style={{ color: 'var(--muted)', fontWeight: 500 }}>
                                {' '}
                                {page.overall_grade}
                              </span>
                            </strong>
                          )}
                        </td>
                        <td className="right">{page.issue_counts?.critical ?? '—'}</td>
                        <td className="right">{page.issue_counts?.warning ?? '—'}</td>
                        <td className="right" style={{ whiteSpace: 'nowrap' }}>
                          {formatMs(page.load_time_ms)}
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </div>

          {results.errors.length > 0 ? (
            <div className="card">
              <div className="section-head">
                <h2>Pages that could not be fetched</h2>
              </div>
              <div className="check-list">
                {results.errors.map((failure) => (
                  <div className="check critical" key={failure.url}>
                    <div className="bar" />
                    <div className="body">
                      <div className="head">
                        <span className="label">{shortUrl(failure.url)}</span>
                      </div>
                      <div className="message">{failure.error || 'Fetch failed.'}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </>
      ) : null}
    </>
  )
}

function IssueRow({ issue }: { issue: SiteIssue }) {
  const share = issue.total_pages ? (issue.affected_pages / issue.total_pages) * 100 : 0
  return (
    <div className={`check ${issue.status}`}>
      <div className="bar" />
      <div className="body">
        <div className="head">
          <span className="label">{issue.label}</span>
          <StatusPill status={issue.status} />
          {issue.sitewide ? <span className="pill warning">site-wide</span> : null}
        </div>
        <div className="message">
          Affects {issue.affected_pages} of {issue.total_pages} pages in{' '}
          {categoryLabel(issue.category)}.
        </div>
        <div className="meter" style={{ margin: '8px 0' }}>
          <span
            style={{
              width: `${share}%`,
              background: issue.status === 'critical' ? 'var(--critical)' : 'var(--warning)',
            }}
          />
        </div>
        {issue.recommendation ? (
          <div className="rec">
            <b>Fix:</b> {issue.recommendation}
          </div>
        ) : null}
        <div className="detail">
          e.g. {issue.example_urls.slice(0, 3).map((u) => shortUrl(u, 40)).join(' · ')}
        </div>
      </div>
      <div className="score">{issue.affected_pages}</div>
    </div>
  )
}
