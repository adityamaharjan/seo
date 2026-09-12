/**
 * The overall score, as a dial.
 *
 * Redesigned to be finer than it was: a hairline track, a 6px value arc with a
 * rounded cap, and the number set large and tight in the middle. The previous
 * version used a 9px stroke that read as a donut chart, which implied parts of
 * a whole when the number is really a single reading on a scale.
 *
 * The arc alone never carries the value. The number is inside it, the grade is
 * under that, and the whole thing exposes one text label to assistive tech.
 */
import type { CheckStatus } from '../api/types'
import { cn } from '@/lib/utils'

interface Props {
  score: number
  grade?: string | null
  size?: number
  stroke?: number
}

/** The band a score falls in. Drives colour everywhere a score is shown. */
export function scoreTone(score: number): Extract<CheckStatus, 'good' | 'warning' | 'critical'> {
  if (score >= 80) return 'good'
  if (score >= 60) return 'warning'
  return 'critical'
}

/** The same bands as a CSS colour, for SVG strokes and inline fills. */
export function scoreColor(score: number): string {
  return `var(--${scoreTone(score)})`
}

/** The same bands as a Tailwind text class. */
export function scoreTextClass(score: number): string {
  const tone = scoreTone(score)
  return tone === 'good' ? 'text-good' : tone === 'warning' ? 'text-warn' : 'text-crit'
}

export function ScoreRing({ score, grade, size = 112, stroke = 6 }: Props) {
  const clamped = Math.max(0, Math.min(100, Math.round(score)))
  const radius = (size - stroke) / 2
  const circumference = 2 * Math.PI * radius
  const offset = circumference * (1 - clamped / 100)

  return (
    <div
      className="relative grid flex-none place-items-center"
      style={{ width: size, height: size }}
      role="img"
      aria-label={`Overall score ${clamped} out of 100${grade ? `, grade ${grade}` : ''}`}
    >
      <svg width={size} height={size} className="-rotate-90" aria-hidden="true">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth={stroke}
          className="stroke-surface-2"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth={stroke}
          strokeLinecap="round"
          stroke={scoreColor(clamped)}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className="motion-safe:transition-[stroke-dashoffset] motion-safe:duration-700 motion-safe:ease-out"
        />
      </svg>
      <div className="absolute grid place-items-center leading-none">
        <div
          className="font-semibold tabular-nums tracking-[-0.04em]"
          style={{ fontSize: size * 0.3 }}
        >
          {clamped}
        </div>
        {grade ? (
          <div className="mt-1.5 text-[10.5px] font-semibold tracking-[0.1em] text-muted-foreground uppercase">
            Grade {grade}
          </div>
        ) : null}
      </div>
    </div>
  )
}

/**
 * A score and its grade in a table cell, coloured by the band it falls in.
 *
 * A report that has not finished has no score rather than a zero, so the null
 * case is an em dash and not a red 0, which would read as a real failing grade.
 */
export function ScoreCell({
  score,
  grade,
}: {
  score: number | null
  grade?: string | null
}) {
  if (score === null) return <span className="text-muted-foreground">—</span>
  return (
    <span className={cn('font-semibold tabular-nums', scoreTextClass(score))}>
      {score}
      {grade ? (
        <span className="ml-1 font-medium text-muted-foreground">{grade}</span>
      ) : null}
    </span>
  )
}
