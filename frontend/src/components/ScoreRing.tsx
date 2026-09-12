/** Circular score gauge. Pure SVG, no chart library. */
interface Props {
  score: number
  grade?: string | null
  size?: number
  stroke?: number
}

export function scoreColor(score: number): string {
  if (score >= 80) return 'var(--good)'
  if (score >= 60) return 'var(--warning)'
  return 'var(--critical)'
}

export function ScoreRing({ score, grade, size = 116, stroke = 9 }: Props) {
  const clamped = Math.max(0, Math.min(100, Math.round(score)))
  const radius = (size - stroke) / 2
  const circumference = 2 * Math.PI * radius
  const offset = circumference * (1 - clamped / 100)

  return (
    <div
      className="ring"
      style={{ width: size, height: size }}
      role="img"
      aria-label={`Overall score ${clamped} out of 100${grade ? `, grade ${grade}` : ''}`}
    >
      <svg width={size} height={size}>
        <circle
          className="ring-track"
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth={stroke}
        />
        <circle
          className="ring-value"
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth={stroke}
          stroke={scoreColor(clamped)}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
        />
      </svg>
      <div className="inner">
        <div className="score">{clamped}</div>
        {grade ? <div className="grade">Grade {grade}</div> : null}
      </div>
    </div>
  )
}
