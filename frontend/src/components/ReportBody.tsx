/**
 * Renders one analyzed page: score, timings, keyword targeting, categories and
 * every check.
 *
 * Shared by the single-page report and by one page inside a site audit. Both
 * carry the identical `SeoResult` payload, so the site audit gets the full
 * report view for free rather than a second, thinner rendering of the same data.
 */
import { useMemo, useRef, useState, type ReactNode } from 'react'
import type {
  CheckResult,
  CheckStatus,
  KeywordReport,
  SeoResult,
} from '../api/types'
import { Notice } from './Notice'
import { ScoreRing, scoreColor } from './ScoreRing'
import { StatusPill } from './StatusPill'
import { categoryLabel, formatDate, formatKb, formatMs, renderValue } from '../lib/format'

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
      <div className="card">
        <div className="report-head">
          <ScoreRing score={results.overall_score} grade={results.overall_grade} />
          <div className="meta">
            <h1>{results.title || results.domain}</h1>
            <div className="url">
              <a href={results.final_url} target="_blank" rel="noreferrer nofollow">
                {results.final_url}
              </a>
            </div>
            <div style={{ marginTop: 10, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {badge}
              {(targetKeywords ?? []).map((keyword) => (
                <span className="pill info" key={keyword}>
                  {keyword}
                </span>
              ))}
            </div>
            <div className="issue-summary">
              <button
                type="button"
                className="issue-stat critical"
                onClick={() => focusChecks('critical')}
                disabled={counts.critical === 0}
              >
                <span className="n">{counts.critical}</span> critical
              </button>
              <button
                type="button"
                className="issue-stat warning"
                onClick={() => focusChecks('warning')}
                disabled={counts.warning === 0}
              >
                <span className="n">{counts.warning}</span>{' '}
                {counts.warning === 1 ? 'warning' : 'warnings'}
              </button>
              <span className="issue-stat good">
                <span className="n">{counts.good}</span> passed
              </span>
            </div>
            <div className="url" style={{ marginTop: 10 }}>
              Analyzed {formatDate(results.generated_at)}
            </div>
          </div>
        </div>

        {capReasons.length > 0 ? (
          <Notice tone="warning">
            <strong>Score capped at {results.overall_score}.</strong>{' '}
            {capReasons.join(' ')}
            {results.uncapped_score === undefined
              ? null
              : ` Fixing that alone would take this page to ${results.uncapped_score}.`}
          </Notice>
        ) : null}

        <div className="stat-grid">
          <div className="stat">
            <div className="label">TTFB</div>
            <div className="value">{formatMs(results.timing.ttfb_ms)}</div>
          </div>
          <div className="stat">
            <div className="label">Load time</div>
            <div className="value">{formatMs(results.timing.load_time_ms)}</div>
          </div>
          <div className="stat">
            <div className="label">Page size</div>
            <div className="value">{formatKb(results.timing.html_size_kb)}</div>
          </div>
          <div className="stat">
            <div className="label">Transferred</div>
            <div className="value">{formatKb(results.timing.transfer_size_kb)}</div>
          </div>
          <div className="stat">
            <div className="label">HTTP</div>
            <div className="value">{results.status_code ?? '—'}</div>
          </div>
          <div className="stat">
            <div className="label">Redirects</div>
            <div className="value">{results.timing.redirect_count}</div>
          </div>
          <div className="stat">
            <div className="label">Compressed</div>
            <div className="value">{results.timing.compressed ? 'Yes' : 'No'}</div>
          </div>
        </div>
      </div>

      {keywords ? <KeywordReportCard report={keywords} /> : null}

      <div className="card">
        <div className="section-head">
          <h2>Category scores</h2>
          <span className="quota-text">Weighted into the overall score</span>
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

      <div className="card" ref={checksRef}>
        <div className="section-head">
          <h2>Checks</h2>
        </div>

        <div className="filters">
          <button
            type="button"
            className={`filter${filter === 'all' ? ' on' : ''}`}
            onClick={() => setFilter('all')}
          >
            All <span className="count">{counts.all}</span>
          </button>
          {STATUS_ORDER.map((status) => (
            <button
              key={status}
              type="button"
              className={`filter${filter === status ? ' on' : ''}`}
              onClick={() => setFilter(status)}
              disabled={counts[status] === 0}
            >
              {status} <span className="count">{counts[status]}</span>
            </button>
          ))}
        </div>

        {grouped.length === 0 ? (
          <div className="empty">Nothing matches that filter.</div>
        ) : (
          grouped.map(([category, checks]) => (
            <div className="check-group" key={category}>
              <h3>{categoryLabel(category)}</h3>
              <div className="check-list">
                {checks.map((check) => (
                  <CheckRow key={check.id} check={check} />
                ))}
              </div>
            </div>
          ))
        )}
      </div>
    </>
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

function KeywordReportCard({ report }: { report: KeywordReport }) {
  const slots = Object.keys(report.placement_weights).length
    ? Object.keys(report.placement_weights)
    : Object.keys(FALLBACK_PLACEMENTS)
  const label = (slot: string) =>
    report.placement_labels[slot] ?? FALLBACK_PLACEMENTS[slot] ?? slot

  return (
    <div className="card">
      <div className="section-head">
        <h2>Keyword targeting</h2>
        <span className="quota-text">Scored separately from the page score</span>
      </div>
      <p className="card-sub">
        {report.message} Placement is what this measures, so it does not change the
        page score above.
      </p>

      <div className="keyword-list">
        {report.keywords.map((result) => (
          <div className="keyword-row" key={result.keyword}>
            <div className="keyword-head">
              <span className="keyword-name">{result.keyword}</span>
              <span className="keyword-score" style={{ color: scoreColor(result.score) }}>
                {result.score}
              </span>
            </div>

            <div className="placement-grid">
              {slots.map((slot) => {
                const match = result.found_in[slot]
                const absent = result.not_applicable?.includes(slot)
                return (
                  <span
                    key={slot}
                    className={`placement ${absent ? 'na' : (match ?? 'missing')}`}
                    title={
                      absent
                        ? 'This page has no such element, so it is not counted'
                        : match === 'exact'
                          ? 'Exact phrase'
                          : match === 'partial'
                            ? 'Close variant'
                            : 'Not found'
                    }
                  >
                    {label(slot)}
                  </span>
                )
              })}
            </div>

            <div className="url">
              Density {result.density_pct}%
              {result.over_used ? ' · repeated too often' : ''}
            </div>
          </div>
        ))}
      </div>

      {report.recommendation ? (
        <div className="rec" style={{ marginTop: 14 }}>
          <b>Fix:</b> {report.recommendation}
        </div>
      ) : null}
    </div>
  )
}

function CheckRow({ check }: { check: CheckResult }) {
  const detail = renderValue(check.value)
  return (
    <div className={`check ${check.status}`}>
      <div className="bar" />
      <div className="body">
        <div className="head">
          <span className="label">{check.label}</span>
          <StatusPill status={check.status} />
        </div>
        <div className="message">{check.message}</div>
        {detail ? <div className="detail">{detail}</div> : null}
        {check.recommendation ? (
          <div className="rec">
            <b>Fix:</b> {check.recommendation}
          </div>
        ) : null}
      </div>
      <div className="score">{check.status === 'info' ? '—' : check.score}</div>
    </div>
  )
}
