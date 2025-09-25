# CreditWatch

CreditWatch is a local-first dashboard for tracking credit cards, their annual fees, and ongoing benefits. It helps you make sure you never miss a benefit and understand whether the value you extract from each card outweighs its cost.

## Features

- 📇 Manage an unlimited list of credit cards with account name, last four digits, annual fee, and fee due date.
- 🎁 Track monthly, quarterly, or annual benefits for each card, including their value, description, and expiration.
- ✅ Mark benefits as used to keep a running tally of realized value versus your annual fees.
- 📊 Gorgeous, card-based Vue 3 interface with at-a-glance progress bars for each credit card.
- 🗂️ SQLite persistence so your data lives alongside the app when run locally or inside Docker.

## Project layout

```
backend/        # FastAPI application, SQLModel models, and SQLite database utilities
frontend/       # Vue 3 + Vite single page application
backend/data/   # Persisted SQLite database files (ignored from git)
```

## Getting started locally

A convenience script is included to bootstrap both the Python and JavaScript dependencies and then start the backend API server.

```bash
./setup.sh
```

This command will:

1. Create a Python virtual environment in `.venv` (if missing) and install backend dependencies.
2. Install the frontend dependencies with `npm install`.
3. Launch the FastAPI development server on `http://127.0.0.1:8010`.

> **Note:** The Vue development server is not started automatically. After running `setup.sh`, open a new terminal and launch the UI:
>
> ```bash
> cd frontend
> npm run dev -- --host
> ```
>
> The interface will be available at `http://127.0.0.1:5173` and is configured to proxy API requests to the backend.

## Running with Docker Compose

If you prefer containers, the project ships with a ready-to-use Compose definition.

```bash
docker compose up --build
```

- The FastAPI backend is exposed on [http://localhost:8010](http://localhost:8010).
- The Vue.js frontend is served by Nginx on [http://localhost:5173](http://localhost:5173).
- SQLite data persists between runs via the `backend/data` bind mount.

Stop the stack with `docker compose down`.

## API reference

The backend exposes a REST API under `/api`. The most important endpoints are:

| Method | Endpoint                              | Description                                  |
|--------|---------------------------------------|----------------------------------------------|
| GET    | `/api/cards`                          | List all cards with benefits and tallies.    |
| POST   | `/api/cards`                          | Create a new credit card.                    |
| PUT    | `/api/cards/{card_id}`                | Update a credit card.                        |
| DELETE | `/api/cards/{card_id}`                | Delete a card and its benefits.              |
| POST   | `/api/cards/{card_id}/benefits`       | Attach a benefit to a card.                  |
| POST   | `/api/benefits/{benefit_id}/usage`    | Mark a benefit as used or reset it.          |
| DELETE | `/api/benefits/{benefit_id}`          | Remove a benefit from a card.                |
| GET    | `/api/frequencies`                    | Enumerate available benefit frequencies.     |

FastAPI automatically exposes interactive docs at [http://localhost:8010/docs](http://localhost:8010/docs).

## Using the app

1. Add a credit card with its fee details using the "Add a credit card" form.
2. Select a card and add benefits such as travel credits or dining offers, including their value and reset cadence.
3. When you use a benefit, hit **Mark used**—the dashboard will adjust the utilized total and net position.
4. Review the progress bars to see which cards are paying for themselves and which still need attention.

## Development tips

- The backend automatically creates the SQLite database on first run. Database files live in `backend/data`.
- Frontend API requests are relative to `/api`, which is proxied in development (Vite) and in production (Nginx) to the FastAPI service.
- Hot reloading is available on both the backend (`uvicorn --reload`) and frontend (`npm run dev`).

## License

This project is provided for internal testing and evaluation purposes.
