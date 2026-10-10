/**
 * Renders one analyzed page: score, timings, keyword targeting, categories and
 * every check.
 *
 * Shared by the single-page report and by one page inside a site audit. Both
 * carry the identical `SeoResult` payload, so the site audit gets the full
 * report view for free rather than a second, thinner rendering of the same data.
 *
 * The redesign is mostly about what leads. A report is read to answer "what do
 * I fix first", so the score, the three counts and the route into the failing
 * checks are the masthead, and everything that merely describes the fetch has
 * moved below a rule. Category scores became a list of meters rather than a
 * grid of eight boxes: they are eight readings on one scale, and a list lets
 * them be compared down a column instead of hunted around a grid.
 */
import { useMemo, useRef, useState, type ReactNode } from 'react'
import { ExternalLink } from 'lucide-react'
import type {
  CheckResult,
  CheckStatus,
  KeywordReport,
  PsiRun,
  SeoResult,
} from '../api/types'
import { Notice } from './Notice'
import { ScoreRing, scoreColor, scoreTextClass } from './ScoreRing'
import { CategoryMeters, CountChip } from './Readouts'
import { StatusPill } from './StatusPill'
import { Finding, FindingDetail, FindingFix, FindingList } from './Finding'
import { EmptyState, Section, Stat, StatGrid } from './Page'
import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { categoryLabel, formatDate, formatKb, formatMs, renderValue } from '../lib/format'
import { cn } from '@/lib/utils'

const STATUS_ORDER: CheckStatus[] = ['critical', 'warning', 'good', 'info']

/**
 * Reports produced before the keyword feature was split out carry their
 * results inside a `keyword_targeting` check instead of a top-level report.
 * Old reports stay readable rather than silently losing their keyword section.
 */
function keywordReportOf(results: SeoResult): KeywordReport | null {
  if (results.keyword_report) return results.keyword_report
  const legacy = results.checks.find((c) => c.id === 'keyword_targeting')
  const value = legacy?.value as { average_score?: number; keywords?: [] } | null
  if (!legacy || !value?.keywords?.length) return null
  return {
    score: value.average_score ?? 0,
    grade: '',
    status: legacy.status,
    message: legacy.message,
    recommendation: legacy.recommendation,
    keywords: value.keywords,
    placement_weights: {},
    placement_labels: {},
  }
}

interface Props {
  results: SeoResult
  /** Keywords this page was judged against, shown as pills in the header. */
  targetKeywords?: string[] | null
  /** Extra badge rendered next to the keyword pills, e.g. a report status. */
  badge?: ReactNode
}

