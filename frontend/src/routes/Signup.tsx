import { useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { ApiError } from '../api/client'
import { Notice } from '../components/Notice'
import { AuthShell } from '../components/AuthShell'
import { TextField } from '../components/Field'
import { Spinner } from '../components/Spinner'
import { useAuth } from '../auth/AuthContext'
import { Button } from '@/components/ui/button'

export function Signup() {
  const { user, loading, signup } = useAuth()
  const navigate = useNavigate()
  // A URL typed on the landing page rides along as ?url= so the audit form
  // arrives prefilled instead of asking for it twice.
  const { search } = useLocation()
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)

  if (!loading && user) return <Navigate to={`/app${search}`} replace />

  const fieldErrors = error instanceof ApiError ? error.fieldErrors : {}

  // Only complain once they have started typing the confirmation, so the
  // form does not shout at someone who is still filling it in.
  const mismatch = confirm.length > 0 && confirm !== password
  const canSubmit = Boolean(username && email && password && confirm) && !mismatch

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (password !== confirm) {
      setError(new Error('The two passwords do not match.'))
      return
    }
    setBusy(true)
    setError(null)
    try {
      await signup(username, email, password)
      navigate(`/app${search}`, { replace: true })
    } catch (caught) {
      setError(caught)
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthShell
      title="Create an account"
      lede="Five free analyses every day. No card required."
      footer={
        <>
          Already registered?{' '}
          <Link
            to="/login"
            className="font-medium text-accent-on-tint underline-offset-4 hover:underline"
          >
            Sign in
          </Link>
        </>
      }
    >
      <Notice error={error} className="mb-4" />
      <form onSubmit={handleSubmit} noValidate className="grid gap-4">
        <TextField
          id="username"
          label="Username"
          autoComplete="username"
          required
          minLength={3}
          maxLength={50}
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          error={fieldErrors.username}
          hint="3 to 50 characters."
        />
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
          autoComplete="new-password"
          required
          minLength={8}
          maxLength={128}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          error={fieldErrors.password}
          hint="At least 8 characters."
        />
        <TextField
          id="confirm"
          label="Confirm password"
          type="password"
          autoComplete="new-password"
          required
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          error={mismatch ? 'The two passwords do not match.' : undefined}
        />
        <Button
          type="submit"
          disabled={busy || !canSubmit}
          className="mt-1 h-10 w-full"
        >
          {busy ? (
            <>
              <Spinner />
              Creating account
            </>
          ) : (
            'Create account'
          )}
        </Button>
      </form>
    </AuthShell>
  )
}
