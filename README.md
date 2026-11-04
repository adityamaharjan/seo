# SEO Analysis API

Production-grade **FastAPI** backend for on-page SEO analysis, with JWT auth,
per-user daily quotas, async MySQL, and background job processing. The frontend
is a separate project — this service exposes a clean, versioned JSON API.

- **Rendered documentation page:** `http://<host>:8001/documentation` (this API reference, styled)
- **Interactive API docs (Swagger):** `http://<host>:8001/docs`
- **ReDoc:** `http://<host>:8001/redoc`
- **OpenAPI schema:** `http://<host>:8001/openapi.json`
- **Full endpoint & response reference (Markdown):** [docs/API.md](docs/API.md)
- **Web frontend:** [frontend/](frontend/) — a static Vite + React app, built and deployed separately

**License:** [MIT with attribution](LICENSE). Free for any use, including commercial.
Hosted copies must keep the visible "Created by @adityamaharjan" credit. See [License](#license).

**Contributing:** improvements are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for setup,
the checks a pull request must pass, and how the code is organised.

---

## Table of contents

1. [Features](#features)
2. [Architecture](#architecture)
3. [Requirements](#requirements)
4. [Quick start (local)](#quick-start-local)
5. [Configuration](#configuration)
6. [Database migrations](#database-migrations)
7. [Running the services](#running-the-services)
8. [Docker](#docker)
9. [Production deploy (systemd)](#production-deploy-systemd)
10. [Security](#security)
11. [API overview](#api-overview)
12. [User management](#user-management)
13. [The SEO engine](#the-seo-engine)
14. [Frontend](#frontend)
15. [Testing](#testing)
16. [Troubleshooting](#troubleshooting)
17. [License](#license)

---

## Features

- **Modular SEO engine** — 35 checks across 8 weighted categories (meta, content,
  structure, links, indexability, performance, security, mobile). Checks are
  weighted by ranking impact within their category, and indexability failures cap
  the score outright rather than being averaged away. See
  [the SEO engine](#the-seo-engine).
- **Two audit features, deliberately separate** — a **page audit** (one URL, with
  optional keyword targeting) and a **site audit** (crawl up to 50 pages and rank
  the problems that repeat). See [the SEO engine](#the-seo-engine).
- **Auth** — JWT access + refresh tokens with rotation & revocation; `user`/`admin` roles.
- **User management** — self-service profile and password changes, plus an admin
  directory for roles, account status, per-user quota overrides, forced sign-out
  and deletion. See [User management](#user-management).
- **Quotas** — free tier of **5 analyses per user per day** (plus a monthly counter),
  enforced at submit time under a row lock; returns HTTP 429 with a reset time
  when exceeded. A failed analysis refunds its unit.
- **Hardened target fetching** — a three-layer SSRF guard keeps users from
  pointing the analyzer at private networks. See [Security](#security).
- **Async everything** — async SQLAlchemy (asyncmy driver) + Alembic migrations.
- **Background jobs** — submit → poll pattern via ARQ + Redis, so slow analyses
  never block the API.
- **Rate limiting** — Redis-backed limits on signup, login and refresh; login is
  limited per source address *and* per targeted account.
- **Retention** — a nightly worker job prunes aged reports and dead refresh tokens.
- **Operable** — structured JSON logging, request IDs, consistent error envelope,
  health/readiness probes, CORS, GZip, a config guard that refuses to boot
  production with development defaults.

## Architecture

```
Client ──HTTP──► FastAPI (uvicorn, :8001)
                   │  POST /analyses  → save "pending" row + enqueue job ──► Redis
                   │  GET  /analyses/{id} → read row/result
                   ▼
                 MySQL  ◄────────────── ARQ worker (separate process)
                                         pulls job, runs SEO engine, writes result
```

Two processes must run: the **API** (uvicorn) and the **worker** (arq). Without
the worker, submitted analyses stay `pending` forever because nothing consumes
the queue.

```
app/
  core/      config (pydantic-settings), security (JWT + bcrypt), logging, exceptions
  db/        async engine/session, declarative base, model registry
  models/    User, Quota, Report, RefreshToken  (SQLAlchemy ORM)
  schemas/   Pydantic request/response models
  crud/      data-access layer
  services/  auth, users, quota, report orchestration, retention (business logic)
  seo/       fetcher, urlguard (SSRF), text, readability, scoring, analyzer, checks/
  api/v1/    endpoints (auth, users, admin, analyses, health) + shared deps
  workers/   ARQ worker settings + tasks
alembic/     migrations
deploy/      systemd units + the nginx front-door config
scripts/     command-line user administration
tests/       pytest suite (+ HTML fixtures)
frontend/    Vite + React web app (its own build; see frontend/README.md)
legacy/      the superseded prototype, kept for reference only
.github/     CI workflow (ruff + pytest)
```

## Requirements

- Python **3.13+** and [**uv**](https://docs.astral.sh/uv/getting-started/installation/),
  which manages dependencies (uv can install Python 3.13 for you)
- **MySQL 8.x** (the `asyncmy` driver needs build tools: `build-essential`,
  `default-libmysqlclient-dev`, `pkg-config`)
- **Redis 6+** (for the ARQ job queue)

## Quick start (local)

```bash
uv sync                       # creates .venv from uv.lock, dev tools included

cp .env.example .env          # then edit DB / JWT / Redis values
uv run alembic upgrade head   # create the schema

# Terminal 1 — API
uv run uvicorn app.main:app --reload --port 8001
# Terminal 2 — worker
uv run arq app.workers.settings.WorkerSettings
```

Dependencies live in `pyproject.toml` and are pinned in `uv.lock`. Add one with
`uv add <package>` (or `uv add --dev <package>` for tooling), and commit both files.

Open http://localhost:8001/docs.

## Configuration

All settings come from environment variables (or a `.env` file in the working
directory). See [.env.example](.env.example) for the full list.

| Variable | Default | Description |
|----------|---------|-------------|
| `DB`, `DBUser`, `DBPassword`, `DBPort`, `DB_HOST` | `seo` / … / `localhost` | MySQL connection |
| `DB_POOL_SIZE`, `DB_MAX_OVERFLOW` | `10` / `20` | Connection pool sizing |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis / ARQ broker |
| `JWT_SECRET` | *(change me)* | HMAC secret — generate: `python -c "import secrets;print(secrets.token_urlsafe(48))"` |
| `JWT_ALGORITHM` | `HS256` | JWT signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Access token lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token lifetime |
| `FREE_DAILY_LIMIT` | `5` | Free analyses per user per day |
| `FREE_MONTHLY_LIMIT` | `100` | Monthly counter (reporting) |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins. A wildcard is rejected in production |
| `CORS_ORIGIN_REGEX` | *(unset)* | Anchored regex for origins you cannot list literally, such as Vercel/Pages preview URLs |
| `CORS_EXPOSE_HEADERS` | `Retry-After,X-Request-ID,X-Process-Time-ms` | Response headers a cross-origin browser may read |
| `RATE_LIMIT_ENABLED` | `true` | Redis-backed limits on the auth endpoints |
| `LOGIN_RATE_LIMIT` / `LOGIN_RATE_WINDOW_SECONDS` | `10` / `300` | Login attempts per window |
| `SIGNUP_RATE_LIMIT` / `SIGNUP_RATE_WINDOW_SECONDS` | `5` / `3600` | Accounts created per window |
| `REPORT_RETENTION_DAYS` | `90` | Age at which reports are pruned (`0` disables) |
| `TOKEN_RETENTION_DAYS` | `7` | Grace period before expired refresh tokens are pruned |
| `SEO_TIMEOUT_SECONDS` | `15` | Per-fetch timeout |
| `SEO_MAX_PAGE_BYTES` | `5000000` | Hard cap on fetched HTML |
| `SEO_MAX_BROKEN_LINK_CHECKS` | `25` | Max outbound HEAD requests per analysis |
| `SEO_MAX_REDIRECTS` | `10` | Redirect hops followed per fetch, each re-checked by the guard |
| `SEO_ALLOW_PRIVATE_TARGETS` | `false` | Allow analyzing private/localhost addresses. **Never enable in production** |

## Database migrations

```bash
alembic upgrade head                              # apply all migrations
alembic revision --autogenerate -m "add column"   # create a new migration
alembic downgrade -1                              # roll back one
alembic current                                   # show applied revision
```

Migrations use the sync PyMySQL URL; the app itself uses the async asyncmy URL.
Both derive from the same `DB*` env vars.

## Running the services

| Process | Command | Purpose |
|---------|---------|---------|
| API | `uvicorn app.main:app --host 0.0.0.0 --port 8001 --workers 3` | Serves HTTP, enqueues jobs |
| Worker | `arq app.workers.settings.WorkerSettings` | Runs analyses from the queue |

## Docker

The compose stack runs API + worker + MySQL + Redis together:

```bash
cp .env.example .env
docker compose up --build
```

`docker-compose.yml` applies migrations automatically before the API starts.

## Production deploy (systemd)

Two unit files are provided in [deploy/](deploy/). The API runs as `www-data`
from the project's `.venv` on port 8001.

```bash
# Install runtime dependencies into /var/www/seo/.venv (no dev tools).
# The Python install dir must be readable by www-data, so keep it out of $HOME.
sudo mkdir -p /opt/uv/python && sudo chown "$USER" /opt/uv/python
cd /var/www/seo
UV_PYTHON_INSTALL_DIR=/opt/uv/python uv sync --locked --no-dev
uv run --no-sync alembic upgrade head

# Redis (durable, via Docker) — or use a host redis-server
sudo docker run -d --restart unless-stopped -p 6379:6379 --name redis redis

# Install / update both units
sudo cp deploy/uvicorn.service     /etc/systemd/system/uvicorn.service
sudo cp deploy/seo-worker.service  /etc/systemd/system/seo-worker.service
sudo systemctl daemon-reload

# Start (and enable on boot)
sudo systemctl enable --now uvicorn.service seo-worker.service
sudo systemctl status uvicorn.service seo-worker.service --no-pager
```

Logs: `journalctl -u uvicorn -f` and `journalctl -u seo-worker -f`.

> **Note:** the API serves everything under the `/api/v1` prefix (the old
> prototype used `/seoapi`, `/signup`, `/login` with no prefix). Update any
> reverse proxy / frontend accordingly.

## Security

### Fetching user-supplied URLs (SSRF)

`POST /analyses` makes the server fetch a URL chosen by the caller, so without a
guard the API is a proxy into whatever network it runs on. `app/seo/urlguard.py`
applies three layers, because each is bypassable on its own:

1. **Static validation** — only `http`/`https`, no literal private, loopback,
   link-local, reserved or multicast address, and no non-web port (SSH, MySQL,
   Redis, Postgres and friends). This runs during request validation, so a bad
   target is a `422` and **no quota is charged**.
2. **Resolution** — the hostname is resolved and rejected if *any* returned
   address is non-public, which catches names like `localhost` and DNS entries
   pointed at internal hosts.
3. **Connected peer** — after connecting, the address the socket actually landed
   on is checked, closing the DNS-rebinding window between steps 2 and 3.

Redirects are followed manually so every hop repeats all three, and the same
guard applies to robots.txt, sitemap and broken-link probes, whose URLs come
from the analyzed page and are equally untrusted.

Set `SEO_ALLOW_PRIVATE_TARGETS=true` only to analyze a site on your own LAN, and
never in production. The config guard refuses to boot if you do.

### Production config guard

With `ENVIRONMENT=production`, the app refuses to start when `JWT_SECRET` is the
built-in default or under 32 characters, `CORS_ORIGINS` is a wildcard,
`SEO_ALLOW_PRIVATE_TARGETS` is on, or `DEBUG` is on. Generate a secret with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

> Changing `JWT_SECRET` invalidates every access and refresh token already issued.

### Rate limiting

Signup, login and refresh are limited through Redis. Login is limited twice:
per source address, and per targeted email so a distributed attempt cannot
spread guesses for one account across many addresses. Forwarded-for headers are
believed only when the direct peer is a local reverse proxy, so a client
connecting straight from the internet cannot forge a fresh bucket.

The limiter **fails open**: if Redis is unreachable the API keeps serving rather
than locking everyone out, and logs the failure.

### Data retention

The worker runs a purge at 03:17 UTC that deletes reports older than
`REPORT_RETENTION_DAYS` and refresh tokens that are revoked or expired past
`TOKEN_RETENTION_DAYS`. Report payloads are the largest rows in the database, so
leaving this off will grow the table without bound.

## API overview

Base URL: `http://<host>:8001` · all app endpoints are under `/api/v1`.

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/v1/auth/signup` | – | Create account |
| POST | `/api/v1/auth/login` | – | Get access + refresh tokens |
| POST | `/api/v1/auth/refresh` | – | Rotate refresh token |
| POST | `/api/v1/auth/logout` | – | Revoke a refresh token |
| GET | `/api/v1/auth/me` | Bearer | Current user |
| PATCH | `/api/v1/users/me` | Bearer | Change your username or email |
| POST | `/api/v1/users/me/password` | Bearer | Change your password, ends all sessions |
| GET | `/api/v1/users/me/quota` | Bearer | Quota usage / remaining today |
| GET | `/api/v1/admin/users` | Admin | Paginated user directory |
| GET | `/api/v1/admin/users/{id}` | Admin | One user with quota and report count |
| PATCH | `/api/v1/admin/users/{id}` | Admin | Change role or enabled status |
| PATCH | `/api/v1/admin/users/{id}/quota` | Admin | Override daily / monthly limits |
| POST | `/api/v1/admin/users/{id}/revoke-sessions` | Admin | Sign a user out everywhere |
| DELETE | `/api/v1/admin/users/{id}` | Admin | Delete a user and their data |
| POST | `/api/v1/analyses` | Bearer | Submit a URL → `202` + status URL |
| GET | `/api/v1/analyses` | Bearer | Paginated history |
| GET | `/api/v1/analyses/{id}` | Bearer | Report status + full results |
| DELETE | `/api/v1/analyses/{id}` | Bearer | Delete a report |
| GET | `/api/v1/health`, `/api/v1/ready` | – | Liveness / readiness |
| GET | `/` | – | Service metadata |

Full request/response schemas and field-by-field documentation live in
**[docs/API.md](docs/API.md)**.

### End-to-end example

```bash
BASE=http://127.0.0.1:8001/api/v1

curl -s -X POST $BASE/auth/signup -H 'content-type: application/json' \
  -d '{"username":"alice","email":"alice@example.com","password":"supersecret"}'

TOKEN=$(curl -s -X POST $BASE/auth/login -H 'content-type: application/json' \
  -d '{"email":"alice@example.com","password":"supersecret"}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

ID=$(curl -s -X POST $BASE/analyses -H "authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' -d '{"url":"https://example.com"}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')

sleep 3
curl -s $BASE/analyses/$ID -H "authorization: Bearer $TOKEN" | python3 -m json.tool
```

## User management

### Making the first administrator

The admin endpoints require an admin, so the first one is made on the server:

```bash
cd /var/www/seo

.venv/bin/python -m scripts.manage_users list
.venv/bin/python -m scripts.manage_users promote you@example.com
```

`demote`, `disable` and `enable` are available too. Everything after that can be
done through the API or the frontend's Users screen.

### What administrators can do

Search and page through every account, change roles, enable and disable
accounts, override a user's daily and monthly allowance, sign someone out of
every device, and delete an account with all of its reports.

### Guard rails

Two rules make it impossible for one request to lock everyone out:

- You cannot change your own role, disable yourself, or delete yourself. Those
  return `403`.
- The last enabled administrator cannot be demoted, disabled or deleted by any
  route. That returns `409`.

Demoting or disabling someone revokes their refresh tokens as part of the same
change, so it bites immediately rather than whenever their access token happens
to expire. The same applies when a user changes their own password: every
session ends, because a password change is usually a response to exposure.

## The SEO engine

Each analysis fetches the page once (capturing real timing) and runs every check
concurrently where network I/O is involved. Checks are pure functions returning a
`status` (`good`/`warning`/`critical`/`info`), a `0–100 score`, a human `message`,
and an actionable `recommendation`.

**Scoring works in three stages**, all tunable from `app/seo/constants.py`:

1. **Within a category**, check scores combine using `CHECK_WEIGHTS` — a relative
   weight per check where `1.0` is ordinary. A missing title tag (`3.0`) moves the
   meta score six times as far as a missing Twitter card (`0.5`). Weighting matters:
   averaging a category's checks equally lets a favicon outvote an H1, which is what
   makes a composite score feel arbitrary.
2. **Across categories**, `CATEGORY_WEIGHTS` combine into the overall score:
   meta `0.20`, content `0.22`, structure `0.12`, links `0.10`, indexability `0.12`,
   performance `0.12`, security `0.06`, mobile `0.06`.
3. **Caps override the average.** A page that cannot be indexed cannot rank,
   whatever else it does right, so the checks in `SCORE_CAPS` put a ceiling on the
   overall score when they come back critical: `meta_robots` (noindex, from the meta
   tag or an `X-Robots-Tag` header) and `robots_txt` cap at `40`, `https` (plain
   HTTP) caps at `60`. `uncapped_score` is what the page scores *with those checks
   fixed and nothing else changed*, so "fixing that alone takes you to 84" is
   literally true rather than an understatement.

> **robots.txt is parsed, not pattern-matched.** `app/seo/robots.py` implements
> RFC 9309: rules grouped by user-agent, longest-rule-wins precedence, `Allow`
> carve-outs, `*` wildcards and `$` anchors, tolerant of CRLF, trailing whitespace
> and a missing space after the colon. Only the `*` group and Googlebot's own group
> can fail the check. Blocking a named scraper or AI crawler in its own group —
> which most sites do — never caps the score. The previous substring scan flagged
> those sites as blocking everyone, costing them up to 55 points, while missing a
> genuine site-wide block served with Windows line endings.

### Keyword targeting (page audit only)

Submit `target_keywords` (up to 5) with a page analysis and each one is scored on
*placement* — title, H1, meta description, first 100 words, subheadings, URL slug
and image alt — weighted by how much each location actually influences relevance,
with an exact phrase worth double an inflected variant ("urban garden" matching
"urban gardening"). Density is reported but only penalised when it crosses into
stuffing.

This is **its own feature, not a check inside the audit**. Its result arrives as a
top-level `keyword_report` and never touches `overall_score`. Page health is a
property of the URL: typing keywords into a box must not change it. Placements the
page cannot have — image alt text with no images, a URL slug on a homepage — are
dropped from the denominator instead of counted as misses, so a perfect score is
actually reachable.

> Earlier versions guessed a page's topic from body-word frequency instead. That
> guess was meaningless on thin or JavaScript-rendered pages — it would report a
> topic as a random three-letter fragment — so the keywords are now an input
> rather than an output.

### Site audit (multi-page crawl)

A site audit crawls up to 50 pages of one host and runs the full page audit on each.
Pages come from the site's sitemaps first (declared in robots.txt, else
`/sitemap.xml`, expanding one index level), falling back to a breadth-first walk of
internal links. robots.txt is obeyed, every hop re-checks the SSRF guard, and
robots.txt is fetched once for the whole crawl rather than per page.

The output is not an average. It is `top_issues`: every warning and critical check
counted across the crawl and ranked by how many pages it affects, with anything
hitting half the site flagged `sitewide`. One page with a short title is a task;
forty pages with short titles is a template bug, and only the count tells them apart.

One crawl costs one quota unit whatever the page count; `max_pages`, concurrency and
a whole-crawl deadline are what bound the work (`SITE_AUDIT_*` in `app/core/config.py`).
Site audits live in their own tables and never appear in single-page history.

Informational checks (`status: "info"`) are excluded from scoring entirely — they
neither help nor hurt. Every report also carries `issue_counts`, a tally of checks
per status, so a client can lead with "3 critical, 7 warnings" instead of making
the single number carry all the meaning.

**Checks by category** (35 total):

- **meta** — title_tag, meta_description, canonical, meta_robots, html_lang,
  structured_data (JSON-LD), open_graph, twitter_card
- **content** — word_count, readability (Flesch), stopword_density, typos,
  image_alt, image_optimization
- **structure** — h1_heading, heading_hierarchy, charset, doctype, favicon
- **links** — links (internal/external), anchor_quality, broken_links
- **indexability** — robots_txt, sitemap, hreflang
- **performance** — ttfb, load_time, page_size, compression, render_blocking,
  core_web_vitals*
- **security** — https, security_headers, mixed_content
- **mobile** — mobile_viewport

\* **Core Web Vitals (FCP/LCP/CLS/INP) are not measured.** They require a real
browser; the pure-HTTP engine returns them as an informational, disabled check.
A future Google PageSpeed / headless integration can be enabled via
`CORE_WEB_VITALS_ENABLED` in `app/seo/checks/performance.py` without changing the
API contract.

## Frontend

A static single-page app lives in [frontend/](frontend/). It is a separate
project with its own dependencies and build, sharing this repository only for
convenience: no Python code imports it, and `ruff` and `pytest` never look at it.

```bash
cd frontend
npm install
npm run dev      # http://localhost:5173, proxies /api to :8001
npm run build    # static output in frontend/dist/
```

### Serving both from one origin

[deploy/nginx-seo.conf](deploy/nginx-seo.conf) puts nginx in front on
`127.0.0.1:8002`. It serves the built app at `/` and forwards the API paths to
uvicorn, so the browser sees a single origin and CORS is never involved.

```bash
npm --prefix frontend run build
sudo cp deploy/nginx-seo.conf /etc/nginx/sites-available/seo
sudo ln -sf /etc/nginx/sites-available/seo /etc/nginx/sites-enabled/seo
sudo nginx -t && sudo systemctl reload nginx
```

Then repoint the Cloudflare tunnel hostname from `http://localhost:8001` to
`http://localhost:8002`.

| Path | Served by |
|------|-----------|
| `/` (landing), `/login`, `/app`, `/site-audit/7` | the frontend, from `frontend/dist/` |
| `/api/v1/*` | FastAPI on `:8001` |
| `/docs`, `/redoc`, `/openapi.json`, `/documentation` | FastAPI on `:8001` |

### Hosting the frontend on Vercel or Cloudflare Pages

Config for both platforms ships in `frontend/`. Set the project root to
`frontend`, set `VITE_API_BASE_URL` as a build variable (Vite inlines it at
build time), and allow the origin on this side:

```bash
CORS_ORIGINS=https://seo-frontend.vercel.app
# Per-branch preview URLs, which cannot be listed literally:
CORS_ORIGIN_REGEX=^https://seo-frontend-[a-z0-9-]+\.vercel\.app$
```

The regex must be anchored with `^` and `$`, and the config guard refuses to
start production if it is not. An origin matched by regex is trusted exactly as
much as one listed literally.

Cross-origin also means the browser hides most response headers.
`CORS_EXPOSE_HEADERS` keeps `Retry-After` readable, which is what lets the
frontend say when a rate limit or quota resets. Full walkthrough in
[frontend/README.md](frontend/README.md).

## Testing

```bash
pytest                                  # full suite (in-memory SQLite; no MySQL/Redis needed)
pytest tests/seo                        # SEO checks against committed HTML fixtures
pytest --cov --cov-report=term-missing  # with coverage
ruff check app tests
mypy app

cd frontend
npm run lint                            # ESLint
npm test                                # Vitest
npm run build                           # type-check and production build
```

All of these run on every push and pull request via
[.github/workflows/ci.yml](.github/workflows/ci.yml), which fails below 70% coverage. The suite needs outbound DNS: the SSRF guard
resolves hostnames even when the HTTP layer is mocked.

## Troubleshooting

| Symptom | Likely cause / fix |
|---------|--------------------|
| Analysis stuck on `pending` | Worker not running → start `seo-worker.service` / `arq …`. Check `journalctl -u seo-worker`. |
| `502` / API won't start | Redis unreachable (lifespan creates an ARQ pool). Verify `REDIS_URL` and that Redis is up. |
| `uv sync` fails building `asyncmy` | Install the build tools it needs: `build-essential`, `default-libmysqlclient-dev`, `pkg-config`. |
| `failed to locate a name 'Quota'` | All models must be imported before mapper config — `app.db.session` imports the registry; don't bypass it. |
| 401 on every request | Missing/expired access token, or `JWT_SECRET` changed (invalidates issued tokens). |
| Migration is an ALTER diff, not CREATE | The DB still has old tables. Start from a clean schema before generating the initial migration. |
| `422` with "is not a public address" | The SSRF guard blocked the target. Expected for private/localhost URLs; set `SEO_ALLOW_PRIVATE_TARGETS=true` in development only. |
| `503 service_unavailable` on submit | Redis was unreachable when queueing. The report is failed and the quota refunded; check Redis and retry. |
| App won't start with "Unsafe configuration for ENVIRONMENT=production" | Working as intended. Fix the listed settings; see [Security](#security). |
| `429 rate_limited` (not `quota_exceeded`) | Auth endpoint rate limit, not the daily quota. Tune `LOGIN_RATE_LIMIT` / `SIGNUP_RATE_LIMIT`. |

## License

Created by [@adityamaharjan](https://github.com/adityamaharjan). Released under the
[MIT License with an attribution term](LICENSE):

- **Use it for anything**, including commercial use: host it, modify it, sell it.
- **Keep the credit:** any copy that other people can use must keep the visible
  "Created by @adityamaharjan" credit, linking to https://github.com/adityamaharjan.
  The frontend already shows it (`frontend/src/components/Credit.tsx`).
- **Add your own name:** you can credit yourself next to it as the person who
  modified or hosts it.

[LICENSE](LICENSE) has the full terms.