export function ReportBody({ results, targetKeywords, badge }: Props) {
  const [filter, setFilter] = useState<CheckStatus | 'all'>('all')
  const checksRef = useRef<HTMLDivElement>(null)

  function focusChecks(status: CheckStatus) {
    setFilter(status)
    checksRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  const counts = useMemo(() => {
    const tally: Record<string, number> = { all: results.checks.length }
    for (const status of STATUS_ORDER) tally[status] = 0
    for (const check of results.checks) tally[check.status] = (tally[check.status] ?? 0) + 1
    return tally
  }, [results])

  /** Reuse each capping check's own message rather than restating it here. */
  const capReasons = useMemo(() => {
    if (!results.capped_by?.length) return []
    return results.capped_by
      .map((id) => results.checks.find((c) => c.id === id)?.message)
      .filter((message): message is string => Boolean(message))
  }, [results])

  const keywords = useMemo(() => keywordReportOf(results), [results])

  const grouped = useMemo(() => {
    const visible = results.checks.filter((c) => filter === 'all' || c.status === filter)
    const byCategory = new Map<string, CheckResult[]>()
    // Follow the category order the API returned, which is weight-ordered.
    for (const category of results.category_scores) byCategory.set(category.category, [])
    for (const check of visible) {
      if (!byCategory.has(check.category)) byCategory.set(check.category, [])
      byCategory.get(check.category)!.push(check)
    }
    return [...byCategory.entries()].filter(([, checks]) => checks.length > 0)
  }, [results, filter])

  return (
    <>
      {/* Masthead: the score, what it is a score of, and the way into the fixes. */}
      <div className="flex flex-wrap items-start gap-x-8 gap-y-6">
        <ScoreRing score={results.overall_score} grade={results.overall_grade} />

        <div className="min-w-[260px] flex-1">
          <h1 className="text-[24px] leading-tight font-semibold tracking-[-0.03em] break-words text-balance">
            {results.title || results.domain}
          </h1>
          <a
            href={results.final_url}
            target="_blank"
            rel="noreferrer nofollow"
            className="mt-1.5 inline-flex items-center gap-1.5 text-[13.5px] break-all text-muted-foreground underline-offset-4 transition-colors hover:text-foreground hover:underline"
          >
            {results.final_url}
            <ExternalLink className="size-3.5 shrink-0" aria-hidden="true" />
          </a>

          {badge || (targetKeywords ?? []).length > 0 ? (
            <div className="mt-3 flex flex-wrap items-center gap-2">
              {badge}
              {(targetKeywords ?? []).map((keyword) => (
                <Badge variant="info" key={keyword} className="font-medium">
                  {keyword}
                </Badge>
              ))}
            </div>
          ) : null}

          <div className="mt-4 flex flex-wrap gap-2">
            <CountChip
              tone="critical"
              count={counts.critical}
              label="critical"
              onSelect={() => focusChecks('critical')}
            />
            <CountChip
              tone="warning"
              count={counts.warning}
              label={counts.warning === 1 ? 'warning' : 'warnings'}
              onSelect={() => focusChecks('warning')}
            />
            <CountChip tone="good" count={counts.good} label="passed" />
          </div>

          <p className="mt-3.5 text-[13px] text-muted-foreground">
            Analyzed {formatDate(results.generated_at)}
          </p>
        </div>
      </div>

      {capReasons.length > 0 ? (
        <Notice tone="warning" className="mt-6">
          <strong className="font-semibold">
            Score capped at {results.overall_score}.
          </strong>{' '}
          {capReasons.join(' ')}
          {results.uncapped_score === undefined
            ? null
            : ` Fixing that alone would take this page to ${results.uncapped_score}.`}
        </Notice>
      ) : null}

      <Section title="How the page was served" headingId="fetch">
        <StatGrid>
          <Stat label="TTFB" value={formatMs(results.timing.ttfb_ms)} />
          <Stat label="Load time" value={formatMs(results.timing.load_time_ms)} />
          <Stat label="Page size" value={formatKb(results.timing.html_size_kb)} />
          <Stat label="Transferred" value={formatKb(results.timing.transfer_size_kb)} />
          <Stat label="HTTP" value={results.status_code ?? '—'} />
          <Stat label="Redirects" value={results.timing.redirect_count} />
          <Stat label="Compressed" value={results.timing.compressed ? 'Yes' : 'No'} />
        </StatGrid>
      </Section>

      {results.psi && Object.keys(results.psi.strategies).length > 0 ? (
        <PageSpeedSection strategies={results.psi.strategies} />
      ) : null}

      {keywords ? <KeywordSection report={keywords} /> : null}

      <Section
        title="Category scores"
        meta="Weighted into the overall score"
        headingId="categories"
      >
        <CategoryMeters categories={results.category_scores} />
      </Section>

      <div ref={checksRef} className="scroll-mt-[calc(var(--header-h)+16px)]">
        <Section
          title="Checks"
          meta={`${results.checks.length} run against this page`}
          headingId="checks"
        >
          <div
            className="flex flex-wrap gap-1.5"
            role="group"
            aria-label="Filter checks by status"
          >
            <FilterChip
              active={filter === 'all'}
              count={counts.all}
              label="All"
              onSelect={() => setFilter('all')}
            />
            {STATUS_ORDER.map((status) => (
              <FilterChip
                key={status}
                active={filter === status}
                count={counts[status]}
                label={status}
                disabled={counts[status] === 0}
                onSelect={() => setFilter(status)}
              />
            ))}
          </div>

          <div className="mt-6 space-y-9">
            {grouped.length === 0 ? (
              <EmptyState title="Nothing matches that filter">
                No checks came back with that status. Pick another one above.
              </EmptyState>
            ) : (
              grouped.map(([category, checks]) => (
                <div key={category}>
                  <h3 className="mb-2.5 text-[11px] font-semibold tracking-[0.07em] text-muted-foreground uppercase">
                    {categoryLabel(category)}
                  </h3>
                  <FindingList>
                    {checks.map((check) => (
                      <CheckRow key={check.id} check={check} />
                    ))}
                  </FindingList>
                </div>
              ))
            )}
          </div>
        </Section>
      </div>
    </>
  )
}

/** A status filter above the check list. */
function FilterChip({
  active,
  count,
  label,
  disabled,
  onSelect,
}: {
  active: boolean
  count: number
  label: string
  disabled?: boolean
  onSelect: () => void
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      disabled={disabled}
      aria-pressed={active}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-[13px] capitalize transition-colors',
        active
          ? 'border-primary/40 bg-accent-soft font-medium text-accent-on-tint'
          : 'border-border-strong text-muted-foreground enabled:hover:bg-surface enabled:hover:text-foreground',
        'disabled:opacity-45',
        !disabled && 'cursor-pointer',
      )}
    >
      {label}
      <span className="tabular-nums opacity-70">{count}</span>
    </button>
  )
}

