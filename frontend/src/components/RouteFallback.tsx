/**
 * What fills the window while a route's code is still being fetched.
 *
 * Deliberately almost nothing. On a warm connection the chunk lands inside a
 * frame or two and anything with structure — a skeleton header, placeholder
 * rows — would flash in and straight back out, which reads as a glitch rather
 * than as loading. A spinner that only appears once the wait is long enough to
 * notice is quieter than a layout that assembles itself twice.
 *
 * The delay is CSS, not state: an animation that spends its first 300ms fully
 * transparent costs nothing and cannot get stuck.
 */
export function RouteFallback() {
  return (
    <div
      className="grid min-h-dvh place-items-center"
      role="status"
      aria-live="polite"
    >
      <span className="sr-only">Loading</span>
      <span
        aria-hidden="true"
        className="size-5 rounded-full border-2 border-border-strong border-t-primary opacity-0 [animation:spin_0.7s_linear_infinite,fade-in_0.2s_ease-out_0.3s_forwards] motion-reduce:[animation:fade-in_0.2s_ease-out_0.3s_forwards]"
      />
    </div>
  )
}
