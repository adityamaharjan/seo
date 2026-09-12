import type { ReactNode } from 'react'
import { Lock } from 'lucide-react'
import { useAuth } from '../auth/AuthContext'
import { EmptyState } from './Page'
import { CenterNote } from './ReportStates'

export function RequireAdmin({ children }: { children: ReactNode }) {
  const { isAdmin, loading } = useAuth()

  if (loading) {
    return <CenterNote>Checking your permissions…</CenterNote>
  }
  if (!isAdmin) {
    // Deliberately not a redirect: the person is signed in, they simply are
    // not allowed here, and saying so is clearer than bouncing them.
    return (
      <div className="mt-10">
        <EmptyState icon={<Lock className="size-5" />} title="Not available">
          This area is for administrators.
        </EmptyState>
      </div>
    )
  }
  return <>{children}</>
}
