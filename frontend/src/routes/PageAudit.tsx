/**
 * Single-page audit: one URL, optionally judged against target keywords.
 *
 * The sibling feature is the site audit, which crawls many pages and takes no
 * keywords. Keeping them apart is deliberate: keyword targeting depends on what
 * the submitter typed, and only makes sense aimed at one specific page.
 */
import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { analysesApi, quotaApi } from '../api/endpoints'
import type { Paginated, Quota, ReportSummary } from '../api/types'
import { Notice } from '../components/Notice'
import { QuotaBar } from '../components/QuotaBar'
import { StatusPill } from '../components/StatusPill'
import { scoreColor } from '../components/ScoreRing'
import { formatDate, shortUrl } from '../lib/format'

const PAGE_SIZE = 10
/** Mirrors MAX_TARGET_KEYWORDS in app/seo/constants.py. */
const MAX_TARGET_KEYWORDS = 5

/** Comma-separated input -> deduplicated keyword list, capped like the API. */
function parseKeywords(raw: string): string[] {
  const seen = new Set<string>()
  const keywords: string[] = []
  for (const part of raw.split(',')) {
    const keyword = part.replace(/\s+/g, ' ').trim()
    if (!keyword || seen.has(keyword.toLowerCase())) continue
    seen.add(keyword.toLowerCase())
    keywords.push(keyword)
  }
  return keywords.slice(0, MAX_TARGET_KEYWORDS)
}

