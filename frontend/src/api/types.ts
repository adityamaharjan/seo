/**
 * Types mirroring docs/API.md. Kept hand-written rather than generated so the
 * shapes the UI actually depends on are visible in one place.
 */

export type CheckStatus = 'good' | 'warning' | 'critical' | 'info'
export type ReportStatus = 'pending' | 'running' | 'done' | 'failed'
export type UserRole = 'user' | 'admin'

export interface User {
  id: number
  username: string
  email: string
  role: UserRole
  is_active: boolean
  created_at: string
}

export interface TokenPair {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

export interface Quota {
  daily_limit: number
  used_today: number
  remaining_today: number
  day_reset_date: string
  monthly_limit: number
  used_this_month: number
  month_reset_date: string | null
}

export type ApiKeyProvider = 'google_psi'

/**
 * How much of a crawl gets a PageSpeed run. Each page costs roughly 10-30
 * seconds per strategy and one unit of the key's 25k/day quota, so on a large
 * crawl this is the difference between a short tail and a very long one.
 */
export type PsiScope = 'off' | 'homepage' | 'sample' | 'all'

export interface ApiKeyStatus {
  provider: ApiKeyProvider
  configured: boolean
  /** Last few characters only — the key itself is never returned. */
  key_hint: string | null
  last_used_at: string | null
  last_error: string | null
  updated_at: string | null
}

export interface ApiKeySettings {
  /** False when the server has no encryption key, so keys cannot be stored. */
  encryption_available: boolean
  providers: ApiKeyStatus[]
}

export interface AnalysisAccepted {
  id: number
  status: ReportStatus
  status_url: string
}

export interface ReportSummary {
  id: number
  url: string
  domain: string | null
  status: ReportStatus
  title: string | null
  target_keywords: string[] | null
  overall_score: number | null
  overall_grade: string | null
  /** Whether this run was enriched with Google PageSpeed Insights data. */
  used_psi: boolean
  created_at: string
}

/** One target keyword's placement result. */
export interface KeywordTargetResult {
  keyword: string
  score: number
  grade?: string
  /** Placement slot -> whether the phrase matched exactly or as an inflection. */
  found_in: Record<string, 'exact' | 'partial'>
  missing_from: string[]
  /** Slots this page cannot have at all, so they are not counted as misses. */
  not_applicable?: string[]
  density_pct: number
  over_used: boolean
}

/**
 * The keyword feature's own report. Scored separately from the page audit and
 * never folded into overall_score, so the same URL always scores the same.
 */
export interface KeywordReport {
  score: number
  grade: string
  status: CheckStatus
  message: string
  recommendation: string | null
  keywords: KeywordTargetResult[]
  /** Shipped by the API so the UI does not keep its own copy in sync. */
  placement_weights: Record<string, number>
  placement_labels: Record<string, string>
}

/** Legacy shape: keyword results used to live inside a check's `value`. */
export interface KeywordTargeting {
  average_score: number
  keywords: KeywordTargetResult[]
}

export interface Timing {
  ttfb_ms: number | null
  load_time_ms: number | null
  transfer_size_kb: number
  html_size_kb: number
  compressed: boolean
  redirect_count: number
}

export interface CategoryScore {
  category: string
  score: number
  grade: string
  weight: number
  checks: string[]
}

export interface CheckResult {
  id: string
  category: string
  status: CheckStatus
  score: number
  label: string
  value: unknown
  message: string
  recommendation: string | null
}

export type IssueCounts = Record<CheckStatus, number>

export interface SeoResult {
  id: string
  url: string
  final_url: string
  domain: string
  generated_at: string
  fetched_ok: boolean
  status_code: number | null
  overall_score: number
  overall_grade: string
  /** Absent on reports produced before capped scoring shipped. */
  uncapped_score?: number
  capped_by?: string[]
  /** Null unless the submitter named target keywords. */
  keyword_report?: KeywordReport | null
  issue_counts?: IssueCounts
  title?: string | null
  timing: Timing
  category_scores: CategoryScore[]
  checks: CheckResult[]
  /** PageSpeed runs by strategy; absent or null when PageSpeed did not run. */
  psi?: { strategies: Record<string, PsiRun>; error: string | null } | null
  error: string | null
}

/** One Lighthouse run, trimmed by the server to what the report shows. */
export interface PsiRun {
  scores: Partial<Record<'performance' | 'accessibility' | 'best-practices' | 'seo', number | null>>
  lab: {
    lcp_ms?: number
    cls?: number
    tbt_ms?: number
    fcp_ms?: number
    speed_index_ms?: number
  }
}

export interface ReportDetail extends ReportSummary {
  final_url: string | null
  job_id: string | null
  error: string | null
  ttfb_ms: number | null
  load_time_ms: number | null
  results: SeoResult | null
}

export interface UserQuotaSummary {
  daily_limit: number
  used_today: number
  monthly_limit: number
  used_this_month: number
  day_reset_date: string | null
}

export interface UserDetail extends User {
  updated_at: string
  report_count: number
  quota: UserQuotaSummary | null
}

export interface SessionsRevoked {
  revoked: number
}

export interface Paginated<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

/** The `details` payload of a 422 validation_error. */
export interface FieldError {
  type: string
  loc: string[]
  msg: string
  input?: unknown
}

export interface ApiErrorBody {
  error: {
    code: string
    message: string
    details?: unknown
  }
}


// --- Site audit: a multi-page crawl, separate from single-page analysis ---

export type SiteAuditStatus = ReportStatus

export interface SiteAuditSummary {
  id: number
  start_url: string
  domain: string | null
  status: SiteAuditStatus
  max_pages: number
  pages_crawled: number
  pages_failed: number
  /** "sitemap", "links" or "mixed": how the page list was found. */
  discovery_source: string | null
  overall_score: number | null
  overall_grade: string | null
  used_psi: boolean
  psi_scope: PsiScope | null
  created_at: string
}

export interface SiteAuditPageSummary {
  id: number
  url: string
  final_url: string | null
  title: string | null
  status_code: number | null
  overall_score: number | null
  overall_grade: string | null
  ttfb_ms: number | null
  load_time_ms: number | null
  issue_counts: IssueCounts | null
  error: string | null
}

export interface SiteAuditPageDetail extends SiteAuditPageSummary {
  audit_id: number
  /** The same payload a single-page report carries. */
  results: SeoResult | null
}

/** One problem, counted across every page the crawl covered. */
export interface SiteIssue {
  id: string
  label: string
  category: string
  status: CheckStatus
  recommendation: string | null
  affected_pages: number
  total_pages: number
  /** True when it hits at least half the site, i.e. a template-level fault. */
  sitewide: boolean
  example_urls: string[]
}

export interface SiteAuditResults {
  id: string
  start_url: string
  domain: string
  generated_at: string
  discovery_source: string
  pages_crawled: number
  pages_failed: number
  overall_score: number
  overall_grade: string
  score_spread: { min: number; max: number; median: number }
  issue_counts: IssueCounts
  category_scores: Omit<CategoryScore, 'checks'>[]
  top_issues: SiteIssue[]
  worst_pages: { url: string; title: string | null; score: number; grade: string }[]
  capped_pages: { url: string; score: number; capped_by: string[] }[]
  /** Pages that got a PageSpeed run, slowest first. Absent on older audits. */
  pagespeed?: {
    url: string
    title: string | null
    performance: number | null
    desktop_performance: number | null
    vitals_status: CheckStatus | null
    lcp_ms: number | null
    cls: number | null
    tbt_ms: number | null
  }[]
  errors: { url: string; error: string | null }[]
}

export interface SiteAuditDetail extends SiteAuditSummary {
  job_id: string | null
  error: string | null
  results: SiteAuditResults | null
  pages: SiteAuditPageSummary[]
}

export interface SiteAuditAccepted {
  id: number
  status: SiteAuditStatus
  status_url: string
  max_pages: number
}
