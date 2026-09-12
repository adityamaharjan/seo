/**
 * One page from a site audit, rendered with the full single-page report view.
 *
 * The crawl stores the identical payload a single-page report produces, so this
 * reuses ReportBody rather than showing a reduced version of the same analysis.
 */
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { siteAuditsApi } from '../api/endpoints'
import type { SiteAuditPageDetail } from '../api/types'
import { Notice } from '../components/Notice'
import { ReportBody } from '../components/ReportBody'

export function SiteAuditPage() {
  const params = useParams<{ auditId: string; pageId: string }>()
  const auditId = Number(params.auditId)
  const pageId = Number(params.pageId)

  const [page, setPage] = useState<SiteAuditPageDetail | null>(null)
  const [error, setError] = useState<unknown>(null)

  useEffect(() => {
    if (!Number.isInteger(auditId) || !Number.isInteger(pageId)) {
      setError(new Error('That page id is not valid.'))
      return
    }
    let cancelled = false
    siteAuditsApi
      .getPage(auditId, pageId)
      .then((data) => {
        if (!cancelled) setPage(data)
      })
      .catch((caught) => {
        if (!cancelled) setError(caught)
      })
    return () => {
      cancelled = true
    }
  }, [auditId, pageId])

  const back = (
    <Link to={`/site-audit/${auditId}`} className="back-link">
      ← Back to site audit
    </Link>
  )

  if (error) {
    return (
      <>
        {back}
        <Notice error={error} />
      </>
    )
  }

  if (!page) {
    return (
      <div className="center-note">
        <span className="spinner" />
        <span>Loading page…</span>
      </div>
    )
  }

  if (!page.results?.fetched_ok) {
    return (
      <>
        {back}
        <div className="card">
          <div className="report-head">
            <div className="meta">
              <h1>This page could not be analyzed</h1>
              <div className="url">{page.url}</div>
            </div>
          </div>
          <Notice tone="error">{page.error || 'The page could not be fetched.'}</Notice>
        </div>
      </>
    )
  }

  return (
    <>
      {back}
      <ReportBody results={page.results} />
    </>
  )
}
