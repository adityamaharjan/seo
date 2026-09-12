/**
 * Which of the two palettes the app is wearing, and who decided.
 *
 * Three choices, not two. "System" is the default and is a real choice rather
 * than the absence of one: it keeps following the OS after the user has picked
 * it, so someone whose machine turns dark at sunset gets that without visiting
 * this menu twice a day. Light and dark are explicit overrides and outrank the
 * OS until they are cleared.
 *
 * The class on <html> is written by the small script in index.html before the
 * first paint, so this module's only job at startup is to agree with what is
 * already on screen. Rewriting it here would be a frame late and would show as
 * a flash of the wrong palette.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

export type ThemeChoice = 'light' | 'dark' | 'system'
export type ResolvedTheme = 'light' | 'dark'

/** Shared with the inline script in index.html; changing one means both. */
const STORAGE_KEY = 'seo-theme'

const DARK_QUERY = '(prefers-color-scheme: dark)'

function readStored(): ThemeChoice {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved === 'light' || saved === 'dark' || saved === 'system') return saved
  } catch {
    // Private windows and blocked site data both throw here. Neither is a
    // reason to fail to render, so fall through to following the OS.
  }
  return 'system'
}

function apply(resolved: ResolvedTheme) {
  const root = document.documentElement
  root.classList.toggle('dark', resolved === 'dark')
  // The address bar on mobile is painted from this, and a light chrome above a
  // dark page is the one seam a theme class cannot cover.
  document
    .querySelector('meta[name="theme-color"]')
    ?.setAttribute('content', resolved === 'dark' ? '#0b0b0e' : '#ffffff')
}

interface ThemeValue {
  /** What the user chose, including "system". */
  theme: ThemeChoice
  /** What that resolves to right now — never "system". */
  resolved: ResolvedTheme
  setTheme: (next: ThemeChoice) => void
}

const ThemeContext = createContext<ThemeValue | null>(null)

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<ThemeChoice>(readStored)
  const [systemIsDark, setSystemIsDark] = useState(
    () => typeof window !== 'undefined' && window.matchMedia(DARK_QUERY).matches,
  )

  // Follow the OS while the choice is "system". The listener stays attached for
  // the other two so switching back to "system" is immediately correct.
  useEffect(() => {
    const media = window.matchMedia(DARK_QUERY)
    const onChange = (event: MediaQueryListEvent) => setSystemIsDark(event.matches)
    media.addEventListener('change', onChange)
    return () => media.removeEventListener('change', onChange)
  }, [])

  const resolved: ResolvedTheme =
    theme === 'system' ? (systemIsDark ? 'dark' : 'light') : theme

  useEffect(() => {
    apply(resolved)
  }, [resolved])

  const setTheme = useCallback((next: ThemeChoice) => {
    setThemeState(next)
    try {
      localStorage.setItem(STORAGE_KEY, next)
    } catch {
      // The choice still applies to this tab; it just will not outlive it.
    }
  }, [])

  const value = useMemo(
    () => ({ theme, resolved, setTheme }),
    [theme, resolved, setTheme],
  )

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useTheme(): ThemeValue {
  const value = useContext(ThemeContext)
  if (!value) throw new Error('useTheme must be used inside ThemeProvider')
  return value
}

export { STORAGE_KEY as THEME_STORAGE_KEY }