export function PageAudit() {
  const navigate = useNavigate()
  // The landing page's hero field hands the URL over as ?url=, surviving the
  // sign-up round trip, so the visitor does not have to type it again.
  const [params] = useSearchParams()
  const [url, setUrl] = useState(() => params.get('url') ?? '')
  const [keywordInput, setKeywordInput] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<unknown>(null)

  const [quota, setQuota] = useState<Quota | null>(null)
  const [history, setHistory] = useState<Paginated<ReportSummary> | null>(null)
  const [page, setPage] = useState(1)
  const [listError, setListError] = useState<unknown>(null)
  const [loadingList, setLoadingList] = useState(true)

  const loadQuota = useCallback(() => {
    quotaApi
      .status()
      .then(setQuota)
      .catch(() => setQuota(null))
  }, [])

  const loadHistory = useCallback((targetPage: number) => {
    setLoadingList(true)
    analysesApi
      .list(targetPage, PAGE_SIZE)
      .then((data) => {
        setHistory(data)
        setListError(null)
      })
      .catch(setListError)
      .finally(() => setLoadingList(false))
  }, [])

  useEffect(() => {
    loadQuota()
  }, [loadQuota])

  useEffect(() => {
    loadHistory(page)
  }, [loadHistory, page])

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const target = url.trim()
    if (!target) return

    setSubmitting(true)
    setSubmitError(null)
    try {
      const accepted = await analysesApi.submit(
        normalizeUrl(target),
        parseKeywords(keywordInput),
      )
      setUrl('')
      setKeywordInput('')
      loadQuota()
      navigate(`/report/${accepted.id}`)
    } catch (caught) {
      setSubmitError(caught)
      // A rejected submission may have been refunded; re-read the real number.
      loadQuota()
    } finally {
      setSubmitting(false)
    }
  }

  async function handleDelete(id: number) {
    if (!window.confirm('Delete this report? This cannot be undone.')) return
    try {
      await analysesApi.remove(id)
      loadHistory(page)
    } catch (caught) {
      setListError(caught)
    }
  }

  const outOfQuota = quota !== null && quota.remaining_today <= 0
  const totalPages = history ? Math.max(1, Math.ceil(history.total / history.page_size)) : 1

  return (
    <>
      <div className="card">
        <div className="card-title">Audit a single page</div>
        <p className="card-sub">
          Enter any public URL. The report covers meta, content, structure, links,
          indexability, performance, security and mobile. Name up to{' '}
          {MAX_TARGET_KEYWORDS} keywords to also see where each one appears on the
          page, scored separately so it never moves the page score. Auditing a
          whole site instead? <Link to="/site-audit">Run a site audit</Link>.
        </p>

        <Notice error={submitError} />
        {outOfQuota && !submitError ? (
          <Notice tone="warning">
            <strong>Daily limit reached.</strong> Your allowance resets at midnight UTC.
          </Notice>
        ) : null}

        <form onSubmit={handleSubmit} className="submit-row" noValidate>
          <div className="field">
            <label htmlFor="url" className="sr-only" style={{ display: 'none' }}>
              URL
            </label>
            <input
              id="url"
              type="text"
              inputMode="url"
              placeholder="https://example.com"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              disabled={submitting}
              required
            />
          </div>
          <div className="field">
            <label htmlFor="keywords" className="sr-only" style={{ display: 'none' }}>
              Target keywords
            </label>
            <input
              id="keywords"
              type="text"
              placeholder="Target keywords (optional, comma separated)"
              value={keywordInput}
              onChange={(e) => setKeywordInput(e.target.value)}
              disabled={submitting}
            />
          </div>
          <button type="submit" className="btn" disabled={submitting || !url.trim()}>
            {submitting ? <span className="spinner" /> : 'Analyze'}
          </button>
        </form>

        <div style={{ marginTop: 18 }}>
          <QuotaBar quota={quota} />
        </div>
      </div>

      <div className="card">
        <div className="section-head">
          <h2>Recent page reports</h2>
          {history ? (
            <span className="quota-text">
              {history.total} total
            </span>
          ) : null}
        </div>

        <Notice error={listError} />

        {loadingList && !history ? (
          <div className="empty">
            <span className="spinner" /> Loading your history…
          </div>
        ) : history && history.items.length > 0 ? (
          <>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Page</th>
                    <th>Status</th>
                    <th className="right">Score</th>
                    <th>Analyzed</th>
                    <th aria-label="Actions" />
                  </tr>
                </thead>
                <tbody>
                  {history.items.map((report) => (
                    <tr key={report.id}>
                      <td>
                        <Link to={`/report/${report.id}`} className="cell-url">
                          <span className="primary">{report.title || shortUrl(report.url)}</span>
                          <span className="secondary">
                            {shortUrl(report.url)}
                            {report.target_keywords?.length
                              ? ` · ${report.target_keywords.join(', ')}`
                              : ''}
                          </span>
                        </Link>
                      </td>
                      <td>
                        <StatusPill status={report.status} />
                      </td>
                      <td className="right">
                        {report.overall_score === null ? (
                          <span style={{ color: 'var(--muted)' }}>—</span>
                        ) : (
                          <strong style={{ color: scoreColor(report.overall_score) }}>
                            {report.overall_score}
                            {report.overall_grade ? (
                              <span style={{ color: 'var(--muted)', fontWeight: 500 }}>
                                {' '}
                                {report.overall_grade}
                              </span>
                            ) : null}
                          </strong>
                        )}
                      </td>
                      <td style={{ color: 'var(--muted)', whiteSpace: 'nowrap' }}>
                        {formatDate(report.created_at)}
                      </td>
                      <td className="right">
                        <button
                          type="button"
                          className="btn danger"
                          onClick={() => handleDelete(report.id)}
                          aria-label={`Delete report for ${report.url}`}
                        >
                          Delete
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {totalPages > 1 ? (
              <div className="pager">
                <span>
                  Page {history.page} of {totalPages}
                </span>
                <div className="controls">
                  <button
                    type="button"
                    className="btn secondary"
                    disabled={page <= 1 || loadingList}
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                  >
                    Previous
                  </button>
                  <button
                    type="button"
                    className="btn secondary"
                    disabled={page >= totalPages || loadingList}
                    onClick={() => setPage((p) => p + 1)}
                  >
                    Next
                  </button>
                </div>
              </div>
            ) : null}
          </>
        ) : (
          <div className="empty">
            <h3>No page reports yet</h3>
            <p>Audit a page above and it will show up here.</p>
          </div>
        )}
      </div>
    </>
  )
}

/** Let people type "example.com" without the scheme. */
function normalizeUrl(value: string): string {
  return /^https?:\/\//i.test(value) ? value : `https://${value}`
}
