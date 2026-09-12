/**
 * The two readouts both report views share: the counts under a score, and the
 * per-category meters.
 */
/**
 * Only the four fields a meter draws. A page report and a crawl report carry
 * category scores of slightly different shapes — the crawl's rows have no
 * per-category `checks` — and this component needs nothing either one is
 * missing, so it asks for the overlap rather than for either concrete type.
 */
interface CategoryReading {
  category: string
  score: number
  grade: string
  weight: number
}
import { scoreTextClass, scoreTone } from './ScoreRing'
import { Progress } from '@/components/ui/progress'
import { categoryLabel } from '../lib/format'
import { cn } from '@/lib/utils'

/**
 * One of the three counts under a score.
 *
 * Given `onSelect` it becomes a button that filters the list below; without one
 * it is static. Passed checks never get a handler, because there is nothing to
 * go and do about a check that passed. A count of zero stays visible and
 * disabled rather than disappearing, so the row keeps its shape between reports
 * and "0 critical" reads as the good news it is.
 */
export function CountChip({
  tone,
  count,
  label,
  onSelect,
}: {
  tone: 'critical' | 'warning' | 'good'
  count: number
  label: string
  onSelect?: () => void
}) {
  const palette = {
    critical: 'bg-crit-soft text-crit',
    warning: 'bg-warn-soft text-warn',
    good: 'bg-good-soft text-good',
  }[tone]

  const content = (
    <>
      <span className="text-[16px] leading-none font-semibold tabular-nums">{count}</span>
      <span className="text-[12.5px] font-medium">{label}</span>
    </>
  )

  const shared = cn('inline-flex items-baseline gap-1.5 rounded-full px-3 py-1.5', palette)

  if (!onSelect) return <span className={shared}>{content}</span>

  return (
    <button
      type="button"
      onClick={onSelect}
      disabled={count === 0}
      className={cn(
        shared,
        'border border-transparent transition-colors',
        'enabled:cursor-pointer enabled:hover:border-current',
        'disabled:opacity-55',
      )}
    >
      {content}
      <span className="sr-only">— show only these checks</span>
    </button>
  )
}

/**
 * Category scores as a list of meters.
 *
 * These were eight bordered boxes in a grid. They are eight readings on one
 * scale, and a list lets them be compared straight down a column instead of
 * hunted around a grid; the meter makes the comparison work without reading a
 * single number.
 */
export function CategoryMeters({
  categories,
}: {
  categories: readonly CategoryReading[]
}) {
  return (
    <div className="grid gap-x-12 sm:grid-cols-2">
      {categories.map((category) => (
        <div
          key={category.category}
          className="flex items-center gap-3 border-b border-border py-3 sm:gap-4"
        >
          <span className="w-24 shrink-0 text-[14px] font-medium">
            {categoryLabel(category.category)}
          </span>
          <Progress
            value={category.score}
            className="min-w-[60px] flex-1"
            indicatorClassName={
              scoreTone(category.score) === 'good'
                ? 'bg-good'
                : scoreTone(category.score) === 'warning'
                  ? 'bg-warn'
                  : 'bg-crit'
            }
            aria-label={`${categoryLabel(category.category)} score`}
          />
          <span
            className={cn(
              'w-7 shrink-0 text-right text-[14px] font-semibold tabular-nums',
              scoreTextClass(category.score),
            )}
          >
            {category.score}
          </span>
          <span className="w-16 shrink-0 text-right text-[12px] tabular-nums text-muted-foreground">
            {category.grade} · {Math.round(category.weight * 100)}%
          </span>
        </div>
      ))}
    </div>
  )
}

/** A bar showing one issue's share of the crawled pages. */
export function ShareMeter({
  share,
  tone,
  ariaLabel,
}: {
  share: number
  tone: 'critical' | 'warning'
  ariaLabel: string
}) {
  return (
    <Progress
      value={share}
      aria-label={ariaLabel}
      className="mt-2.5 max-w-[320px]"
      indicatorClassName={tone === 'critical' ? 'bg-crit' : 'bg-warn'}
    />
  )
}
