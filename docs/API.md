# API Reference

Complete reference for the SEO Analysis API. For setup and running, see the
[README](../README.md). An always-current interactive version is served at
`/docs` (Swagger) and `/redoc`.

- **Base URL:** `http://<host>:8001`
- **App prefix:** all endpoints below are under `/api/v1` unless noted
- **Content type:** `application/json`
- **Auth:** JWT Bearer — send `Authorization: Bearer <access_token>`

---

## Table of contents

- [Conventions](#conventions)
- [Errors](#errors)
- [Authentication](#authentication)
  - [POST /auth/signup](#post-authsignup)
  - [POST /auth/login](#post-authlogin)
  - [POST /auth/refresh](#post-authrefresh)
  - [POST /auth/logout](#post-authlogout)
  - [GET /auth/me](#get-authme)
- [Users & quota](#users--quota)
  - [GET /users/me](#get-usersme)
  - [PATCH /users/me](#patch-usersme)
  - [POST /users/me/password](#post-usersmepassword)
  - [GET /users/me/quota](#get-usersmequota)
- [Administration](#administration)
  - [GET /admin/users](#get-adminusers)
  - [GET /admin/users/{id}](#get-adminusersid)
  - [PATCH /admin/users/{id}](#patch-adminusersid)
  - [PATCH /admin/users/{id}/quota](#patch-adminusersidquota)
  - [POST /admin/users/{id}/revoke-sessions](#post-adminusersidrevoke-sessions)
  - [DELETE /admin/users/{id}](#delete-adminusersid)
- [Analyses](#analyses)
  - [POST /analyses](#post-analyses)
  - [GET /analyses](#get-analyses)
  - [GET /analyses/{id}](#get-analysesid)
  - [DELETE /analyses/{id}](#delete-analysesid)
- [Site audits](#site-audits)
  - [POST /site-audits](#post-site-audits)
  - [GET /site-audits](#get-site-audits)
  - [GET /site-audits/{id}](#get-site-auditsid)
  - [GET /site-audits/{id}/pages/{page_id}](#get-site-auditsidpagespage_id)
  - [DELETE /site-audits/{id}](#delete-site-auditsid)
- [Health](#health)
- [SEO result schema](#seo-result-schema)
- [Data model](#data-model)

---

## Conventions

- Timestamps are ISO-8601 UTC.
- All responses include `X-Request-ID` and `X-Process-Time-ms` headers.
- Pagination uses `page` (1-based) and `page_size` query params.
- A short-lived **access token** authorizes requests; a longer-lived **refresh
  token** obtains new access tokens. Refresh tokens are **rotated** — each use
  revokes the old one and returns a new pair.
- The unauthenticated endpoints are rate limited. Defaults are 10 logins per 5
  minutes per source address (and per targeted account) and 5 signups per hour
  per address. Exceeding a limit returns `429 rate_limited` with `Retry-After`.

## Errors

All errors share one envelope:

```json
{
  "error": {
    "code": "quota_exceeded",
    "message": "Daily free limit of 5 analyses reached.",
    "details": { "daily_limit": 5, "used_today": 5, "resets_at": "2026-06-26T00:00:00Z" }
  }
}
```

| HTTP | `code` | Meaning |
|------|--------|---------|
| 400 | `bad_request` | Generic bad request |
| 401 | `authentication_failed` | Missing/invalid/expired token or credentials |
| 403 | `forbidden` | Authenticated but not allowed (e.g. admin-only) |
| 404 | `not_found` | Resource does not exist (or not owned by you) |
| 409 | `conflict` | Duplicate (e.g. email/username already taken) |
| 422 | `validation_error` | Request body failed validation (`details` = field errors) |
| 429 | `quota_exceeded` | Daily analysis quota reached; includes `Retry-After` header |
| 429 | `rate_limited` | Too many requests to an auth endpoint; includes `Retry-After` header |
| 500 | `internal_error` | Unexpected server error |
| 503 | `service_unavailable` | The job queue was unreachable; quota is refunded |

Two different conditions return `429`. Distinguish them by `code`:
`quota_exceeded` is the daily analysis allowance, `rate_limited` is the
short-window limit on signup, login and refresh.

---

## Authentication

### POST /auth/signup

Create a new account. A quota record is created automatically.

**Body**

| Field | Type | Rules |
|-------|------|-------|
| `username` | string | 3–50 chars, unique |
| `email` | string | valid email, unique |
| `password` | string | 8–128 chars |

**Request**
```json
{ "username": "alice", "email": "alice@example.com", "password": "supersecret" }
```

**`201 Created`**
```json
{
  "id": 1,
  "username": "alice",
  "email": "alice@example.com",
  "role": "user",
  "is_active": true,
  "created_at": "2026-06-25T16:30:00Z"
}
```

Errors: `409 conflict` if email or username exists.

### POST /auth/login

Exchange credentials for a token pair.

**Request**
```json
{ "email": "alice@example.com", "password": "supersecret" }
```

**`200 OK`**
```json
{
  "access_token": "eyJhbGciOi...",
  "refresh_token": "eyJhbGciOi...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

`expires_in` is the access-token lifetime in seconds. Errors: `401`.

### POST /auth/refresh

Rotate a refresh token. The presented refresh token is revoked and a new pair is
returned.

**Request**
```json
{ "refresh_token": "eyJhbGciOi..." }
```

**`200 OK`** — same shape as login. Errors: `401` if the token is invalid,
expired, already used, or revoked.

### POST /auth/logout

Revoke a refresh token (use on sign-out).

**Request**
```json
{ "refresh_token": "eyJhbGciOi..." }
```

**`204 No Content`**

### GET /auth/me

Return the authenticated user. **Auth required.**

**`200 OK`** — same shape as the signup response.

---

## Users & quota

### GET /users/me

Alias of `/auth/me`. **Auth required.**

### PATCH /users/me

Change your own username or email. Omitted fields are left alone, and at least
one must be present. **Auth required.**

**Body**

| Field | Type | Rules |
|-------|------|-------|
| `username` | string | optional, 3–50 chars, unique |
| `email` | string | optional, valid email, unique |

**Request**
```json
{ "username": "alice2" }
```

**`200 OK`** — the updated user, same shape as signup.

Errors: `409 conflict` if the username or email belongs to someone else,
`422 validation_error` if the body is empty.

### POST /users/me/password

Change your password. **Every session is signed out**, including the one making
the request, so the client must send the user back to sign-in afterwards. This
is deliberate: a password change is usually a response to exposure, and a stolen
refresh token must not keep working. **Auth required.**

**Body**

| Field | Type | Rules |
|-------|------|-------|
| `current_password` | string | must match the account's current password |
| `new_password` | string | 8–128 chars, must differ from the current one |

**`200 OK`**
```json
{ "revoked": 3 }
```

`revoked` is how many refresh tokens were invalidated.

Errors: `401 authentication_failed` if the current password is wrong,
`422 validation_error` if the new password is too short or unchanged.

### GET /users/me/quota

Current quota usage for the authenticated user. Counters auto-reset (daily on a
new UTC day, monthly on a new month) when read. **Auth required.**

**`200 OK`**
```json
{
  "daily_limit": 5,
  "used_today": 2,
  "remaining_today": 3,
  "day_reset_date": "2026-06-25",
  "monthly_limit": 100,
  "used_this_month": 12,
  "month_reset_date": "2026-06-25T00:00:00Z"
}
```

---

## Analyses

### POST /analyses

Submit a URL for analysis. **Consumes one daily quota unit.** The work runs in
the background worker; poll `status_url` for the result. **Auth required.**

**Body**

| Field | Type | Rules |
|-------|------|-------|
| `url` | string (URL) | Valid `http(s)` URL pointing at a **public** host |
| `target_keywords` | array of string | Optional, up to **5**, each ≤100 chars. Terms this page should be judged against. Whitespace is collapsed and case-insensitive duplicates dropped |

**Target keywords.** Given any, the response carries a separate
[`keyword_report`](#keyword_report) scoring each keyword on *placement* — title, H1,
meta description, first 100 words, subheadings, URL slug and image alt — weighted by
influence, with an exact phrase worth double an inflected match ("urban garden"
matching "urban gardening"). Density is reported and penalised only when it crosses
into stuffing. Given none, `keyword_report` is `null`.

Keyword targeting is **scored separately and never folded into `overall_score`**.
Page health is a property of the URL, so the same page scores the same whether or
not keywords were named. Placements the page cannot have — image alt text on a page
with no images, a URL slug on a homepage — are dropped from the denominator rather
than counted as misses.

The target must be publicly routable. Loopback, private (RFC1918), link-local,
reserved and multicast addresses are refused, as are non-web ports (SSH, MySQL,
Redis and similar) and non-HTTP schemes. This is checked during request
validation, so a refused URL returns `422` and **does not consume quota**:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Request validation failed",
    "details": [
      {
        "type": "value_error",
        "loc": ["body", "url"],
        "msg": "Value error, '169.254.169.254' is not a public address."
      }
    ]
  }
}
```

Hostnames are additionally resolved at fetch time, so a name that points at a
private address is rejected then and the quota unit is refunded.

**Request**
```json
{ "url": "https://example.com", "target_keywords": ["coffee beans"] }
```

**`202 Accepted`**
```json
{
  "id": 42,
  "status": "pending",
  "status_url": "/api/v1/analyses/42"
}
```

**Quota accounting.** One unit is consumed when the submission is accepted and
**refunded if the analysis fails** — an unreachable host, a blocked target, or a
queue outage costs the user nothing. Refunds are idempotent, so a retried job
cannot credit the same report twice.

Errors:

- `422 validation_error` — malformed URL, or a target the fetch guard refuses.
  No quota consumed.
- `429 quota_exceeded` — daily limit reached. Includes a `Retry-After` header
  and the reset time in `details`.
- `503 service_unavailable` — the job queue was unreachable. The report is
  marked `failed` and the quota unit is refunded; retry shortly.

### GET /analyses

Paginated history for the authenticated user, newest first. **Auth required.**

**Query**: `page` (default 1, ≥1), `page_size` (default 20, 1–100).

**`200 OK`**
```json
{
  "items": [
    {
      "id": 42,
      "url": "https://example.com",
      "domain": "example.com",
      "status": "done",
      "title": "Example Domain",
      "target_keywords": ["coffee beans"],
      "overall_score": 78,
      "overall_grade": "C",
      "created_at": "2026-06-25T16:30:05Z"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20
}
```

### GET /analyses/{id}

Full report including the structured `results` payload. Returns the current
`status` — poll until it is `done` or `failed`. Only the owner can read a report.
**Auth required.**

**`200 OK`**
```json
{
  "id": 42,
  "url": "https://example.com",
  "domain": "example.com",
  "status": "done",
  "title": "Example Domain",
  "target_keywords": ["coffee beans"],
  "overall_score": 78,
  "overall_grade": "C",
  "created_at": "2026-06-25T16:30:05Z",
  "final_url": "https://example.com/",
  "job_id": "a1b2c3...",
  "error": null,
  "ttfb_ms": 120.4,
  "load_time_ms": 240.1,
  "results": { "...": "see SEO result schema below" }
}
```

`status` is one of `pending`, `running`, `done`, `failed`. When `failed`, `error`
holds the reason and `results.error` is populated, and the quota unit that the
submission consumed has been refunded. Errors: `404` if not found or not owned
by you.

**Retention.** Reports older than `REPORT_RETENTION_DAYS` (90 by default) are
deleted by a nightly job, after which this endpoint returns `404`.

### DELETE /analyses/{id}

Delete one of your reports. **Auth required.**

**`204 No Content`** · Errors: `404`.

---

## Site audits

A **site audit** crawls many pages of one site and reports which problems repeat.
It is a separate feature from a single-page analysis, with its own table, history
and quota accounting. It takes a page budget and **never takes target keywords**:
keyword placement is a judgement about one specific page, not something to average
across a crawl.

Pages are discovered from the site's sitemaps first (declared in robots.txt, else
`/sitemap.xml`, expanding one index level), falling back to a breadth-first walk of
internal links. Every candidate must be on the same host and crawlable per
robots.txt.

### POST /site-audits

Submit a site for a multi-page audit. **Consumes one daily quota unit regardless of
page count** — the page budget is what bounds the work. **Auth required.**

**Body**

| Field | Type | Rules |
|-------|------|-------|
| `url` | string (URL) | Valid `http(s)` URL pointing at a **public** host |
| `max_pages` | int | Optional, `1`–`50`, default `10`. Upper bound on pages crawled; the crawl may find fewer |

**`202 Accepted`**

```json
{
  "id": 41,
  "status": "pending",
  "status_url": "/api/v1/site-audits/41",
  "max_pages": 10
}
```

Errors: `401`, `422` (bad URL, private target, or `max_pages` out of range), `429`
(quota), `503` (queue unavailable — quota is refunded).

### GET /site-audits

Your site audits, newest first. Query: `page` (≥1), `page_size` (1–100, default 20).
**Auth required.** Returns the same envelope as `GET /analyses`, with items shaped
like the summary below.

### GET /site-audits/{id}

One site audit including the aggregate and every crawled page. **Auth required.**

```json
{
  "id": 41,
  "start_url": "https://example.com",
  "domain": "example.com",
  "status": "done",
  "max_pages": 10,
  "pages_crawled": 9,
  "pages_failed": 1,
  "discovery_source": "sitemap",
  "overall_score": 74,
  "overall_grade": "C",
  "created_at": "2026-09-12T09:12:00Z",
  "job_id": "b1f0…",
  "error": null,
  "results": {
    "score_spread": { "min": 41, "max": 92, "median": 77 },
    "issue_counts": { "critical": 2, "warning": 31, "good": 240, "info": 36 },
    "category_scores": [{ "category": "meta", "score": 68, "grade": "D", "weight": 0.2 }],
    "top_issues": [
      {
        "id": "meta_description",
        "label": "Meta description",
        "category": "meta",
        "status": "warning",
        "recommendation": "Write a 70-160 character description.",
        "affected_pages": 8,
        "total_pages": 9,
        "sitewide": true,
        "example_urls": ["https://example.com/a", "https://example.com/b"]
      }
    ],
    "worst_pages": [{ "url": "https://example.com/x", "title": "X", "score": 41, "grade": "F" }],
    "capped_pages": [{ "url": "https://example.com/x", "score": 40, "capped_by": ["meta_robots"] }],
    "errors": [{ "url": "https://example.com/gone", "error": "Fetch failed with status 404" }]
  },
  "pages": [
    {
      "id": 902,
      "url": "https://example.com/a",
      "final_url": "https://example.com/a",
      "title": "A",
      "status_code": 200,
      "overall_score": 81,
      "overall_grade": "B",
      "ttfb_ms": 96.2,
      "load_time_ms": 310.5,
      "issue_counts": { "critical": 0, "warning": 4, "good": 27, "info": 4 },
      "error": null
    }
  ]
}
```

`top_issues` is the point of the feature: every warning or critical check, counted
across the crawl and ranked by pages affected, critical first. `sitewide` marks the
ones hitting at least half the pages, which is what distinguishes a template bug
from a one-off. `discovery_source` is `"sitemap"`, `"links"` or `"mixed"`.

Errors: `401`, `404`.

### GET /site-audits/{id}/pages/{page_id}

The full analysis for one crawled page. `results` carries the **identical shape** a
single-page report produces, so the same client code renders both. **Auth required.**

Errors: `401`, `404`.

### DELETE /site-audits/{id}

Delete one of your site audits and every page it crawled. **Auth required.**

**`204 No Content`** · Errors: `404`.

---

## Health

These live under the `/api/v1` prefix like the rest of the app (the root path
`/` returns service metadata).

### GET /api/v1/health
Liveness. **`200`** `{ "status": "ok", "version": "1.0.0" }`

### GET /api/v1/ready
Readiness — checks DB and Redis connectivity.
```json
{ "status": "ready", "checks": { "database": true, "redis": true } }
```
Returns `status: "degraded"` if any dependency is down.

---

## Administration

Every route below requires the `admin` role and returns `403 forbidden`
otherwise. The first administrator cannot be created through the API, since
these endpoints already need one; make it on the server:

```bash
python -m scripts.manage_users promote you@example.com
```

Two rules apply throughout, so that no single request can leave the system with
nobody able to administer it:

- An administrator cannot change their own role, disable themselves, or delete
  themselves. Those return `403 forbidden`.
- The last enabled administrator cannot be demoted, disabled or deleted by any
  route. That returns `409 conflict`.

Demoting or disabling someone also revokes their refresh tokens, so the change
takes effect at once rather than whenever their access token expires.

### GET /admin/users

Paginated user directory, newest first.

**Query**: `page` (default 1), `page_size` (default 20, 1–100),
`search` (matches username or email), `role` (`user`/`admin`),
`is_active` (`true`/`false`).

**`200 OK`**
```json
{
  "items": [
    {
      "id": 7,
      "username": "alice",
      "email": "alice@example.com",
      "role": "user",
      "is_active": true,
      "created_at": "2026-06-25T16:30:00Z",
      "updated_at": "2026-09-10T09:12:00Z",
      "report_count": 12,
      "quota": {
        "daily_limit": 5,
        "used_today": 2,
        "monthly_limit": 100,
        "used_this_month": 31,
        "day_reset_date": "2026-09-10"
      }
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20
}
```

`quota` is null only if the user has no quota row yet. Password hashes are never
returned.

### GET /admin/users/{id}

One user, same shape as a directory row. Errors: `404 not_found`.

### PATCH /admin/users/{id}

Change a user's role or enabled status. Omitted fields are left alone, and at
least one must be present.

**Body**

| Field | Type | Rules |
|-------|------|-------|
| `role` | string | optional, `user` or `admin` |
| `is_active` | bool | optional |

**Request**
```json
{ "role": "admin" }
```

**`200 OK`** — the updated user.

Errors: `403 forbidden` when acting on yourself, `409 conflict` when it would
remove the last enabled administrator, `404 not_found`.

### PATCH /admin/users/{id}/quota

Override a user's allowance, for example to lift the free tier for a paying
customer. Omitted fields are left alone.

**Body**

| Field | Type | Rules |
|-------|------|-------|
| `daily_limit` | int | optional, 0–100000 |
| `monthly_limit` | int | optional, 0–1000000 |

**Request**
```json
{ "daily_limit": 100 }
```

**`200 OK`** — the updated user, including the new `quota`. The change applies
to the user's very next submission. A limit of `0` blocks them entirely.

### POST /admin/users/{id}/revoke-sessions

Sign a user out of every device without changing anything else.

**`200 OK`**
```json
{ "revoked": 2 }
```

### DELETE /admin/users/{id}

Delete a user along with their reports, quota and sessions, via the database
cascade.

**`204 No Content`**

Errors: `403 forbidden` when deleting yourself, `409 conflict` when it would
remove the last enabled administrator, `404 not_found`.

---

## SEO result schema

The `results` object on a completed report. Abbreviated example (checks trimmed):

```json
{
  "id": "report-1a2b3c4d",
  "url": "https://example.com",
  "final_url": "https://example.com/",
  "domain": "example.com",
  "generated_at": "2026-06-25T16:30:07Z",
  "fetched_ok": true,
  "status_code": 200,
  "overall_score": 78,
  "overall_grade": "C",
  "uncapped_score": 78,
  "capped_by": [],
  "keyword_report": null,
  "issue_counts": { "critical": 0, "warning": 5, "good": 27, "info": 4 },
  "title": "Example Domain",
  "timing": {
    "ttfb_ms": 120.4,
    "load_time_ms": 240.1,
    "transfer_size_kb": 1.3,
    "html_size_kb": 1.3,
    "compressed": true,
    "redirect_count": 0
  },
  "category_scores": [
    {
      "category": "meta",
      "score": 80,
      "grade": "B",
      "weight": 0.20,
      "checks": ["title_tag", "meta_description", "canonical", "meta_robots",
                 "html_lang", "structured_data", "open_graph", "twitter_card"]
    }
  ],
  "checks": [
    {
      "id": "title_tag",
      "category": "meta",
      "status": "good",
      "score": 100,
      "label": "Title tag",
      "value": { "title": "Example Domain", "length": 14 },
      "message": "Title length is optimal.",
      "recommendation": null
    }
  ],
  "error": null
}
```

### Top-level fields

| Field | Type | Notes |
|-------|------|-------|
| `id` | string | Engine-generated report id (distinct from the DB row id) |
| `url` / `final_url` | string | Requested vs. post-redirect URL |
| `domain` | string | Host of the final URL |
| `generated_at` | string | ISO-8601 UTC |
| `fetched_ok` | bool | Whether the page was retrieved successfully |
| `status_code` | int\|null | HTTP status of the fetch |
| `overall_score` | int | 0–100, weighted across categories, then capped (see below) |
| `overall_grade` | string | A (≥90), B (≥80), C (≥70), D (≥60), F (<60) |
| `uncapped_score` | int | The weighted score *before* caps. Equals `overall_score` unless `capped_by` is non-empty |
| `capped_by` | array | Check ids that capped the score. Empty in the normal case |
| `keyword_report` | object\|null | The keyword feature's own result. `null` unless `target_keywords` were sent. Never affects `overall_score` |
| `issue_counts` | object | Checks per status: `critical`, `warning`, `good`, `info`. Sums to `checks.length` |
| `timing` | object | See below |
| `category_scores` | array | Per-category score, grade, weight, member check ids |
| `checks` | array | Every individual check result |
| `error` | string\|null | Set when `fetched_ok` is false |

### Score caps

A page that cannot be indexed cannot rank, so three checks put a ceiling on
`overall_score` when they come back `critical`, instead of being averaged in with
everything the page does right: `meta_robots` (noindex, via either the meta tag or
an `X-Robots-Tag` response header) and `robots_txt` cap at **40**, `https` (served
over plain HTTP) caps at **60**. The lowest applicable cap wins.

`uncapped_score` is what the page would score **with the capping checks fixed and
nothing else changed**, so "capped at 40 because this page is noindex; fixing that
alone takes it to 84" is literally true. Look up the offending check in `checks[]`
by id for its `message` and `recommendation`.

**robots.txt is parsed, not pattern-matched.** Rules are grouped by user-agent per
RFC 9309 and matched longest-rule-wins. Only the `*` group and Googlebot's own group
can fail the check, so blocking a named scraper or AI crawler in its own group —
which most sites do — is reported as context and never caps the score. CRLF line
endings, trailing whitespace, a missing space after the colon, `Allow` carve-outs,
`*` wildcards and `$` anchors are all handled.

### `timing`

| Field | Type | Notes |
|-------|------|-------|
| `ttfb_ms` | float\|null | True time-to-first-byte (first body chunk) |
| `load_time_ms` | float\|null | Full document download time |
| `transfer_size_kb` | float | Bytes received over the wire |
| `html_size_kb` | float | Decoded HTML size |
| `compressed` | bool | Whether a `Content-Encoding` was present |
| `redirect_count` | int | Number of redirects followed |

### `checks[]`

| Field | Type | Notes |
|-------|------|-------|
| `id` | string | Stable check identifier (e.g. `title_tag`) |
| `category` | string | meta, content, structure, links, indexability, performance, security, mobile |
| `status` | string | `good`, `warning`, `critical`, or `info` |
| `score` | int | 0–100 contribution of this check |
| `label` | string | Human-readable name |
| `value` | any | Check-specific detail (string/number/object/array/null) |
| `message` | string | Human-readable finding |
| `recommendation` | string\|null | Actionable fix, when applicable |

### `keyword_report`

The keyword feature's own result, alongside `checks` rather than inside it. `null`
unless `target_keywords` were sent. It is **never folded into `overall_score`**.

```json
{
  "score": 72,
  "grade": "C",
  "status": "warning",
  "message": "'coffee beans' scores 72/100 on placement.",
  "recommendation": "Add 'coffee beans' to the meta description and the URL.",
  "keywords": [
    {
      "keyword": "coffee beans",
      "score": 85,
      "grade": "B",
      "found_in": { "title": "exact", "h1": "exact", "first_paragraph": "partial" },
      "missing_from": ["meta_description", "url_slug"],
      "not_applicable": ["image_alt"],
      "density_pct": 1.8,
      "over_used": false
    }
  ],
  "placement_weights": { "title": 25, "h1": 20, "meta_description": 15, "first_paragraph": 15, "subheading": 10, "url_slug": 10, "image_alt": 5 },
  "placement_labels": { "title": "title tag", "h1": "H1 heading" }
}
```

`found_in` maps a placement slot to `"exact"` (the phrase verbatim) or `"partial"`
(an inflected variant, worth half). `missing_from` is ordered most-valuable-first,
so its head is the best next fix. `not_applicable` lists slots this page cannot
have — image alt text with no images, a URL slug on a homepage — which are dropped
from the denominator rather than scored as misses. `placement_weights` and
`placement_labels` ship with every report so clients need no copy of their own.

Reports produced before this split carry the same data inside a
`keyword_targeting` check's `value`, with `average_score` in place of `score`.

`info` checks are excluded from category scoring (they neither help nor hurt the
score). See the [README](../README.md#the-seo-engine) for the full list of checks
and category weights.

---

## Data model

| Table | Key columns |
|-------|-------------|
| `users` | `id`, `username` (unique), `email` (unique), `hashed_password`, `role` (`user`/`admin`), `is_active`, timestamps |
| `quotas` | `user_id` (unique FK), `daily_limit`, `used_today`, `day_reset_date`, `monthly_limit`, `used_this_month`, `month_reset_date` |
| `seo_reports` | `id`, `user_id` (FK), `url`, `final_url`, `domain`, `status`, `job_id`, `error`, `quota_refunded`, `title`, `target_keywords` (JSON), `overall_score`, `overall_grade`, `ttfb_ms`, `load_time_ms`, `results` (JSON), timestamps. Composite index on (`user_id`, `created_at`) |
| `site_audits` | `id`, `user_id` (FK), `start_url`, `domain`, `status`, `job_id`, `error`, `quota_refunded`, `max_pages`, `pages_crawled`, `pages_failed`, `discovery_source`, `overall_score`, `overall_grade`, `results` (JSON), timestamps. Composite index on (`user_id`, `created_at`) |
| `site_audit_pages` | `id`, `audit_id` (FK, cascade), `url`, `final_url`, `title`, `status_code`, `overall_score`, `overall_grade`, `ttfb_ms`, `load_time_ms`, `issue_counts` (JSON), `error`, `results` (JSON), timestamps |
| `refresh_tokens` | `id`, `user_id` (FK), `jti` (unique), `token_hash`, `expires_at`, `revoked`, timestamps |

Passwords are SHA-256 pre-hashed then bcrypt-hashed. Refresh tokens are stored as
SHA-256 hashes (never in plaintext) and support rotation + revocation.
