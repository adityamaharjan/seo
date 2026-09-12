import type { ReactNode } from 'react'
import { useAuth } from '../auth/AuthContext'

export function RequireAdmin({ children }: { children: ReactNode }) {
  const { isAdmin, loading } = useAuth()

  if (loading) {
    return (
      <div className="center-note">
        <span className="spinner" />
      </div>
    )
  }
  if (!isAdmin) {
    // Deliberately not a redirect: the person is signed in, they simply are
    // not allowed here, and saying so is clearer than bouncing them.
    return (
      <div className="center-note">
        <h2>Not available</h2>
        <p>This area is for administrators.</p>
      </div>
    )
  }
  return <>{children}</>
}
