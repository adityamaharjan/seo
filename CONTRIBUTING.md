# Contributing

Thanks for helping improve SEO Analysis. Bug reports, fixes, new SEO checks,
docs and UI improvements are all welcome.

## Ways to help

- **Report a bug:** open an issue. Include the URL you analyzed (if it's public),
  what you expected, what you got, and any error from the API or browser console.
- **Suggest a feature:** open an issue describing the problem it solves before
  writing a lot of code, so we can agree on the approach first.
- **Send a fix or feature:** open a pull request, as described below.

## Sending a change

All changes reach this repository through pull requests. Nobody pushes to
`main` directly.

1. **Fork** the repository on GitHub (the **Fork** button), then clone your fork:
   ```bash
   git clone https://github.com/<you>/seo.git
   cd seo
   git remote add upstream https://github.com/adityamaharjan/seo.git
   ```
2. **Branch** from an up-to-date `main`:
   ```bash
   git fetch upstream
   git switch -c my-feature upstream/main
   ```
3. **Commit** your change, with the checks below passing, and push the branch
   to your fork: `git push origin my-feature`.
4. **Open a pull request** from your branch to `adityamaharjan/seo:main`.
   GitHub offers a button for this right after you push. Describe what it
   changes and why, and link the issue if there is one.
5. **Review:** CI runs automatically, and the maintainer reviews the change.
   Push more commits to the same branch to address feedback. Once it's
   approved and green, it is merged into `main`.

If `main` moves on while you work, update your branch with
`git fetch upstream && git rebase upstream/main`, then `git push --force-with-lease`.

## Setting up

You need Python 3.13+, [uv](https://docs.astral.sh/uv/), and Node 22+.
MySQL and Redis are only needed to run the full app. The test suite uses
in-memory SQLite and mocks the network.

```bash
# Backend
uv sync                       # installs app and dev tools from uv.lock
cp .env.example .env          # then fill in DB / JWT / Redis values
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8001
uv run arq app.workers.settings.WorkerSettings   # in a second terminal

# Frontend
cd frontend
npm install
npm run dev                   # http://localhost:5173, proxies /api to :8001
```

The [README](README.md) covers configuration, architecture and the SEO engine
in depth. [docs/API.md](docs/API.md) is the endpoint reference.

## Before you open a pull request

Run the same checks CI runs. A pull request needs all of them passing:

```bash
uv run ruff check app tests
uv run mypy app
uv run pytest --cov           # fails below 70% coverage

cd frontend
npm run lint
npm test
npm run build
```

## How the code is written

Following these keeps reviews quick:

- **Keep the layers.** Endpoints in `app/api/` stay thin and call services in
  `app/services/`, which use `app/crud/` for database access. SEO checks live in
  `app/seo/checks/`, one function per check, registered in that module's `CHECKS`.
- **Test what you change.** New logic comes with a test. SEO checks are tested
  against the HTML fixtures in `tests/seo/fixtures/`, and nothing in the suite
  touches the real network.
- **Comment the why, not the what.** The existing docstrings explain the reason
  behind each decision (thresholds, weights, trade-offs). New code should do
  the same where the reason isn't obvious from the code.
- **Database changes need a migration:** `uv run alembic revision --autogenerate -m "..."`.
- **Update the docs** in `docs/API.md` when you change an endpoint or a
  response shape, and add a line to `CHANGELOG.md` under "Unreleased".
- **Keep pull requests focused.** One fix or feature per pull request is far
  easier to review than several mixed together.

## Security issues

Please don't open a public issue for a security vulnerability, such as a way
to bypass the private-address guard or read another user's reports. Use
GitHub's private vulnerability reporting instead: the repository's
**Security** tab, then **Report a vulnerability**.

## License

By contributing, you agree that your contribution is released under this
project's [LICENSE](LICENSE): MIT with an attribution term. You can add your
name to the credit of a copy you modify or host, but the original
"Created by @adityamaharjan" credit stays.
