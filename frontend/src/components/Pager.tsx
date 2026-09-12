import { ChevronLeft, ChevronRight } from 'lucide-react'
import { Button } from '@/components/ui/button'

/**
 * Previous/next paging.
 *
 * The position is a real sentence rather than two bare numerals, and it sits in
 * a live region so moving between pages is announced to a screen reader, which
 * otherwise gets no feedback at all when the rows above silently change.
 */
export function Pager({
  page,
  totalPages,
  busy,
  onChange,
}: {
  page: number
  totalPages: number
  busy?: boolean
  onChange: (page: number) => void
}) {
  if (totalPages <= 1) return null
  return (
    <div className="mt-5 flex items-center justify-between gap-4">
      <p className="text-[13px] text-muted-foreground" role="status" aria-live="polite">
        Page <span className="tabular-nums">{page}</span> of{' '}
        <span className="tabular-nums">{totalPages}</span>
      </p>
      <div className="flex gap-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={page <= 1 || busy}
          onClick={() => onChange(Math.max(1, page - 1))}
        >
          <ChevronLeft />
          Previous
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={page >= totalPages || busy}
          onClick={() => onChange(page + 1)}
        >
          Next
          <ChevronRight />
        </Button>
      </div>
    </div>
  )
}
