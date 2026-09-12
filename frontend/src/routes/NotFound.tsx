import { Link } from 'react-router-dom'
import { Compass } from 'lucide-react'
import { EmptyState } from '../components/Page'
import { Button } from '@/components/ui/button'

export function NotFound() {
  return (
    <div className="mt-10">
      <EmptyState
        icon={<Compass className="size-5" />}
        title="Page not found"
        action={
          <Button asChild>
            <Link to="/app">Back to the page audit</Link>
          </Button>
        }
      >
        That address does not match anything here. It may have been deleted, or the
        link may be wrong.
      </EmptyState>
    </div>
  )
}
