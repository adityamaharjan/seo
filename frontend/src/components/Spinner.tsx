import { cn } from '@/lib/utils'

/**
 * A busy indicator sized to the text beside it.
 *
 * It is `aria-hidden` on purpose. A spinner never carries the message on its
 * own here: every place one appears, the surrounding copy already says what is
 * happening, and that copy sits in the live region a screen reader announces.
 */
export function Spinner({ className }: { className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        'inline-block size-3.5 shrink-0 rounded-full border-2 border-current border-r-transparent align-[-2px] motion-safe:animate-[spin_0.7s_linear_infinite]',
        className,
      )}
    />
  )
}
