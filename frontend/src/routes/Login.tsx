import { useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { ApiError } from '../api/client'
import { Notice } from '../components/Notice'
import { useAuth } from '../auth/AuthContext'

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
    <div className="auth-wrap">
      <div className="auth-card">
        <div className="auth-head">
          <div className="brand">
            <span className="dot" />
            SEO Analysis
          </div>
          <p>Sign in to analyze a page.</p>
        </div>

        <div className="card">
          <Notice error={error} />
          <form onSubmit={handleSubmit} noValidate>
            <div className="field">
              <label htmlFor="email">Email</label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                aria-invalid={Boolean(fieldErrors.email)}
              />
              {fieldErrors.email ? <span className="error">{fieldErrors.email}</span> : null}
            </div>

            <div className="field">
              <label htmlFor="password">Password</label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                aria-invalid={Boolean(fieldErrors.password)}
              />
              {fieldErrors.password ? <span className="error">{fieldErrors.password}</span> : null}
            </div>

            <button type="submit" className="btn block" disabled={busy}>
              {busy ? <span className="spinner" /> : 'Sign in'}
            </button>
          </form>
        </div>

        <p className="auth-alt">
          No account yet? <Link to="/signup">Create one</Link>
        </p>
      </div>
    </div>
  )
}
