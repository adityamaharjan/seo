/**
 * Site audit: crawl many pages of one site and report what repeats.
 *
 * The sibling feature is the single-page audit, which takes target keywords.
 * This one takes a page budget instead: keyword placement is a judgement about
 * one specific page, not something to average across a crawl.
 */
import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { quotaApi, siteAuditsApi } from '../api/endpoints'
import type { Paginated, Quota, SiteAuditSummary } from '../api/types'
import { Notice } from '../components/Notice'
import { QuotaBar } from '../components/QuotaBar'
import { StatusPill } from '../components/StatusPill'
import { scoreColor } from '../components/ScoreRing'
import { formatDate, shortUrl } from '../lib/format'

const PAGE_SIZE = 10
/** Must stay within SITE_AUDIT_MAX_PAGES in app/core/config.py. */
const PAGE_BUDGETS = [5, 10, 25, 50]
const DEFAULT_BUDGET = 10

export function SiteAudit() {
  const navigate = useNavigate()
  const [url, setUrl] = useState('')
  const [maxPages, setMaxPages] = useState(DEFAULT_BUDGET)
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<unknown>(null)

  const [quota, setQuota] = useState<Quota | null>(null)
  const [history, setHistory] = useState<Paginated<SiteAuditSummary> | null>(null)
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
    siteAuditsApi
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
      const accepted = await siteAuditsApi.submit(normalizeUrl(target), maxPages)
      setUrl('')
      loadQuota()
      navigate(`/site-audit/${accepted.id}`)
    } catch (caught) {
      setSubmitError(caught)
      // A rejected submission may have been refunded; re-read the real number.
      loadQuota()
    } finally {
      setSubmitting(false)
    }
  }

  async function handleDelete(id: number) {
    if (!window.confirm('Delete this site audit? This cannot be undone.')) return
    try {
      await siteAuditsApi.remove(id)
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
        <div className="card-title">Audit a whole site</div>
        <p className="card-sub">
          Enter a site and we crawl it, starting from its sitemap and falling back
          to internal links. Every page gets the full audit, then the report ranks
          the problems by how many pages they touch, which is what separates a
          template bug from a one-off. One crawl costs one quota unit whatever the
          page count. Auditing one page instead?{' '}
          <Link to="/app">Run a page audit</Link>.
        </p>

        <Notice error={submitError} />
        {outOfQuota && !submitError ? (
          <Notice tone="warning">
            <strong>Daily limit reached.</strong> Your allowance resets at midnight UTC.
          </Notice>
        ) : null}

        <form onSubmit={handleSubmit} className="submit-row" noValidate>
          <div className="field">
            <label htmlFor="site-url" style={{ display: 'none' }}>
              Site URL
            </label>
            <input
              id="site-url"
              type="text"
              inputMode="url"
              placeholder="https://example.com"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              disabled={submitting}
              required
            />
          </div>
          <div className="field budget">
            <label htmlFor="max-pages" style={{ display: 'none' }}>
              Pages to crawl
            </label>
            <select
              id="max-pages"
              value={maxPages}
              onChange={(e) => setMaxPages(Number(e.target.value))}
              disabled={submitting}
            >
              {PAGE_BUDGETS.map((budget) => (
                <option key={budget} value={budget}>
                  Up to {budget} pages
                </option>
              ))}
            </select>
          </div>
          <button type="submit" className="btn" disabled={submitting || !url.trim()}>
            {submitting ? <span className="spinner" /> : 'Crawl site'}
          </button>
        </form>

        <div style={{ marginTop: 18 }}>
          <QuotaBar quota={quota} />
        </div>
      </div>

      <div className="card">
        <div className="section-head">
          <h2>Recent site audits</h2>
          {history ? <span className="quota-text">{history.total} total</span> : null}
        </div>

        <Notice error={listError} />

        {loadingList && !history ? (
          <div className="empty">
            <span className="spinner" /> Loading your site audits…
          </div>
        ) : history && history.items.length > 0 ? (
          <>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Site</th>
                    <th>Status</th>
                    <th className="right">Pages</th>
                    <th className="right">Avg score</th>
                    <th>Started</th>
                    <th aria-label="Actions" />
                  </tr>
                </thead>
                <tbody>
                  {history.items.map((audit) => (
                    <tr key={audit.id}>
                      <td>
                        <Link to={`/site-audit/${audit.id}`} className="cell-url">
                          <span className="primary">
                            {audit.domain || shortUrl(audit.start_url)}
                          </span>
                          <span className="secondary">
                            {shortUrl(audit.start_url)}
                            {audit.discovery_source ? ` · via ${audit.discovery_source}` : ''}
                          </span>
                        </Link>
                      </td>
                      <td>
                        <StatusPill status={audit.status} />
                      </td>
                      <td className="right">
                        {audit.status === 'done' ? (
                          <>
                            {audit.pages_crawled}
                            <span style={{ color: 'var(--muted)' }}>
                              {' '}
                              / {audit.max_pages}
                            </span>
                          </>
                        ) : (
                          <span style={{ color: 'var(--muted)' }}>—</span>
                        )}
                      </td>
                      <td className="right">
                        {audit.overall_score === null ? (
                          <span style={{ color: 'var(--muted)' }}>—</span>
                        ) : (
                          <strong style={{ color: scoreColor(audit.overall_score) }}>
                            {audit.overall_score}
                            {audit.overall_grade ? (
                              <span style={{ color: 'var(--muted)', fontWeight: 500 }}>
                                {' '}
                                {audit.overall_grade}
                              </span>
                            ) : null}
                          </strong>
                        )}
                      </td>
                      <td style={{ color: 'var(--muted)', whiteSpace: 'nowrap' }}>
                        {formatDate(audit.created_at)}
                      </td>
                      <td className="right">
                        <button
                          type="button"
                          className="btn danger"
                          onClick={() => handleDelete(audit.id)}
                          aria-label={`Delete site audit for ${audit.start_url}`}
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
            <h3>No site audits yet</h3>
            <p>Crawl a site above and it will show up here.</p>
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
