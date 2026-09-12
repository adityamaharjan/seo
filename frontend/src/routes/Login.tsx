import { useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { ApiError } from '../api/client'
import { Notice } from '../components/Notice'
import { AuthShell } from '../components/AuthShell'
import { TextField } from '../components/Field'
import { Spinner } from '../components/Spinner'
import { useAuth } from '../auth/AuthContext'
import { Button } from '@/components/ui/button'

export function Login() {
  const { user, loading, login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)

  if (!loading && user) {
    const from = (location.state as { from?: string } | null)?.from
    return <Navigate to={from && from !== '/login' ? from : `/app${location.search}`} replace />
  }

  const fieldErrors = error instanceof ApiError ? error.fieldErrors : {}

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await login(email, password)
      const from = (location.state as { from?: string } | null)?.from
      navigate(from && from !== '/login' ? from : `/app${location.search}`, { replace: true })
    } catch (caught) {
      setError(caught)
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthShell
      title="Sign in"
      lede="Pick up where you left off."
      footer={
        <>
          No account yet?{' '}
          <Link
            to="/signup"
            className="font-medium text-accent-on-tint underline-offset-4 hover:underline"
          >
            Create one
          </Link>
        </>
      }
    >
      <Notice error={error} className="mb-4" />
      <form onSubmit={handleSubmit} noValidate className="grid gap-4">
        <TextField
          id="email"
          label="Email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          error={fieldErrors.email}
        />
        <TextField
          id="password"
          label="Password"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          error={fieldErrors.password}
        />
        <Button type="submit" disabled={busy} className="mt-1 h-10 w-full">
          {busy ? (
            <>
              <Spinner />
              Signing in
            </>
          ) : (
            'Sign in'
          )}
        </Button>
      </form>
    </AuthShell>
  )
}
