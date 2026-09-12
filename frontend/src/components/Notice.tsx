import type { ReactNode } from 'react'
import { ApiError } from '../api/client'
import { untilReset } from '../lib/format'

/**
 * Turns an unknown thrown value into one line a person can act on. The API's
 * error codes carry more meaning than the HTTP status, so they drive the copy.
 */
export function errorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) {
    return error instanceof Error ? error.message : 'Something went wrong.'
  }

  if (error.isQuotaExceeded) {
    const details = error.details as { resets_at?: string; daily_limit?: number } | undefined
    const limit = details?.daily_limit
    return `You have used all ${limit ?? ''} of your free analyses for today. More ${untilReset(details?.resets_at)}.`.replace(
      /\s+/g,
      ' ',
    )
  }
  if (error.isRateLimited) {
    const wait = error.retryAfter ? `${Math.ceil(error.retryAfter / 60)} minute(s)` : 'a moment'
    return `Too many attempts. Try again in ${wait}.`
  }
  if (error.code === 'validation_error') {
    const fields = Object.values(error.fieldErrors)
    return fields.length ? fields.join(' ') : error.message
  }
  if (error.code === 'service_unavailable') {
    return 'The analysis queue is temporarily unavailable, so nothing was charged to your quota. Please try again shortly.'
  }
  if (error.code === 'conflict') {
    return error.message || 'That username or email is already taken.'
  }
  if (error.status === 401) {
    return error.message || 'Those credentials were not recognised.'
  }
  return error.message || 'Something went wrong.'
}

interface Props {
  error?: unknown
  tone?: 'error' | 'warning' | 'info'
  children?: ReactNode
}

export function Notice({ error, tone = 'error', children }: Props) {
  if (!error && !children) return null
  return (
    <div className={`notice ${tone}`} role={tone === 'error' ? 'alert' : 'status'}>
      {children ?? errorMessage(error)}
    </div>
  )
}
