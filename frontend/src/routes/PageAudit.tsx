/**
 * Single-page audit: one URL, optionally judged against target keywords.
 *
 * The sibling feature is the site audit, which crawls many pages and takes no
 * keywords. Keeping them apart is deliberate: keyword targeting depends on what
 * the submitter typed, and only makes sense aimed at one specific page.
 *
 * The submit form used to put the URL, the keywords and the button on one line,
 * which left no room for either field to be labelled and made the optional one
 * look as required as the URL. It is two rows now: the thing you must give, and
 * the thing you may.
 */
import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { FileSearch, Search, Trash2 } from 'lucide-react'
import { analysesApi, quotaApi } from '../api/endpoints'
import type { Paginated, Quota, ReportSummary } from '../api/types'
import { Notice } from '../components/Notice'
import { QuotaBar } from '../components/QuotaBar'
import { StatusPill } from '../components/StatusPill'
import { ScoreCell } from '../components/ScoreRing'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { Pager } from '../components/Pager'
import { EmptyState, PageHeader, Panel, Section, TableSkeleton } from '../components/Page'
import { Spinner } from '../components/Spinner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
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
  const [pendingDelete, setPendingDelete] = useState<ReportSummary | null>(null)

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

  async function confirmDelete() {
    const target = pendingDelete
    setPendingDelete(null)
    if (!target) return
    try {
      await analysesApi.remove(target.id)
      loadHistory(page)
    } catch (caught) {
      setListError(caught)
    }
  }

  const outOfQuota = quota !== null && quota.remaining_today <= 0
  const totalPages = history ? Math.max(1, Math.ceil(history.total / history.page_size)) : 1

  return (
    <>
      <PageHeader
        title="Page audit"
        description={
          <>
            Every check against a single URL, covering meta, content, structure,
            links, indexability, performance, security and mobile. Auditing a whole
            site instead?{' '}
            <Link
              to="/site-audit"
              className="font-medium text-accent-on-tint underline-offset-4 hover:underline"
            >
              Run a site audit
            </Link>
            .
          </>
        }
      />

      <Panel className="mt-8">
        <Notice error={submitError} className="mb-4" />
        {outOfQuota && !submitError ? (
          <Notice tone="warning" className="mb-4">
            <strong className="font-semibold">Daily limit reached.</strong> Your
            allowance resets at midnight UTC.
          </Notice>
        ) : null}

        <form onSubmit={handleSubmit} noValidate className="grid gap-4">
          <div className="grid gap-1.5">
            <Label htmlFor="url">Page URL</Label>
            <div className="flex flex-col gap-2.5 sm:flex-row">
              <div className="relative flex-1">
                <Search
                  aria-hidden="true"
                  className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
                />
                <Input
                  id="url"
                  type="text"
                  inputMode="url"
                  placeholder="https://example.com"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  disabled={submitting}
                  required
                  className="h-10 pl-9"
                />
              </div>
              <Button
                type="submit"
                disabled={submitting || !url.trim()}
                className="h-10 px-5 sm:w-auto"
              >
                {submitting ? (
                  <>
                    <Spinner />
                    Analyzing
                  </>
                ) : (
                  'Analyze'
                )}
              </Button>
            </div>
          </div>

          <div className="grid gap-1.5">
            <Label htmlFor="keywords">
              Target keywords
              <span className="font-normal text-muted-foreground">optional</span>
            </Label>
            <Input
              id="keywords"
              type="text"
              placeholder="running shoes, trail runners"
              value={keywordInput}
              onChange={(e) => setKeywordInput(e.target.value)}
              disabled={submitting}
              aria-describedby="keywords-hint"
              className="h-10"
            />
            <p id="keywords-hint" className="text-[12.5px] text-muted-foreground">
              Up to {MAX_TARGET_KEYWORDS}, comma separated. You get a map of where
              each one appears on the page, scored separately so it never moves the
              page score.
            </p>
          </div>
        </form>

        <Separator className="my-5" />
        <QuotaBar quota={quota} />
      </Panel>

      <Section
        title="Recent page reports"
        meta={history ? `${history.total} total` : undefined}
      >
        <Notice error={listError} className="mb-4" />

        {loadingList && !history ? (
          <TableSkeleton />
        ) : history && history.items.length > 0 ? (
          <>
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead>Page</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Score</TableHead>
                  <TableHead>Analyzed</TableHead>
                  <TableHead>
                    <span className="sr-only">Actions</span>
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {history.items.map((report) => (
                  <TableRow key={report.id} className="group">
                    <TableCell className="max-w-[420px]">
                      <Link
                        to={`/report/${report.id}`}
                        className="block min-w-0 rounded-sm"
                      >
                        <span className="block truncate font-medium">
                          {report.title || shortUrl(report.url)}
                        </span>
                        <span className="block truncate text-[12.5px] text-muted-foreground">
                          {shortUrl(report.url)}
                          {report.target_keywords?.length
                            ? ` · ${report.target_keywords.join(', ')}`
                            : ''}
                        </span>
                      </Link>
                    </TableCell>
                    <TableCell>
                      <StatusPill status={report.status} />
                    </TableCell>
                    <TableCell className="text-right">
                      <ScoreCell
                        score={report.overall_score}
                        grade={report.overall_grade}
                      />
                    </TableCell>
                    <TableCell className="whitespace-nowrap text-muted-foreground">
                      {formatDate(report.created_at)}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon-sm"
                        onClick={() => setPendingDelete(report)}
                        aria-label={`Delete report for ${report.url}`}
                        className="text-muted-foreground hover:bg-crit-soft hover:text-crit"
                      >
                        <Trash2 />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>

            <Pager
              page={history.page}
              totalPages={totalPages}
              busy={loadingList}
              onChange={setPage}
            />
          </>
        ) : (
          <EmptyState
            icon={<FileSearch className="size-5" />}
            title="No page reports yet"
          >
            Audit a page above and it will show up here.
          </EmptyState>
        )}
      </Section>

      <ConfirmDialog
        open={pendingDelete !== null}
        onOpenChange={(open) => {
          if (!open) setPendingDelete(null)
        }}
        title="Delete this report?"
        description={
          pendingDelete
            ? `The report for ${shortUrl(pendingDelete.url)} will be removed permanently. This cannot be undone.`
            : ''
        }
        confirmLabel="Delete report"
        destructive
        onConfirm={confirmDelete}
      />
    </>
  )
}

/** Let people type "example.com" without the scheme. */
function normalizeUrl(value: string): string {
  return /^https?:\/\//i.test(value) ? value : `https://${value}`
}
