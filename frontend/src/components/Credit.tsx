/**
 * Original-author credit. The project's LICENSE requires every hosted copy to
 * show it; you may add your own name beside it (as modifier or host), but not
 * remove it.
 */
export function Credit({ className }: { className?: string }) {
  return (
    <span className={className}>
      Created by{' '}
      <a
        href="https://github.com/adityamaharjan"
        target="_blank"
        rel="noopener"
        className="font-medium text-foreground underline-offset-4 hover:underline"
      >
        @adityamaharjan
      </a>
    </span>
  )
}
