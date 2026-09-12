/**
 * Site audit report.
 *
 * The useful output of a crawl is not an average score, it is *which problems
 * repeat*. One page with a short title is a task; forty pages with short titles
 * is a template bug. So issues ranked by how many pages they affect lead the
 * page, and the per-page table sits underneath for drilling in.
 */
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ExternalLink } from 'lucide-react'
import { siteAuditsApi } from '../api/endpoints'
import type { SiteAuditDetail, SiteIssue } from '../api/types'
import { Notice } from '../components/Notice'
import { ScoreRing, ScoreCell } from '../components/ScoreRing'
import { StatusPill } from '../components/StatusPill'
import { CategoryMeters, CountChip, ShareMeter } from '../components/Readouts'
import { Finding, FindingDetail, FindingFix, FindingList } from '../components/Finding'
import { BackLink, EmptyState, Section, Stat, StatGrid } from '../components/Page'
import { CenterNote, FailedPanel, PendingPanel } from '../components/ReportStates'
import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
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

  // Worst page first: the table is a queue of work, not a leaderboard.
  const pagesWorstFirst = useMemo(() => {
    if (!audit) return []
    return [...audit.pages].sort(
      (a, b) => (a.overall_score ?? -1) - (b.overall_score ?? -1),
    )
  }, [audit])

  const back = <BackLink to="/site-audit">Back to site audits</BackLink>

  if (error) {
    return (
      <>
        {back}
        <Notice error={error} className="mt-4" />
      </>
    )
  }

  if (!audit) {
    return <CenterNote>Loading site audit…</CenterNote>
  }

  const results = audit.results
  const waiting = audit.status === 'pending' || audit.status === 'running'

  return (
    <>
      {back}

      {waiting ? (
        <PendingPanel
          title={audit.domain || audit.start_url}
          url={audit.start_url}
          status={audit.status}
          timedOut={timedOut}
          onRetry={() => setReloadKey((k) => k + 1)}
          stalledNoun="Still crawling."
        >
          Crawling up to {audit.max_pages} pages and auditing each one. A large site
          can take a few minutes.
        </PendingPanel>
      ) : null}

      {audit.status === 'failed' ? (
        <FailedPanel
          title="Site audit failed"
          url={audit.start_url}
          status={audit.status}
          error={audit.error}
          fallback="The site could not be crawled."
        />
      ) : null}

      {results && audit.status === 'done' ? (
        <div className="mt-6">
          {/* Masthead: the average, the site it belongs to, and the counts. */}
          <div className="flex flex-wrap items-start gap-x-8 gap-y-6">
            <ScoreRing score={results.overall_score} grade={results.overall_grade} />

            <div className="min-w-[260px] flex-1">
              <h1 className="text-[24px] leading-tight font-semibold tracking-[-0.03em] break-words">
                {results.domain}
              </h1>
              <a
                href={audit.start_url}
                target="_blank"
                rel="noreferrer nofollow"
                className="mt-1.5 inline-flex items-center gap-1.5 text-[13.5px] break-all text-muted-foreground underline-offset-4 transition-colors hover:text-foreground hover:underline"
              >
                {audit.start_url}
                <ExternalLink className="size-3.5 shrink-0" aria-hidden="true" />
              </a>

              <div className="mt-3 flex flex-wrap items-center gap-2">
                <StatusPill status={audit.status} />
                <Badge variant="info" className="font-medium">
                  {results.pages_crawled} pages via {results.discovery_source}
                </Badge>
              </div>

              <div className="mt-4 flex flex-wrap gap-2">
                <CountChip
                  tone="critical"
                  count={results.issue_counts.critical}
                  label="critical"
                />
                <CountChip
                  tone="warning"
                  count={results.issue_counts.warning}
                  label={results.issue_counts.warning === 1 ? 'warning' : 'warnings'}
                />
                <CountChip tone="good" count={results.issue_counts.good} label="passed" />
              </div>

              <p className="mt-3.5 text-[13px] text-muted-foreground">
                Crawled {formatDate(results.generated_at)}
              </p>
            </div>
          </div>

          {results.pages_failed > 0 ? (
            <Notice tone="warning" className="mt-6">
              <strong className="font-semibold">
                {results.pages_failed} page{results.pages_failed === 1 ? '' : 's'} could
                not be fetched.
              </strong>{' '}
              They are excluded from the averages below and listed at the bottom.
            </Notice>
          ) : null}

          {results.capped_pages.length > 0 ? (
            <Notice tone="warning" className="mt-3">
              <strong className="font-semibold">
                {results.capped_pages.length} page
                {results.capped_pages.length === 1 ? '' : 's'} cannot be indexed.
              </strong>{' '}
              Their scores are capped, which drags the site average down. Fix those
              first: {results.capped_pages.slice(0, 3).map((p) => shortUrl(p.url)).join(', ')}
              {results.capped_pages.length > 3 ? ' and others' : ''}.
            </Notice>
          ) : null}

          <Section title="Spread across the crawl" headingId="spread">
            <StatGrid className="lg:grid-cols-6">
              <Stat label="Average score" value={results.overall_score} />
              <Stat label="Best page" value={results.score_spread.max} />
              <Stat label="Median" value={results.score_spread.median} />
              <Stat label="Worst page" value={results.score_spread.min} />
              <Stat label="Pages crawled" value={results.pages_crawled} />
              <Stat label="Failed" value={results.pages_failed} />
            </StatGrid>
          </Section>

          <Section
            title="Issues across the site"
            meta="Ranked by pages affected"
            headingId="issues"
          >
            {results.top_issues.length === 0 ? (
              <EmptyState title="Nothing repeating">
                No warnings or critical issues came back on any crawled page.
              </EmptyState>
            ) : (
              <FindingList>
                {results.top_issues.map((issue) => (
                  <IssueRow key={issue.id} issue={issue} />
                ))}
              </FindingList>
            )}
          </Section>

          <Section
            title="Category averages"
            meta={`Across ${results.pages_crawled} pages`}
            headingId="categories"
          >
            <CategoryMeters categories={results.category_scores} />
          </Section>

          <Section title="Pages" meta="Worst first" headingId="pages">
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead>Page</TableHead>
                  <TableHead className="text-right">Score</TableHead>
                  <TableHead className="text-right">Critical</TableHead>
                  <TableHead className="text-right">Warnings</TableHead>
                  <TableHead className="text-right">Load</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {pagesWorstFirst.map((page) => (
                  <TableRow key={page.id}>
                    <TableCell className="max-w-[440px]">
                      <Link
                        to={`/site-audit/${audit.id}/page/${page.id}`}
                        className="block min-w-0 rounded-sm"
                      >
                        <span className="block truncate font-medium">
                          {page.title || shortUrl(page.final_url || page.url)}
                        </span>
                        <span className="block truncate text-[12.5px] text-muted-foreground">
                          {shortUrl(page.final_url || page.url)}
                        </span>
                      </Link>
                    </TableCell>
                    <TableCell className="text-right">
                      {page.overall_score === null ? (
                        <StatusPill status="failed" />
                      ) : (
                        <ScoreCell
                          score={page.overall_score}
                          grade={page.overall_grade}
                        />
                      )}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {page.issue_counts?.critical ?? '—'}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {page.issue_counts?.warning ?? '—'}
                    </TableCell>
                    <TableCell className="text-right whitespace-nowrap tabular-nums">
                      {formatMs(page.load_time_ms)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Section>

          {results.errors.length > 0 ? (
            <Section title="Pages that could not be fetched" headingId="errors">
              <FindingList>
                {results.errors.map((failure) => (
                  <Finding
                    key={failure.url}
                    status="critical"
                    label={shortUrl(failure.url)}
                    message={failure.error || 'Fetch failed.'}
                  />
                ))}
              </FindingList>
            </Section>
          ) : null}
        </div>
      ) : null}
    </>
  )
}

/** One problem, with how much of the site it touches. */
function IssueRow({ issue }: { issue: SiteIssue }) {
  const share = issue.total_pages ? (issue.affected_pages / issue.total_pages) * 100 : 0
  const tone = issue.status === 'critical' ? 'critical' : 'warning'
  return (
    <Finding
      status={issue.status}
      label={issue.label}
      badges={
        <>
          <StatusPill status={issue.status} />
          {issue.sitewide ? <Badge variant="warning">site-wide</Badge> : null}
        </>
      }
      message={
        <>
          Affects {issue.affected_pages} of {issue.total_pages} pages in{' '}
          {categoryLabel(issue.category)}.
        </>
      }
      trailing={issue.affected_pages}
    >
      <ShareMeter
        share={share}
        tone={tone}
        ariaLabel={`Affects ${issue.affected_pages} of ${issue.total_pages} pages`}
      />
      {issue.recommendation ? <FindingFix>{issue.recommendation}</FindingFix> : null}
      <FindingDetail>
        e.g. {issue.example_urls.slice(0, 3).map((u) => shortUrl(u, 40)).join(' · ')}
      </FindingDetail>
    </Finding>
  )
}
