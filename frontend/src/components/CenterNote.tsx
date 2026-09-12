import type { ReactNode } from 'react'
import { Spinner } from './Spinner'

/**
 * A single line of "wait here", centred in whatever space is going.
 *
 * It lives in its own module rather than beside the other report states so the
 * route guards can use it without dragging the report's alerts, panels and
 * status pills into the entry bundle. Guards run on the first paint of every
 * signed-in session; the report does not.
 */
export function CenterNote({ children }: { children: ReactNode }) {
  return (
    <div
      className="grid min-h-[55vh] place-items-center gap-3 text-center text-muted-foreground"
      role="status"
      aria-live="polite"
    >
      <span className="flex items-center gap-2.5 text-[14px]">
        <Spinner />
        {children}
      </span>
    </div>
  )
}
