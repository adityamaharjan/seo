/**
 * Token storage.
 *
 * Both tokens live in localStorage. This is a static single-page app with no
 * server of its own, so there is nowhere to keep an httpOnly cookie: any token
 * the app can use is a token script on the page can read. Keeping the access
 * token in memory only would not change that, since the refresh token beside it
 * mints new ones, so the simpler and more reliable option wins. The real
 * mitigations are the short access-token lifetime and refresh rotation, both of
 * which the API already enforces.
 */

const ACCESS_KEY = 'seo.access_token'
const REFRESH_KEY = 'seo.refresh_token'

function read(key: string): string | null {
  try {
    return window.localStorage.getItem(key)
  } catch {
    return null // private mode, or storage blocked
  }
}

function write(key: string, value: string | null): void {
  try {
    if (value === null) window.localStorage.removeItem(key)
    else window.localStorage.setItem(key, value)
  } catch {
    /* storage unavailable: the session simply will not survive a reload */
  }
}

export const tokens = {
  get access() {
    return read(ACCESS_KEY)
  },
  get refresh() {
    return read(REFRESH_KEY)
  },
  set(pair: { access_token: string; refresh_token: string }) {
    write(ACCESS_KEY, pair.access_token)
    write(REFRESH_KEY, pair.refresh_token)
  },
  clear() {
    write(ACCESS_KEY, null)
    write(REFRESH_KEY, null)
  },
  get hasSession() {
    return read(REFRESH_KEY) !== null
  },
}