/** Fallback order and wording for reports that predate the API sending labels. */
const FALLBACK_PLACEMENTS: Record<string, string> = {
  title: 'Title',
  h1: 'H1',
  meta_description: 'Meta description',
  first_paragraph: 'First 100 words',
  subheading: 'Subheading',
  url_slug: 'URL',
  image_alt: 'Image alt',
}

function KeywordSection({ report }: { report: KeywordReport }) {
  const slots = Object.keys(report.placement_weights).length
    ? Object.keys(report.placement_weights)
    : Object.keys(FALLBACK_PLACEMENTS)
  const label = (slot: string) =>
    report.placement_labels[slot] ?? FALLBACK_PLACEMENTS[slot] ?? slot

  return (
    <Section
      title="Keyword targeting"
      meta="Scored separately from the page score"
      headingId="keywords"
    >
      <p className="max-w-[70ch] text-[14px] leading-relaxed text-muted-foreground">
        {report.message} Placement is what this measures, so it does not change the
        page score above.
      </p>

      {/*
        One legend for the whole card. The placement chips below are coloured
        and struck through to say the same thing, but the vocabulary is specific
        enough to this tool that naming it once is worth the four lines.
      */}
      <ul className="mt-4 flex list-none flex-wrap gap-x-5 gap-y-1.5 p-0 text-[12px] text-muted-foreground">
        <LegendKey className="bg-good-soft text-good">Exact phrase</LegendKey>
        <LegendKey className="bg-warn-soft text-warn">Close variant</LegendKey>
        <LegendKey className="bg-surface-2 text-muted-foreground line-through">
          Not found
        </LegendKey>
        <LegendKey className="border border-border text-muted-foreground opacity-60">
          No such element
        </LegendKey>
      </ul>

      <div className="mt-5 grid gap-3">
        {report.keywords.map((result) => (
          <div
            key={result.keyword}
            className="rounded-xl border border-border px-4 py-3.5"
          >
            <div className="flex items-baseline justify-between gap-4">
              <span className="font-semibold break-words">{result.keyword}</span>
              <span
                className={cn(
                  'text-[17px] font-semibold tabular-nums tracking-[-0.02em]',
                  scoreTextClass(result.score),
                )}
              >
                {result.score}
              </span>
            </div>

            <div className="mt-2.5 flex flex-wrap gap-1.5">
              {slots.map((slot) => {
                const match = result.found_in[slot]
                const absent = result.not_applicable?.includes(slot)
                return (
                  <span
                    key={slot}
                    className={cn(
                      'rounded-full px-2.5 py-0.5 text-[11.5px] font-semibold',
                      absent
                        ? 'border border-border text-muted-foreground opacity-60'
                        : match === 'exact'
                          ? 'bg-good-soft text-good'
                          : match === 'partial'
                            ? 'bg-warn-soft text-warn'
                            : 'bg-surface-2 text-muted-foreground line-through',
                    )}
                  >
                    {label(slot)}
                  </span>
                )
              })}
            </div>

            <p className="mt-2.5 text-[13px] text-muted-foreground">
              Density <span className="tabular-nums">{result.density_pct}%</span>
              {result.over_used ? ' · repeated too often' : ''}
            </p>
          </div>
        ))}
      </div>

      {report.recommendation ? (
        <div className="mt-4">
          <FindingFix>{report.recommendation}</FindingFix>
        </div>
      ) : null}
    </Section>
  )
}

