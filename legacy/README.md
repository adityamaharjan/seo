# Legacy prototype

The original single-file prototype, superseded by the `app/` package.

Kept only as a reference for behaviour that predates the rewrite. Nothing in
`app/` imports any of it, and no running process serves it: `uvicorn.service`
now points at `app.main:app`.

| File | Replaced by |
|------|-------------|
| `main.py` | `app/main.py` plus `app/api/v1/endpoints/` |
| `models.py` | `app/models/` |
| `database.py` | `app/db/session.py` |
| `schemas.py` | `app/schemas/` |
| `seo_analyzer.py` | `app/seo/` |
| `templates/` | none; the API is JSON-only and the frontend is a separate project |

Safe to delete once you are confident nothing here is still needed.
