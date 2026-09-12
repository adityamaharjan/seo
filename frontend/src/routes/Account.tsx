import { useEffect, useState, type FormEvent } from 'react'
import { ApiError } from '../api/client'
import { accountApi, apiKeysApi } from '../api/endpoints'
import type { ApiKeySettings } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { Notice } from '../components/Notice'
import { formatDate } from '../lib/format'

const PSI_KEY_DOCS = 'https://developers.google.com/speed/docs/insights/v5/get-started'

export function Account() {
  const { user, refreshUser, logout } = useAuth()

  const [username, setUsername] = useState(user?.username ?? '')
  const [email, setEmail] = useState(user?.email ?? '')
  const [profileError, setProfileError] = useState<unknown>(null)
  const [profileDone, setProfileDone] = useState(false)
  const [savingProfile, setSavingProfile] = useState(false)

  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [passwordError, setPasswordError] = useState<unknown>(null)
  const [savingPassword, setSavingPassword] = useState(false)

  useEffect(() => {
    if (user) {
      setUsername(user.username)
      setEmail(user.email)
    }
  }, [user])

  const profileFieldErrors = profileError instanceof ApiError ? profileError.fieldErrors : {}
  const dirty = user ? username !== user.username || email !== user.email : false
  const mismatch = confirm.length > 0 && confirm !== next

  async function saveProfile(event: FormEvent) {
    event.preventDefault()
    if (!user) return
    setSavingProfile(true)
    setProfileError(null)
    setProfileDone(false)
    try {
      // Send only what actually changed; the API rejects an empty patch.
      const changes: { username?: string; email?: string } = {}
      if (username !== user.username) changes.username = username
      if (email !== user.email) changes.email = email
      await accountApi.updateProfile(changes)
      await refreshUser()
      setProfileDone(true)
    } catch (caught) {
      setProfileError(caught)
    } finally {
      setSavingProfile(false)
    }
  }

  async function savePassword(event: FormEvent) {
    event.preventDefault()
    if (next !== confirm) {
      setPasswordError(new Error('The two passwords do not match.'))
      return
    }
    setSavingPassword(true)
    setPasswordError(null)
    try {
      await accountApi.changePassword(current, next)
      // The API revokes every session, this one included, so sign out cleanly
      // rather than letting the next request fail on its own.
      await logout()
    } catch (caught) {
      setPasswordError(caught)
    } finally {
      setSavingPassword(false)
    }
  }

  return (
    <>
      <div className="card">
        <div className="card-title">Profile</div>
        <p className="card-sub">
          Member since {formatDate(user?.created_at)}
          {user?.role === 'admin' ? ' · administrator' : ''}
        </p>

        <Notice error={profileError} />
        {profileDone && !profileError ? (
          <Notice tone="info">Your profile has been updated.</Notice>
        ) : null}

        <form onSubmit={saveProfile} noValidate style={{ maxWidth: 420 }}>
          <div className="field">
            <label htmlFor="account-username">Username</label>
            <input
              id="account-username"
              value={username}
              minLength={3}
              maxLength={50}
              onChange={(e) => setUsername(e.target.value)}
              aria-invalid={Boolean(profileFieldErrors.username)}
            />
            {profileFieldErrors.username ? (
              <span className="error">{profileFieldErrors.username}</span>
            ) : null}
          </div>

          <div className="field">
            <label htmlFor="account-email">Email</label>
            <input
              id="account-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              aria-invalid={Boolean(profileFieldErrors.email)}
            />
            {profileFieldErrors.email ? (
              <span className="error">{profileFieldErrors.email}</span>
            ) : null}
          </div>

          <button type="submit" className="btn" disabled={savingProfile || !dirty}>
            {savingProfile ? <span className="spinner" /> : 'Save changes'}
          </button>
        </form>
      </div>

      <ApiKeysCard />

      <div className="card">
        <div className="card-title">Password</div>
        <p className="card-sub">
          Changing your password signs you out everywhere, including here.
        </p>

        <Notice error={passwordError} />

        <form onSubmit={savePassword} noValidate style={{ maxWidth: 420 }}>
          <div className="field">
            <label htmlFor="current-password">Current password</label>
            <input
              id="current-password"
              type="password"
              autoComplete="current-password"
              required
              value={current}
              onChange={(e) => setCurrent(e.target.value)}
            />
          </div>

          <div className="field">
            <label htmlFor="new-password">New password</label>
            <input
              id="new-password"
              type="password"
              autoComplete="new-password"
              required
              minLength={8}
              maxLength={128}
              value={next}
              onChange={(e) => setNext(e.target.value)}
            />
            <span className="hint">At least 8 characters.</span>
          </div>

          <div className="field">
            <label htmlFor="confirm-password">Confirm new password</label>
            <input
              id="confirm-password"
              type="password"
              autoComplete="new-password"
              required
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              aria-invalid={mismatch}
            />
            {mismatch ? (
              <span className="error">The two passwords do not match.</span>
            ) : null}
          </div>

          <button
            type="submit"
            className="btn"
            disabled={savingPassword || !current || !next || !confirm || mismatch}
          >
            {savingPassword ? <span className="spinner" /> : 'Change password'}
          </button>
        </form>
      </div>
    </>
  )
}

