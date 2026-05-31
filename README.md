# SEOMATE API

Read-only HTTP API serving the Next.js inspection UI.

The auditor is the only writer to Postgres. This API exposes captures over typed JSON for the web UI to consume.

## Setup (will be filled in during Foundation week)

```bash
# from repo root
docker compose up -d

cd api
python -m venv .venv
.venv/Scripts/activate          # Windows
pip install -e ../seomate-ai    # share storage models with the auditor (sibling repo)
pip install -e ".[dev]"

uvicorn seomate_api.main:app --reload --port 8000
```

## Endpoints (planned)

See `docs/site-auditor-architecture.md` §13.5 for the full route plan. Initial routes implemented during Foundation:

- `GET /api/audits` — list audits
- `GET /api/audits/{audit_id}` — audit overview
- `GET /api/health` — readiness probe

Additional routes land alongside H1a/b/c/d as more capture data exists to expose.

---

## Multi-Repo Layout

This repo is one of three sibling repos that together form **SEOMATE Phase 1**:

| Repo | What |
|---|---|
| [`temurkhan13/seomate-ai`](https://github.com/temurkhan13/seomate-ai) | Auditor pipeline (Python CLI). Sole writer to the shared Postgres. Carries `docs/o1-taxonomy.md`. |
| [`temurkhan13/seomate-be`](https://github.com/temurkhan13/seomate-be) | Read-only FastAPI serving the inspection UI. Imports SQLAlchemy models from `seomate-ai`. |
| [`temurkhan13/seomate-fe`](https://github.com/temurkhan13/seomate-fe) | Next.js 16 + React 19 inspection UI. Talks to `seomate-be` over HTTP. |

**Original monorepo** (preserves the full 50-commit build history): [`h-chishty/seomate`](https://github.com/h-chishty/seomate). Handover authored 2026-05-15 by Humza Chishty. See `HANDOVER.md` and `ROADMAP.md` in this repo for full context, architecture, deferred work, and Phase 2/3 plans.

### Local dev across all three

Clone them as siblings under one parent directory:

```bash
mkdir seomate && cd seomate
git clone https://github.com/temurkhan13/seomate-ai.git
git clone https://github.com/temurkhan13/seomate-be.git
git clone https://github.com/temurkhan13/seomate-fe.git
```

Then per the setup notes above, `seomate-be` installs `seomate-ai` as an editable sibling: `pip install -e ../seomate-ai`.

`docker-compose.yml` lives in `seomate-be`; it boots the Postgres + pgvector instance that both the auditor and the API talk to.
