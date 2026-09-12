/** Session state: who is signed in, and how to sign in or out. */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { onSessionEnded } from '../api/client'
import { authApi } from '../api/endpoints'
import type { User } from '../api/types'
import { tokens } from './tokens'

interface AuthValue {
  user: User | null
  /** True until the stored session has been checked on first load. */
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  signup: (username: string, email: string, password: string) => Promise<void>
  logout: () => Promise<void>
  /** Re-read the signed-in user, after editing the profile for example. */
  refreshUser: () => Promise<void>
  isAdmin: boolean
}

const AuthContext = createContext<AuthValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  // Seeded from storage rather than always starting true. With no stored
  // session there is nothing to restore, so a visitor who was never signed in
  // renders the signed-out UI on the very first paint instead of flashing a
  // loading state and then swapping.
  const [loading, setLoading] = useState(() => tokens.hasSession)

  // Restore a session left in storage. The client renews the access token on
  // its own if it has expired, so one call to /auth/me settles it either way.
  useEffect(() => {
    let cancelled = false
    if (!tokens.hasSession) {
      setLoading(false)
      return
    }
    authApi
      .me()
      .then((me) => {
        if (!cancelled) setUser(me)
      })
      .catch(() => {
        if (!cancelled) {
          tokens.clear()
          setUser(null)
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  // The client tells us when a renewal failed, so the UI can drop back to the
  // sign-in screen instead of showing a signed-in shell with no data.
  useEffect(() => onSessionEnded(() => setUser(null)), [])

  const login = useCallback(async (email: string, password: string) => {
    const pair = await authApi.login(email, password)
    tokens.set(pair)
    setUser(await authApi.me())
  }, [])

  const signup = useCallback(
    async (username: string, email: string, password: string) => {
      await authApi.signup(username, email, password)
      const pair = await authApi.login(email, password)
      tokens.set(pair)
      setUser(await authApi.me())
    },
    [],
  )

  const refreshUser = useCallback(async () => {
    setUser(await authApi.me())
  }, [])

  const logout = useCallback(async () => {
    const refresh = tokens.refresh
    if (refresh) {
      // Revoke server-side, but never block sign-out on it failing.
      await authApi.logout(refresh).catch(() => undefined)
    }
    tokens.clear()
    setUser(null)
  }, [])

  const value = useMemo(
    () => ({
      user,
      loading,
      login,
      signup,
      logout,
      refreshUser,
      isAdmin: user?.role === 'admin',
    }),
    [user, loading, login, signup, logout, refreshUser],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthValue {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth must be used inside <AuthProvider>')
  return value
}
