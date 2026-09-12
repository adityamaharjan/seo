/**
 * Fetch wrapper for the SEO Analysis API.
 *
 * Handles the shared error envelope, bearer auth, and transparent access-token
 * renewal. Refresh tokens are rotated server-side, so a refresh is single
 * flighted: concurrent 401s wait on one renewal rather than racing and
 * revoking each other's token.
 */
import { tokens } from '../auth/tokens'
import type { ApiErrorBody, FieldError, TokenPair } from './types'

const BASE = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/+$/, '')

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details: unknown
  readonly retryAfter: number | null

  constructor(
    status: number,
    code: string,
    message: string,
    details?: unknown,
    retryAfter?: number | null,
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
    this.retryAfter = retryAfter ?? null
  }

  /** Field name to message, for a 422 validation_error. */
  get fieldErrors(): Record<string, string> {
    if (this.code !== 'validation_error' || !Array.isArray(this.details)) return {}
    const out: Record<string, string> = {}
    for (const item of this.details as FieldError[]) {
      const field = item.loc?.filter((part) => part !== 'body').join('.') || '_'
      // Pydantic prefixes custom validator messages; the prefix adds nothing here.
      out[field] = (item.msg || '').replace(/^Value error,\s*/, '')
    }
    return out
  }

  /** True when the daily analysis allowance is spent, not a short-window limit. */
  get isQuotaExceeded() {
    return this.code === 'quota_exceeded'
  }

  get isRateLimited() {
    return this.code === 'rate_limited'
  }
}

interface RequestOptions {
  method?: string
  body?: unknown
  auth?: boolean
  signal?: AbortSignal
}

function isJson(response: Response): boolean {
  return (response.headers.get('content-type') || '').includes('application/json')
}

async function toApiError(response: Response): Promise<ApiError> {
  const retryAfterHeader = response.headers.get('retry-after')
  const retryAfter = retryAfterHeader ? Number(retryAfterHeader) : null

  if (isJson(response)) {
    try {
      const body = (await response.json()) as ApiErrorBody
      if (body?.error) {
        return new ApiError(
          response.status,
          body.error.code,
          body.error.message,
          body.error.details,
          retryAfter,
        )
      }
    } catch {
      /* fall through to the generic error below */
    }
  }
  return new ApiError(
    response.status,
    'http_error',
    `Request failed (${response.status} ${response.statusText}).`,
    undefined,
    retryAfter,
  )
}

let refreshInFlight: Promise<string> | null = null
type Listener = () => void
const sessionEndedListeners = new Set<Listener>()

/** Called when the session cannot be renewed and the user must sign in again. */
export function onSessionEnded(listener: Listener): () => void {
  sessionEndedListeners.add(listener)
  return () => sessionEndedListeners.delete(listener)
}

function endSession(): void {
  tokens.clear()
  sessionEndedListeners.forEach((listener) => listener())
}

async function renewAccessToken(): Promise<string> {
  if (refreshInFlight) return refreshInFlight

  refreshInFlight = (async () => {
    const refresh_token = tokens.refresh
    if (!refresh_token) throw new ApiError(401, 'authentication_failed', 'Not signed in.')

    const response = await fetch(`${BASE}/auth/refresh`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ refresh_token }),
    })
    if (!response.ok) {
      endSession()
      throw await toApiError(response)
    }
    const pair = (await response.json()) as TokenPair
    tokens.set(pair)
    return pair.access_token
  })().finally(() => {
    refreshInFlight = null
  })

  return refreshInFlight
}

async function send(path: string, options: RequestOptions, accessToken: string | null) {
  const headers: Record<string, string> = {}
  if (options.body !== undefined) headers['content-type'] = 'application/json'
  if (accessToken) headers.authorization = `Bearer ${accessToken}`

  return fetch(`${BASE}${path}`, {
    method: options.method || 'GET',
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
    signal: options.signal,
  })
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const useAuth = options.auth !== false

  let response: Response
  try {
    response = await send(path, options, useAuth ? tokens.access : null)
  } catch (error) {
    if ((error as Error)?.name === 'AbortError') throw error
    throw new ApiError(0, 'network_error', 'Could not reach the API. Check your connection.')
  }

  // One transparent retry after renewing an expired access token.
  if (response.status === 401 && useAuth && tokens.refresh) {
    try {
      const fresh = await renewAccessToken()
      response = await send(path, options, fresh)
    } catch {
      endSession()
      throw new ApiError(401, 'authentication_failed', 'Your session expired. Please sign in again.')
    }
  }

  if (!response.ok) {
    const error = await toApiError(response)
    if (error.status === 401 && useAuth) endSession()
    throw error
  }

  if (response.status === 204) return undefined as T
  if (!isJson(response)) return undefined as T
  return (await response.json()) as T
}