function ApiKeysCard() {
  const [settings, setSettings] = useState<ApiKeySettings | null>(null)
  const [key, setKey] = useState('')
  const [error, setError] = useState<unknown>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    let cancelled = false
    apiKeysApi
      .list()
      .then((loaded) => {
        if (!cancelled) setSettings(loaded)
      })
      .catch((caught) => {
        if (!cancelled) setError(caught)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const psi = settings?.providers.find((p) => p.provider === 'google_psi')
  const canStore = settings?.encryption_available ?? false

  async function save(event: FormEvent) {
    event.preventDefault()
    setSaving(true)
    setError(null)
    try {
      setSettings(await apiKeysApi.save('google_psi', key.trim()))
      setKey('')
    } catch (caught) {
      setError(caught)
    } finally {
      setSaving(false)
    }
  }

  async function remove() {
    setError(null)
    try {
      await apiKeysApi.remove('google_psi')
      setSettings(await apiKeysApi.list())
    } catch (caught) {
      setError(caught)
    }
  }

  return (
    <div className="card">
      <div className="card-title">API keys</div>
      <p className="card-sub">
        Core Web Vitals come from Google PageSpeed Insights, which needs your own
        API key. It is free — 25,000 requests a day — and is stored encrypted.{' '}
        <a href={PSI_KEY_DOCS} target="_blank" rel="noreferrer">
          How to get a key
        </a>
        .
      </p>

      <Notice error={error} />
      {settings && !canStore ? (
        <Notice tone="warning">
          This server cannot store API keys yet — the operator needs to set{' '}
          <code>API_KEY_ENCRYPTION_KEY</code>. Keys are never stored unencrypted.
        </Notice>
      ) : null}
      {psi?.last_error ? (
        <Notice tone="warning">
          Google last rejected this key: {psi.last_error}
        </Notice>
      ) : null}

      {psi?.configured ? (
        <div className="field" style={{ maxWidth: 420 }}>
          <span className="hint">
            Key ending <strong>…{psi.key_hint}</strong> saved
            {psi.last_used_at ? ` · last used ${formatDate(psi.last_used_at)}` : ''}
          </span>
          <button type="button" className="btn ghost" onClick={remove}>
            Remove key
          </button>
        </div>
      ) : (
        <form onSubmit={save} noValidate style={{ maxWidth: 420 }}>
          <div className="field">
            <label htmlFor="psi-key">PageSpeed Insights API key</label>
            <input
              id="psi-key"
              type="password"
              autoComplete="off"
              placeholder="AIza…"
              value={key}
              onChange={(e) => setKey(e.target.value)}
              disabled={!canStore}
            />
            <span className="hint">Checked with Google before it is saved.</span>
          </div>
          <button type="submit" className="btn" disabled={saving || !key.trim() || !canStore}>
            {saving ? <span className="spinner" /> : 'Save key'}
          </button>
        </form>
      )}
    </div>
  )
}
