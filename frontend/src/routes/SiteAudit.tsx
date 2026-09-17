/**
 * Site audit: crawl many pages of one site and report what repeats.
 *
 * The sibling feature is the single-page audit, which takes target keywords.
 * This one takes a page budget instead: keyword placement is a judgement about
 * one specific page, not something to average across a crawl.
 */
import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Globe, Search, Trash2 } from 'lucide-react'
import { quotaApi, siteAuditsApi } from '../api/endpoints'
import type { Paginated, PsiScope, Quota, SiteAuditSummary } from '../api/types'
import { Notice } from '../components/Notice'
import { PsiOption, usePsiKey } from '../components/PsiOption'
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
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
/** Must stay within SITE_AUDIT_MAX_PAGES in app/core/config.py. */
const PAGE_BUDGETS = [5, 10, 25, 50]
const DEFAULT_BUDGET = 10

export function SiteAudit() {
  const navigate = useNavigate()
  const [url, setUrl] = useState('')
  const [maxPages, setMaxPages] = useState(DEFAULT_BUDGET)
  // Opt-out rather than opt-in: with a key saved, the default is to use it.
  const psiKey = usePsiKey()
  const [usePsi, setUsePsi] = useState(true)
  // 'homepage' is the default coverage even though the API would accept 'all'.
  // A PSI run is 20-30s per page, so defaulting a 50-page crawl to full
  // coverage would turn a two-minute audit into a twenty-minute one for
  // someone who only ticked a box.
  const [psiScope, setPsiScope] = useState<PsiScope>('homepage')
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<unknown>(null)

  const [quota, setQuota] = useState<Quota | null>(null)
  const [history, setHistory] = useState<Paginated<SiteAuditSummary> | null>(null)
  const [page, setPage] = useState(1)
  const [listError, setListError] = useState<unknown>(null)
  const [loadingList, setLoadingList] = useState(true)
  const [pendingDelete, setPendingDelete] = useState<SiteAuditSummary | null>(null)

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
      const accepted = await siteAuditsApi.submit(
        normalizeUrl(target),
        maxPages,
        // Only ever an explicit false; see the page audit for why.
        psiKey.configured && !usePsi ? false : undefined,
        psiKey.configured && usePsi ? psiScope : undefined,
      )
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

  async function confirmDelete() {
    const target = pendingDelete
    setPendingDelete(null)
    if (!target) return
    try {
      await siteAuditsApi.remove(target.id)
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
        title="Site audit"
        description={
          <>
            Crawls from your sitemap, falling back to internal links, and runs the
            full audit on every page. Findings are then ranked by how many pages
            they touch, which is what separates a template bug from a one-off.
            Auditing one page instead?{' '}
            <Link
              to="/app"
              className="font-medium text-accent-on-tint underline-offset-4 hover:underline"
            >
              Run a page audit
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
            <Label htmlFor="site-url">Site URL</Label>
            <div className="flex flex-col gap-2.5 sm:flex-row">
              <div className="relative flex-1">
                <Search
                  aria-hidden="true"
                  className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
                />
                <Input
                  id="site-url"
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
              <Select
                value={String(maxPages)}
                onValueChange={(value) => setMaxPages(Number(value))}
                disabled={submitting}
              >
                <SelectTrigger
                  id="max-pages"
                  aria-label="Pages to crawl"
                  className="h-10 sm:w-[168px]"
                >
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {PAGE_BUDGETS.map((budget) => (
                    <SelectItem key={budget} value={String(budget)}>
                      Up to {budget} pages
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button
                type="submit"
                disabled={submitting || !url.trim()}
                className="h-10 px-5"
              >
                {submitting ? (
                  <>
                    <Spinner />
                    Starting
                  </>
                ) : (
                  'Crawl site'
                )}
              </Button>
            </div>
            <p className="text-[12.5px] text-muted-foreground">
              One crawl costs one quota unit whatever the page count.
            </p>
          </div>

          <PsiOption
            keyState={psiKey}
            enabled={usePsi}
            onEnabledChange={setUsePsi}
            disabled={submitting}
            scope={psiScope}
            onScopeChange={setPsiScope}
            maxPages={maxPages}
          />
        </form>

        <Separator className="my-5" />
        <QuotaBar quota={quota} />
      </Panel>

      <Section
        title="Recent site audits"
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
                  <TableHead>Site</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Pages</TableHead>
                  <TableHead className="text-right">Avg score</TableHead>
                  <TableHead>Started</TableHead>
                  <TableHead>
                    <span className="sr-only">Actions</span>
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {history.items.map((audit) => (
                  <TableRow key={audit.id}>
                    <TableCell className="max-w-[380px]">
                      <Link
                        to={`/site-audit/${audit.id}`}
                        className="block min-w-0 rounded-sm"
                      >
                        <span className="block truncate font-medium">
                          {audit.domain || shortUrl(audit.start_url)}
                        </span>
                        <span className="block truncate text-[12.5px] text-muted-foreground">
                          {shortUrl(audit.start_url)}
                          {audit.discovery_source ? ` · via ${audit.discovery_source}` : ''}
                        </span>
                      </Link>
                    </TableCell>
                    <TableCell>
                      <StatusPill status={audit.status} />
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {audit.status === 'done' ? (
                        <>
                          {audit.pages_crawled}
                          <span className="text-muted-foreground"> / {audit.max_pages}</span>
                        </>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      <ScoreCell
                        score={audit.overall_score}
                        grade={audit.overall_grade}
                      />
                    </TableCell>
                    <TableCell className="whitespace-nowrap text-muted-foreground">
                      {formatDate(audit.created_at)}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon-sm"
                        onClick={() => setPendingDelete(audit)}
                        aria-label={`Delete site audit for ${audit.start_url}`}
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
          <EmptyState icon={<Globe className="size-5" />} title="No site audits yet">
            Crawl a site above and it will show up here.
          </EmptyState>
        )}
      </Section>

      <ConfirmDialog
        open={pendingDelete !== null}
        onOpenChange={(open) => {
          if (!open) setPendingDelete(null)
        }}
        title="Delete this site audit?"
        description={
          pendingDelete
            ? `The crawl of ${pendingDelete.domain || shortUrl(pendingDelete.start_url)} and every page report in it will be removed permanently. This cannot be undone.`
            : ''
        }
        confirmLabel="Delete audit"
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
