# Changelog

## Unreleased — PageSpeed: faster crawls, desktop shown

### Changed

- **Desktop results are now shown.** Before, desktop ran on every page but was stored and never displayed. Now:
  - The page report has a **PageSpeed** panel with mobile and desktop side by side: the four Lighthouse category scores, LCP, CLS, TBT, FCP and Speed Index.
  - The Lighthouse performance check's message includes the desktop score.
  - Only mobile is scored. `PSI_STRATEGIES=mobile` still halves the time and quota.
- **PageSpeed no longer holds up the crawl.** Before, a page that ran PageSpeed held its crawl slot for 10–30 s, and the rest of that batch of 4 pages waited on it. Now PageSpeed runs alongside the crawl, up to `PSI_CONCURRENCY` (6) at a time, and pages are rescored once their results arrive. Only pages that were fetched count towards `psi_scope`.
- **The UI time estimate** now accounts for parallel runs.

### Added

- **A dead key stops early.** When Google rejects the key or reports it out of quota (400 invalid, 403, 429), the remaining PageSpeed runs in that audit are skipped. Those pages say why they have no PageSpeed data.
- **Deadline:** a PageSpeed run still going 60 s after the crawl deadline is cancelled, and that page reports why it has no data. This keeps audits inside the worker's job timeout.
- **A site-wide PageSpeed table.** Site audit results gain a `pagespeed` list, and the report shows a **PageSpeed** table: mobile and desktop Lighthouse scores, mobile LCP, CLS and TBT, and the vitals verdict, slowest first. Older audits don't have it and simply don't show the table.

### Deploying

- **uv is now the only Python package manager.** `requirements.txt` is gone;
  `pyproject.toml` and `uv.lock` are the single source of dependencies.
- **Docker:** the image now runs Python 3.13 (it was 3.12, which nothing was
  tested on), installs from `uv.lock` without dev tools, and no longer copies
  `.env` into the image.
- **systemd servers, one-time switch:** the units now run from `.venv` instead
  of `.seo`. On the server:
  ```bash
  sudo mkdir -p /opt/uv/python && sudo chown "$USER" /opt/uv/python
  cd /var/www/seo && UV_PYTHON_INSTALL_DIR=/opt/uv/python uv sync --locked --no-dev
  sudo cp deploy/*.service /etc/systemd/system/ && sudo systemctl daemon-reload
  sudo systemctl restart uvicorn seo-worker
  ```
  The old `.seo` directory can be deleted once both services are running.
- No database migration needed.

## 2026-09-17 — PageSpeed Insights

Reports and site audits can now include rendered performance data (Core Web Vitals and Lighthouse scores) from the Google PageSpeed Insights (PSI) API. Each user supplies their own key. Commit `836e6ab`.

### Added

- **Five new checks in the `performance` category.** They run only when the run used PageSpeed. Without it, they show as `info` and are not scored.
  | Check | Scored | What it measures |
  |-------|--------|------------------|
  | `field_vitals` | weight 3.0 | Real-user Core Web Vitals (LCP, INP, CLS) from CrUX at the 75th percentile. Uses origin-level data when the URL has too little traffic. |
  | `core_web_vitals` | weight 2.0 | Lab LCP, CLS and TBT from a Lighthouse run. The worst metric sets the verdict. |
  | `lighthouse_performance` | weight 2.0 | Lighthouse's 0–100 performance score. |
  | `pagespeed_opportunities` | no | Lighthouse's fixes, ranked by estimated savings (at most 8, each saving ≥100 ms). |
  | `lighthouse_categories` | no | Lighthouse accessibility, best-practices and SEO scores. |
- **Mobile is scored.** When both strategies run, desktop results are kept in the payload for display only.
- **`use_psi` on `POST /analyses` and `POST /site-audits`.** It takes three values: `true` requires PageSpeed, `false` skips it, and omitting it uses the account's saved key when one exists.
- **`psi_scope` on `POST /site-audits`**: `off`, `homepage`, `sample` (the first 5 pages in crawl order) or `all`. The API defaults to `all`; the UI defaults to `homepage`.
- **`used_psi` on reports**, and `used_psi` and `psi_scope` on site audits, so consumers can tell which runs include rendered metrics.
- **UI:** the page-audit and site-audit forms have a PageSpeed control. It is on by default when a key is saved, and disabled with a link to Account settings when no key is saved. The site-audit form also has a coverage picker. Reports show the ranked opportunity list.
- **Key health:** every run records `last_used_at` / `last_error` on the user's stored PSI key, so a key that runs out of quota shows up in Account settings.

### Changed

- The `core_web_vitals` check is no longer a disabled placeholder. Its weight went from 1.0 to 2.0, and it now scores lab data when PageSpeed ran.
- Performance scores are only comparable between runs with the same `used_psi` value. When PageSpeed runs, it makes up about half of the performance category.

### Behaviour worth knowing

- **PageSpeed never fails a report.** If Google is slow, rate-limiting or down, the run loses its PageSpeed data and the rest of the report is still produced. PSI calls are never retried.
- **`use_psi: true` with no saved key returns `400` at submit time**, before any quota is charged. If `use_psi` is omitted, the run silently goes ahead without PageSpeed.
- **Decrypted keys never enter the job queue.** The worker reads the key again when the job runs. If the key was deleted in between, the run continues without PageSpeed.
- **Cost:** each PSI run takes about 10–30 s per page per strategy and uses one unit of the key's 25,000/day quota. Running `all` on a 50-page crawl takes much longer than the same crawl without PageSpeed.

### Deploying

- **Migration required:** `alembic upgrade head` (revision `b4e2c8a71f03`). It adds `seo_reports.used_psi`, `site_audits.used_psi` and `site_audits.psi_scope`. Existing rows default to `false` / `NULL`.
- **New env vars** (see `.env.example`):
  - `GOOGLE_PAGE_SPEED_INSIGHTS_API_KEY`: a fallback key for development only. It is **ignored when `ENVIRONMENT=production`**, where users must bring their own key.
  - `PSI_TIMEOUT_SECONDS` (default `90`), `PSI_STRATEGIES` (default `mobile,desktop`), `PSI_CONCURRENCY` (default `6`, the number of concurrent PSI calls per audit).
- API changes are additive. Existing clients that don't send `use_psi` get PageSpeed automatically once the user saves a key.

### Docs and tests

- `docs/API.md` has a new **PageSpeed Insights** section.
- New tests: `tests/seo/test_psi.py` and `tests/test_psi_opt_in.py`.
