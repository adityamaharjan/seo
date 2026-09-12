import { useEffect, useState, type FormEvent } from 'react'
import { ExternalLink } from 'lucide-react'
import { ApiError } from '../api/client'
import { accountApi, apiKeysApi } from '../api/endpoints'
import type { ApiKeySettings } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { Notice } from '../components/Notice'
import { TextField } from '../components/Field'
import { Spinner } from '../components/Spinner'
import { PageHeader, Panel, Section } from '../components/Page'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { formatDate } from '../lib/format'

const PSI_KEY_DOCS = 'https://developers.google.com/speed/docs/insights/v5/get-started'

/** Forms here are read left to right, not scanned, so they stay one column. */
const FORM_WIDTH = 'max-w-[420px]'

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
      <PageHeader
        title="Account"
        description={
          <>
            Member since {formatDate(user?.created_at)}
            {user?.role === 'admin' ? ' · administrator' : ''}
          </>
        }
      />

      <Section title="Profile">
        <Notice error={profileError} className="mb-4" />
        {profileDone && !profileError ? (
          <Notice tone="success" className="mb-4">
            Your profile has been updated.
          </Notice>
        ) : null}

        <form onSubmit={saveProfile} noValidate className={`grid gap-4 ${FORM_WIDTH}`}>
          <TextField
            id="account-username"
            label="Username"
            minLength={3}
            maxLength={50}
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            error={profileFieldErrors.username}
          />
          <TextField
            id="account-email"
            label="Email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            error={profileFieldErrors.email}
          />
          <div>
            <Button type="submit" disabled={savingProfile || !dirty}>
              {savingProfile ? (
                <>
                  <Spinner />
                  Saving
                </>
              ) : (
                'Save changes'
              )}
            </Button>
          </div>
        </form>
      </Section>

      <ApiKeysSection />

      <Section title="Password">
        <p className={`text-[13.5px] text-muted-foreground ${FORM_WIDTH}`}>
          Changing your password signs you out everywhere, including here.
        </p>

        <Notice error={passwordError} className="mt-4" />

        <form onSubmit={savePassword} noValidate className={`mt-4 grid gap-4 ${FORM_WIDTH}`}>
          <TextField
            id="current-password"
            label="Current password"
            type="password"
            autoComplete="current-password"
            required
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
          />
          <TextField
            id="new-password"
            label="New password"
            type="password"
            autoComplete="new-password"
            required
            minLength={8}
            maxLength={128}
            value={next}
            onChange={(e) => setNext(e.target.value)}
            hint="At least 8 characters."
          />
          <TextField
            id="confirm-password"
            label="Confirm new password"
            type="password"
            autoComplete="new-password"
            required
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            error={mismatch ? 'The two passwords do not match.' : undefined}
          />
          <div>
            <Button
              type="submit"
              disabled={savingPassword || !current || !next || !confirm || mismatch}
            >
              {savingPassword ? (
                <>
                  <Spinner />
                  Changing
                </>
              ) : (
                'Change password'
              )}
            </Button>
          </div>
        </form>
      </Section>
    </>
  )
}

function ApiKeysSection() {
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
    <Section title="API keys" meta="Stored encrypted">
      <p className="max-w-[62ch] text-[13.5px] leading-relaxed text-muted-foreground">
        Core Web Vitals come from Google PageSpeed Insights, which needs your own API
        key. It is free, at 25,000 requests a day.{' '}
        <a
          href={PSI_KEY_DOCS}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1 font-medium text-accent-on-tint underline-offset-4 hover:underline"
        >
          How to get a key
          <ExternalLink className="size-3.5" aria-hidden="true" />
        </a>
      </p>

      <Notice error={error} className="mt-4" />
      {settings && !canStore ? (
        <Notice tone="warning" className="mt-4">
          This server cannot store API keys yet — the operator needs to set{' '}
          <code className="rounded bg-code px-1 py-0.5 font-mono text-[12px]">
            API_KEY_ENCRYPTION_KEY
          </code>
          . Keys are never stored unencrypted.
        </Notice>
      ) : null}
      {psi?.last_error ? (
        <Notice tone="warning" className="mt-4">
          Google last rejected this key: {psi.last_error}
        </Notice>
      ) : null}

      {!settings && !error ? (
        <Skeleton className="mt-4 h-10 max-w-[420px]" />
      ) : psi?.configured ? (
        <Panel className={`mt-4 ${FORM_WIDTH}`}>
          <p className="text-[13.5px]">
            Key ending{' '}
            <strong className="font-mono font-semibold">…{psi.key_hint}</strong> saved
            {psi.last_used_at ? ` · last used ${formatDate(psi.last_used_at)}` : ''}
          </p>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={remove}
            className="mt-3.5"
          >
            Remove key
          </Button>
        </Panel>
      ) : (
        <form onSubmit={save} noValidate className={`mt-4 grid gap-4 ${FORM_WIDTH}`}>
          <TextField
            id="psi-key"
            label="PageSpeed Insights API key"
            type="password"
            autoComplete="off"
            placeholder="AIza…"
            value={key}
            onChange={(e) => setKey(e.target.value)}
            disabled={!canStore}
            hint="Checked with Google before it is saved."
          />
          <div>
            <Button type="submit" disabled={saving || !key.trim() || !canStore}>
              {saving ? (
                <>
                  <Spinner />
                  Saving
                </>
              ) : (
                'Save key'
              )}
            </Button>
          </div>
        </form>
      )}
    </Section>
  )
}
