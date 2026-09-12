/**
 * One page from a site audit, rendered with the full single-page report view.
 *
 * The crawl stores the identical payload a single-page report produces, so this
 * reuses ReportBody rather than showing a reduced version of the same analysis.
 */
import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { siteAuditsApi } from '../api/endpoints'
import type { SiteAuditPageDetail } from '../api/types'
import { Notice } from '../components/Notice'
import { ReportBody } from '../components/ReportBody'
import { BackLink, Panel } from '../components/Page'
import { CenterNote } from '../components/ReportStates'

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

  const back = <BackLink to={`/site-audit/${auditId}`}>Back to site audit</BackLink>

  if (error) {
    return (
      <>
        {back}
        <Notice error={error} className="mt-4" />
      </>
    )
  }

  if (!page) {
    return <CenterNote>Loading page…</CenterNote>
  }

  if (!page.results?.fetched_ok) {
    return (
      <>
        {back}
        <Panel className="mt-6">
          <h1 className="text-[22px] leading-tight font-semibold tracking-[-0.025em]">
            This page could not be analyzed
          </h1>
          <p className="mt-1.5 text-[13.5px] break-all text-muted-foreground">
            {page.url}
          </p>
          <Notice tone="error" className="mt-5">
            {page.error || 'The page could not be fetched.'}
          </Notice>
        </Panel>
      </>
    )
  }

  return (
    <>
      {back}
      <div className="mt-6">
        <ReportBody results={page.results} />
      </div>
    </>
  )
}
