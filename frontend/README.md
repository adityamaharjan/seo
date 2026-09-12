# SEO Analysis — Frontend

Static single-page app for the [SEO Analysis API](../README.md). Built with
Vite, React and TypeScript. `npm run build` produces plain files in `dist/` that
any web server can host.

It lives in this repository for convenience but is completely separate from the
backend: its own dependencies, its own build, its own deploy. Nothing in `app/`
imports it and no Python tooling looks at it.

---

## Contents

1. [Requirements](#requirements)
2. [Development](#development)
3. [Building](#building)
4. [Deploying](#deploying)
5. [Configuration](#configuration)
6. [What the app does](#what-the-app-does)
7. [Project structure](#project-structure)
8. [How auth works](#how-auth-works)

## Requirements

Node 20 or newer. Node 22 is what this was built and tested against.

## Development

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173
```

The dev server proxies `/api` to the backend so the browser still sees a single
origin and no CORS is involved. It defaults to `http://127.0.0.1:8001`. To
develop against the deployed API instead, create `.env.local`:

```bash
VITE_DEV_API_TARGET=https://seo.hakezlabs.qzz.io
```

Other commands:

```bash
npm run typecheck    # TypeScript, no emit
npm run build        # typecheck + production build
npm run preview      # serve dist/ locally to check the real build
```

## Building

```bash
npm run build
```

Output lands in `dist/`: an `index.html` plus fingerprinted assets, and no
runtime dependency on any CDN.

Every view is loaded on demand, and React and the router are split into their
own chunks so a deploy that touches a view leaves them cached. A first visit to
the landing page is about 120 KB gzipped across four files; moving into the app
fetches the shell and that view only.

## Deploying

### Same origin (what this repo is set up for)

nginx serves `dist/` at `/` and forwards the API paths to uvicorn, so the app
and the API share one hostname and CORS never enters the picture.

```bash
npm --prefix frontend run build

sudo cp deploy/nginx-seo.conf /etc/nginx/sites-available/seo
sudo ln -sf /etc/nginx/sites-available/seo /etc/nginx/sites-enabled/seo
sudo nginx -t && sudo systemctl reload nginx
```

Then repoint the Cloudflare tunnel's public hostname for
`seo.hakezlabs.qzz.io` from `http://localhost:8001` to `http://localhost:8002`,
which is where the nginx front door listens. Routing afterwards:

| Path | Served by |
|------|-----------|
| `/` (landing), `/login`, `/app`, `/site-audit/7` | this app, from `dist/` |
| `/api/v1/*` | FastAPI on `:8001` |
| `/docs`, `/redoc`, `/openapi.json` | FastAPI on `:8001` |
| `/documentation` | FastAPI on `:8001` |

Rebuilding is just `npm run build`; nginx picks up the new files with no reload.

### Vercel or Cloudflare Pages

Hosting the frontend on its own domain works, and config for both platforms is
already in this folder. Three things have to line up.

**1. Point the build at the API.** Vite inlines this at build time, so it must
be set as a build environment variable on the platform, not at runtime:

```
VITE_API_BASE_URL = https://seo.hakezlabs.qzz.io/api/v1
```

**2. Set the project root.** This repository's root is the Python backend, so
both platforms need telling that the app lives in a subdirectory.

| Setting | Vercel | Cloudflare Pages |
|---------|--------|------------------|
| Root directory | `frontend` | `frontend` |
| Framework preset | Vite | Vite |
| Build command | `npm run build` | `npm run build` |
| Output directory | `dist` | `dist` |
| Node version | 22 (from `.nvmrc`) | 22 (set `NODE_VERSION=22`) |

Routing is already handled. [vercel.json](vercel.json) rewrites unknown paths to
`index.html` and caches the fingerprinted assets forever;
[public/_redirects](public/_redirects) and [public/_headers](public/_headers) do
the same on Pages. Without that fallback, reloading on `/site-audit/7` returns a
404, because only the browser knows that route exists.

**3. Allow the origin on the API.** Add the frontend's origin to `CORS_ORIGINS`
in the API's `.env` and restart it:

```bash
CORS_ORIGINS=https://seo-frontend.vercel.app
```

Both platforms also publish a fresh URL for every branch and pull request. Those
previews have origins you cannot list ahead of time, so match them with a regex
instead. It must be anchored, and the API refuses to start in production if it
is not:

```bash
# Vercel previews
CORS_ORIGIN_REGEX=^https://seo-frontend-[a-z0-9-]+\.vercel\.app$

# Cloudflare Pages previews
CORS_ORIGIN_REGEX=^https://[a-z0-9]+\.seo-frontend\.pages\.dev$
```

Keep the pattern tight. An origin matched by regex is trusted exactly as much as
one listed literally, so a loose pattern is a wildcard that merely looks
specific.

> The repository must be pushed to GitHub before either platform can build it.
> `app/` and `frontend/` are currently untracked.

#### What changes when the origin differs

- **Preflight requests.** The browser sends an `OPTIONS` before anything with an
  `Authorization` header. The API answers these already.
- **Readable response headers.** Cross-origin, a browser hides every response
  header that is not on a short safelist, and `Retry-After` is not on it. The
  API lists it under `CORS_EXPOSE_HEADERS`, which is what lets this app say
  "try again in 4 minutes" rather than just "too many requests".
- **Latency.** Every API call becomes a cross-origin round trip, with a
  preflight on the first of each kind. Preflights are cached for ten minutes.

### Any other static host

Upload `dist/` anywhere: Netlify, an S3 bucket, a plain directory. Same three
requirements as above, plus the host must rewrite unknown paths to `index.html`.

## Configuration

| Variable | Default | When you need it |
|----------|---------|------------------|
| `VITE_API_BASE_URL` | `/api/v1` | Only when the frontend is on a different origin than the API. Inlined at build time, so it must be set before `npm run build`, not at runtime |
| `VITE_DEV_API_TARGET` | `http://127.0.0.1:8001` | Development only: where `npm run dev` proxies `/api` |

Copy [.env.example](.env.example) to `.env` to change them.

## What the app does

- **Sign up and sign in.** Signing up logs you straight in.
- **Submit a URL.** The scheme is optional, so `example.com` works. Rejected
  targets, such as a private address, come back as a field error and cost no
  quota.
- **Watch the report build.** The report page polls until the worker finishes,
  backing off from one second to three, and gives up after about two minutes
  with a retry button rather than spinning forever.
- **Read the result.** Overall score ring and grade, timing stats, the eight
  weighted category scores, and all 36 checks grouped by category with a filter
  for critical, warning, good and info.
- **Track quota.** A bar shows analyses left today and when the allowance
  resets. A failed analysis is refunded, and the number updates to match.
- **Browse history.** Paginated list of past reports, each deletable.

Errors are shown in the API's own vocabulary: hitting the daily allowance reads
differently from hitting the login rate limit, because the API distinguishes
them by error code even though both are HTTP 429.

## Project structure

```
src/
  api/
    client.ts      fetch wrapper: error envelope, bearer auth, token renewal
    endpoints.ts   one typed function per endpoint
    types.ts       response shapes, mirroring docs/API.md
  auth/
    AuthContext.tsx  who is signed in; login, signup, logout
    tokens.ts        token storage
  theme/
    ThemeContext.tsx light, dark or follow the system
  components/      Layout, AuthShell, RequireAuth, ScoreRing, StatusPill,
                   QuotaBar, Notice, ThemeToggle, RouteFallback
  components/Page.tsx        the layout vocabulary every view is built from:
                             PageHeader, Section, Panel, Stat, EmptyState
  components/ui/   shadcn/ui components, used everywhere
  components/ReportBody.tsx  one page's full report, shared by both features
  routes/          Landing, Login, Signup, PageAudit, Report,
                   SiteAudit, SiteAuditReport, SiteAuditPage, Account, Admin
  dev/             visual preview harness, not shipped
  lib/format.ts    dates, durations, sizes, check values
  tailwind.css     the app's only stylesheet: tokens, the shadcn token
                   bridge, and the handful of keyframes views compose with
```

One styling system across every surface. Views are Tailwind utilities on
shadcn/ui primitives, and the only thing `tailwind.css` holds is what utilities
cannot express: the palette, the mapping from it onto the names shadcn expects,
and the motion primitives. Tailwind's preflight is imported, so the reset
behaves the way its documentation says it does.

shadcn's token names are aliases for the palette rather than separate values, so
there is exactly one definition of each colour and one place to change it.

Adding a shadcn component is `npx shadcn@latest add <name>`; it lands in
`src/components/ui/` and is yours to edit.

### Theme

Light, dark, or follow the operating system, chosen from the control in the
header and remembered in `localStorage` under `seo-theme`. Dark is a `dark`
class on `<html>`, written by a short inline script in `index.html` before the
first paint so the page never flashes the wrong palette on the way to the right
one; `ThemeProvider` resolves "system" against `prefers-color-scheme` and keeps
following it as the OS changes.

Changing the palette means editing the two token blocks at the top of
`tailwind.css` and the two colours the startup script and `ThemeContext.tsx`
use for the `theme-color` meta tag.

## How auth works

The API issues a short-lived access token and a longer-lived refresh token, and
rotates the refresh token on every use.

- Both tokens are kept in `localStorage`. This is a static app with no server of
  its own, so there is no way to use an httpOnly cookie: any token the app can
  read, script on the page can read. Keeping the access token in memory would
  not change that while the refresh token sits beside it. The real mitigations
  are the short access-token lifetime and rotation, which the API enforces.
- When a request returns 401, the client renews the access token once and
  retries. Renewal is single flighted, so several requests failing at the same
  moment wait on one renewal instead of racing and revoking each other's token.
- If renewal fails, tokens are cleared and the app returns to the sign-in
  screen, remembering where you were headed.

One known limit: because refresh tokens rotate, two browser tabs that renew at
the exact same moment can invalidate each other and force one to sign in again.
Single-flighting fixes this within a tab, not across tabs.