/** Rows of the mobile/desktop comparison, in Lighthouse's own order. */
const PSI_ROWS: { label: string; read: (run: PsiRun) => ReactNode }[] = [
  { label: 'Performance', read: (r) => scoreCell(r.scores.performance) },
  { label: 'Accessibility', read: (r) => scoreCell(r.scores.accessibility) },
  { label: 'Best practices', read: (r) => scoreCell(r.scores['best-practices']) },
  { label: 'SEO', read: (r) => scoreCell(r.scores.seo) },
  { label: 'Largest Contentful Paint', read: (r) => formatMs(r.lab.lcp_ms) },
  { label: 'Cumulative Layout Shift', read: (r) => r.lab.cls?.toFixed(3) ?? '—' },
  { label: 'Total Blocking Time', read: (r) => formatMs(r.lab.tbt_ms) },
  { label: 'First Contentful Paint', read: (r) => formatMs(r.lab.fcp_ms) },
  { label: 'Speed Index', read: (r) => formatMs(r.lab.speed_index_ms) },
]

function scoreCell(score: number | null | undefined): ReactNode {
  if (score === null || score === undefined) return '—'
  return <span className={cn('font-semibold', scoreTextClass(score))}>{score}</span>
}

/**
 * Mobile and desktop Lighthouse runs side by side. Only mobile is scored,
 * because Google ranks on the mobile crawl; desktop is here for comparison.
 */
function PageSpeedSection({ strategies }: { strategies: Record<string, PsiRun> }) {
  const order = ['mobile', 'desktop'].filter((name) => strategies[name])
  return (
    <Section title="PageSpeed" meta="Lighthouse lab run · mobile is scored" headingId="pagespeed">
      <Table>
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <TableHead>Metric</TableHead>
            {order.map((name) => (
              <TableHead key={name} className="text-right capitalize">
                {name}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {PSI_ROWS.map((row) => (
            <TableRow key={row.label}>
              <TableCell>{row.label}</TableCell>
              {order.map((name) => (
                <TableCell key={name} className="text-right whitespace-nowrap tabular-nums">
                  {row.read(strategies[name])}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Section>
  )
}

function LegendKey({
  className,
  children,
}: {
  className?: string
  children: ReactNode
}) {
  return (
    <li className="flex items-center gap-1.5">
      <span
        aria-hidden="true"
        className={cn('rounded-full px-1.5 py-px text-[10px] font-semibold', className)}
      >
        Aa
      </span>
      {children}
    </li>
  )
}

interface PsiOpportunity {
  id: string
  title: string
  savings_ms: number
  savings_bytes: number
}

/**
 * Lighthouse's ranked fixes. These need their own renderer: the generic one
 * stringifies an array of objects into "[object Object]", and the ordering is
 * the whole point — the list is sorted by estimated impact, so it reads as a
 * work queue rather than a set of unrelated notes.
 */
function OpportunityList({ items }: { items: PsiOpportunity[] }) {
  return (
    <ul className="mt-2.5 grid gap-1.5">
      {items.map((item) => (
        <li
          key={item.id}
          className="flex items-baseline justify-between gap-3 text-[13px]"
        >
          <span className="min-w-0 break-words">{item.title}</span>
          <span className="shrink-0 font-mono text-[12px] tabular-nums text-muted-foreground">
            {item.savings_ms > 0
              ? `−${formatMs(item.savings_ms)}`
              : `−${formatKb(item.savings_bytes / 1024)}`}
          </span>
        </li>
      ))}
    </ul>
  )
}

/**
 * PageSpeed checks whose message already spells the numbers out in full.
 * Repeating the raw payload underneath them adds a line of `lcp ms: 1568 ·
 * cls: 0.001` that says the same thing less clearly.
 */
const SELF_DESCRIBING = new Set([
  'core_web_vitals',
  'field_vitals',
  'lighthouse_performance',
  'lighthouse_categories',
])

function CheckRow({ check }: { check: CheckResult }) {
  const opportunities =
    check.id === 'pagespeed_opportunities' && Array.isArray(check.value)
      ? (check.value as PsiOpportunity[])
      : null
  const detail =
    opportunities || SELF_DESCRIBING.has(check.id) ? null : renderValue(check.value)

  return (
    <Finding
      status={check.status}
      label={check.label}
      badges={<StatusPill status={check.status} />}
      message={check.message}
      trailing={check.status === 'info' ? '—' : check.score}
    >
      {detail ? <FindingDetail>{detail}</FindingDetail> : null}
      {opportunities && opportunities.length > 0 ? (
        <OpportunityList items={opportunities} />
      ) : null}
      {check.recommendation ? <FindingFix>{check.recommendation}</FindingFix> : null}
    </Finding>
  )
}

/** Re-exported so views that show a single score can match the report's palette. */
export { scoreColor }
