/**
 * The "use PageSpeed Insights" control, shared by the page and site audit forms.
 *
 * PageSpeed data is opt-out rather than opt-in once a key is saved: someone who
 * went to the trouble of adding a key wants the data, and making them tick a box
 * every time would be a tax on their own setup. The control exists so they can
 * skip it on a run where the extra 20-30 seconds is not worth it.
 *
 * With no key stored, the control is disabled and says where to get one instead
 * of quietly disappearing — an absent option looks like a missing feature.
 */
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Gauge } from 'lucide-react'
import { apiKeysApi } from '../api/endpoints'
import type { PsiScope } from '../api/types'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

export interface PsiKeyState {
  /** Null while loading, so the control can hold its shape instead of flicking. */
  configured: boolean | null
  hint: string | null
  error: string | null
}

/** Whether this account has a usable PageSpeed key, for gating the control. */
export function usePsiKey(): PsiKeyState {
  const [state, setState] = useState<PsiKeyState>({
    configured: null,
    hint: null,
    error: null,
  })

  useEffect(() => {
    let cancelled = false
    apiKeysApi
      .list()
      .then((settings) => {
        if (cancelled) return
        const psi = settings.providers.find((p) => p.provider === 'google_psi')
        setState({
          configured: Boolean(psi?.configured),
          hint: psi?.key_hint ?? null,
          error: psi?.last_error ?? null,
        })
      })
      // A failed lookup must not block submitting. Treating it as "no key"
      // means the run goes ahead without PageSpeed rather than not at all.
      .catch(() => {
        if (!cancelled) setState({ configured: false, hint: null, error: null })
      })
    return () => {
      cancelled = true
    }
  }, [])

  return state
}

const SCOPE_LABELS: Record<PsiScope, string> = {
  off: 'No pages',
  homepage: 'Homepage only',
  sample: 'First 5 pages',
  all: 'Every crawled page',
}

interface PsiOptionProps {
  keyState: PsiKeyState
  enabled: boolean
  onEnabledChange: (enabled: boolean) => void
  disabled?: boolean
  /** Supplied by the site audit only; the page audit has a single page. */
  scope?: PsiScope
  onScopeChange?: (scope: PsiScope) => void
  /** Drives the time estimate shown against the chosen scope. */
  maxPages?: number
}

/** Rough cost of one Lighthouse run, in seconds. */
const SECONDS_PER_RUN = 25
/** Mirror the server's PSI_STRATEGIES (mobile, desktop) and PSI_CONCURRENCY defaults. */
const RUNS_PER_PAGE = 2
const PARALLEL_RUNS = 6

export function estimate(scope: PsiScope, maxPages: number): string {
  const pages =
    scope === 'all' ? maxPages : scope === 'sample' ? Math.min(5, maxPages) : 1
  const seconds = Math.ceil((pages * RUNS_PER_PAGE) / PARALLEL_RUNS) * SECONDS_PER_RUN
  if (seconds < 90) return `about ${seconds} seconds`
  return `about ${Math.round(seconds / 60)} minutes`
}

export function PsiOption({
  keyState,
  enabled,
  onEnabledChange,
  disabled = false,
  scope,
  onScopeChange,
  maxPages = 1,
}: PsiOptionProps) {
  const hasKey = keyState.configured === true
  const checked = hasKey && enabled
  const showScope = scope !== undefined && onScopeChange !== undefined

  return (
    <div className="grid gap-1.5">
      <div className="flex items-start gap-2.5">
        <input
          id="use-psi"
          type="checkbox"
          checked={checked}
          disabled={disabled || !hasKey}
          onChange={(e) => onEnabledChange(e.target.checked)}
          aria-describedby="use-psi-hint"
          className="mt-0.5 size-4 shrink-0 cursor-pointer rounded border-input accent-[var(--accent)] disabled:cursor-not-allowed disabled:opacity-50"
        />
        <div className="grid gap-1.5">
          <Label
            htmlFor="use-psi"
            className={`cursor-pointer ${!hasKey ? 'opacity-60' : ''}`}
          >
            <Gauge className="size-3.5 text-muted-foreground" aria-hidden="true" />
            Measure Core Web Vitals with PageSpeed Insights
          </Label>

          {showScope && checked ? (
            <div className="flex flex-wrap items-center gap-2">
              <Select
                value={scope}
                onValueChange={(next) => onScopeChange(next as PsiScope)}
                disabled={disabled}
              >
                <SelectTrigger className="h-8 w-[190px]" aria-label="PageSpeed coverage">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {(['homepage', 'sample', 'all'] as const).map((value) => (
                    <SelectItem key={value} value={value}>
                      {SCOPE_LABELS[value]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <span className="text-[12.5px] text-muted-foreground">
                adds {estimate(scope, maxPages)}
              </span>
            </div>
          ) : null}

          <p id="use-psi-hint" className="text-[12.5px] text-muted-foreground">
            {keyState.configured === null ? (
              'Checking for a saved key…'
            ) : hasKey ? (
              <>
                Runs Google&rsquo;s real Lighthouse test on mobile and desktop for
                LCP, CLS and INP, plus what real Chrome users experienced. Uses your
                saved key
                {keyState.hint ? ` ending …${keyState.hint}` : ''}.
              </>
            ) : (
              <>
                Needs a free Google PageSpeed API key.{' '}
                <Link
                  to="/account"
                  className="font-medium text-accent-on-tint underline-offset-4 hover:underline"
                >
                  Add one in Account
                </Link>{' '}
                to measure Core Web Vitals.
              </>
            )}
          </p>
        </div>
      </div>
    </div>
  )
}
