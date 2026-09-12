/** Small presentation helpers shared across the views. */

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatMs(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return '—'
  if (ms < 1000) return `${Math.round(ms)} ms`
  return `${(ms / 1000).toFixed(2)} s`
}

export function formatKb(kb: number | null | undefined): string {
  if (kb === null || kb === undefined) return '—'
  if (kb < 1024) return `${kb.toFixed(1)} KB`
  return `${(kb / 1024).toFixed(2)} MB`
}

/** "https://example.com/path" -> "example.com/path", for compact display. */
export function shortUrl(url: string, max = 52): string {
  const trimmed = url.replace(/^https?:\/\//, '').replace(/\/$/, '')
  return trimmed.length > max ? `${trimmed.slice(0, max - 1)}…` : trimmed
}

export function titleCase(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1)
}

const CATEGORY_LABELS: Record<string, string> = {
  meta: 'Meta',
  content: 'Content',
  structure: 'Structure',
  links: 'Links',
  indexability: 'Indexability',
  performance: 'Performance',
  security: 'Security',
  mobile: 'Mobile',
}

export function categoryLabel(category: string): string {
  return CATEGORY_LABELS[category] ?? titleCase(category)
}

/** Render a check's freeform `value` as something a person can read. */
export function renderValue(value: unknown): string | null {
  if (value === null || value === undefined) return null
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (typeof value === 'number') return String(value)
  if (typeof value === 'string') return value.length > 220 ? `${value.slice(0, 219)}…` : value
  if (Array.isArray(value)) {
    if (value.length === 0) return null
    return value.slice(0, 8).map(String).join(', ') + (value.length > 8 ? ` (+${value.length - 8} more)` : '')
  }
  if (typeof value === 'object') {
    const entries = Object.entries(value as Record<string, unknown>)
      .filter(([, v]) => v !== null && v !== undefined && v !== '')
      .slice(0, 6)
      .map(([k, v]) => `${k.replace(/_/g, ' ')}: ${typeof v === 'object' ? JSON.stringify(v) : String(v)}`)
    return entries.length ? entries.join(' · ') : null
  }
  return null
}

/** Seconds until a quota reset, phrased for a person. */
export function untilReset(iso: string | null | undefined): string {
  if (!iso) return 'tomorrow'
  const target = new Date(iso).getTime()
  if (Number.isNaN(target)) return 'tomorrow'
  const seconds = Math.max(0, Math.round((target - Date.now()) / 1000))
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  if (hours > 0) return `in ${hours}h ${minutes}m`
  if (minutes > 0) return `in ${minutes}m`
  return 'shortly'
}
