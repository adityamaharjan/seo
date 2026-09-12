import { useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { ApiError } from '../api/client'
import { Notice } from '../components/Notice'
import { useAuth } from '../auth/AuthContext'

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
    <div className="auth-wrap">
      <div className="auth-card">
        <div className="auth-head">
          <div className="brand">
            <span className="dot" />
            SEO Analysis
          </div>
          <p>Create an account. Five free analyses every day.</p>
        </div>

        <div className="card">
          <Notice error={error} />
          <form onSubmit={handleSubmit} noValidate>
            <div className="field">
              <label htmlFor="username">Username</label>
              <input
                id="username"
                autoComplete="username"
                required
                minLength={3}
                maxLength={50}
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                aria-invalid={Boolean(fieldErrors.username)}
              />
              {fieldErrors.username ? (
                <span className="error">{fieldErrors.username}</span>
              ) : (
                <span className="hint">3 to 50 characters.</span>
              )}
            </div>

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
                autoComplete="new-password"
                required
                minLength={8}
                maxLength={128}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                aria-invalid={Boolean(fieldErrors.password)}
              />
              {fieldErrors.password ? (
                <span className="error">{fieldErrors.password}</span>
              ) : (
                <span className="hint">At least 8 characters.</span>
              )}
            </div>

            <div className="field">
              <label htmlFor="confirm">Confirm password</label>
              <input
                id="confirm"
                type="password"
                autoComplete="new-password"
                required
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                aria-invalid={mismatch}
                aria-describedby={mismatch ? 'confirm-error' : undefined}
              />
              {mismatch ? (
                <span className="error" id="confirm-error">
                  The two passwords do not match.
                </span>
              ) : null}
            </div>

            <button type="submit" className="btn block" disabled={busy || !canSubmit}>
              {busy ? <span className="spinner" /> : 'Create account'}
            </button>
          </form>
        </div>

        <p className="auth-alt">
          Already registered? <Link to="/login">Sign in</Link>
        </p>
      </div>
    </div>
  )
}
