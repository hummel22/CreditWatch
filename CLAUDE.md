# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CreditWatch is a local-first dashboard for tracking credit cards, annual fees, and benefits. It helps users track whether the value extracted from each card outweighs its cost. The app supports benefit tracking with multiple frequencies (monthly/quarterly/semiannual/yearly) and types (standard/incremental/cumulative), historical year-over-year views, preconfigured card templates, automated SMB backups, and Home Assistant notifications.

## Architecture

- **Backend**: FastAPI + SQLModel/SQLAlchemy with SQLite persistence (`backend/app/`)
- **Frontend**: Vue 3 (Composition API with `<script setup>`) + Vite SPA (`frontend/src/`)
- **Deployment**: Docker Compose — backend runs uvicorn, frontend builds to static files served by Nginx
- **Data**: SQLite database stored in `backend/data/` (git-ignored). Preconfigured card templates live in `backend/data/creditcards/*.json`

### Backend Structure (`backend/app/`)

- `main.py` — FastAPI app with all route definitions, benefit window calculation logic, and startup hooks
- `models.py` — SQLModel table definitions (CreditCard, Benefit, BenefitRedemption, BenefitWindowExclusion, BackupSettings, NotificationSettings, NotificationLog, Bug, InterfaceSettings)
- `schemas.py` — Pydantic v2 request/response schemas
- `crud.py` — Database query helpers
- `database.py` — Engine creation, session management, `init_db()`
- `migrations.py` — Manual schema migrations (no Alembic)
- `backup.py` — SMB backup service (smbprotocol)
- `notifications.py` — Home Assistant webhook integration
- `preconfigured.py` — Card template management from JSON files

### Frontend Structure (`frontend/src/`)

- `App.vue` — Root component
- `components/CreditCardList.vue` — Main dashboard view
- `components/CreditCardCard.vue` — Individual card display with benefits
- `components/BenefitCard.vue` — Benefit display and interaction
- `components/charts/` — ApexCharts-based visualizations (pie, bar, line, timeline)
- `utils/apiClient.js` — Axios-based API client
- `utils/benefits.js` — Benefit calculation helpers
- `utils/dates.js` — Date formatting utilities

### Key Design Patterns

- API routes are all under `/api` prefix. Frontend proxies `/api` to the backend (Vite dev proxy or Nginx in production)
- Benefits have three types: **standard** (binary used/unused), **incremental** (partial redemptions tracked via BenefitRedemption entries), **cumulative** (open-ended value accumulation)
- Year tracking can follow either **calendar** year or **anniversary** (annual fee due date) boundaries, configurable per card
- The backend uses manual migrations in `migrations.py` rather than Alembic

## Common Commands

### Local Development

```bash
# Backend (creates .venv, installs deps, starts uvicorn on :8010)
./setup_backend.sh

# Frontend (installs deps, builds, serves via vite preview on :4173)
./setup_frontend.sh

# Frontend dev mode with hot reload
cd frontend && npm run dev
```

### Docker

```bash
docker compose up --build        # Backend on :8010, frontend on :5173
docker compose down
```

### Testing

```bash
# Run all backend tests
pytest backend/tests

# Run a single test file
pytest backend/tests/test_benefit_windows.py

# Run a specific test
pytest backend/tests/test_benefit_windows.py::test_name -v
```

Tests use an in-memory SQLite database with FastAPI's TestClient. The `conftest.py` provides `client`, `engine`, and `freeze_today` fixtures. Test modules use `scope="module"` for the engine/session fixtures.

## Conventions

- Python code uses SQLModel + Pydantic v2 typing conventions
- Vue components use `<script setup>` Composition API exclusively
- The frontend is a PWA (vite-plugin-pwa) with service worker auto-updates
- Do not commit SQLite database files from `backend/data/`
- Backend port: 8010; Frontend port: 5173 (Docker) or 4173 (local preview)
- Docker service name for the backend is `creditwatch` (used in inter-container URLs)
