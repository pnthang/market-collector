
# Market Collector

A backend data collector for the Market Analyze project. This service gathers Yahoo Finance index data, related analysis, insights, and news using Python, Playwright, and PostgreSQL—all orchestrated with Docker.

## Features

- **Automated Data Collection:** Scrapes index prices, metadata, analysis, and news from Yahoo Finance.
- **Python + Playwright:** Robust scraping with headless browser automation.
- **PostgreSQL Database:** Stores all collected data in a structured, queryable format.
- **Dockerized Deployment:** Easy to run, scale, and manage.
- **Scheduled Tasks:** 
  - Index price scraping every 15 seconds.
  - Content/news scraping every 2 hours.
- **Extensible Architecture:** Ready for integration with analytics tools (e.g., Kafka, Grafana).

## Architecture

```
┌────────────┐
│  Scheduler │
└─────┬──────┘
      │
┌─────▼───────────────────────────┐
│        Python Services           │
│  ┌──────────────┐  ┌──────────┐ │
│  │ Index Scraper│  │ Content  │ │
│  │   (15s)      │  │ Scraper  │ │
│  │ Playwright   │  │   (2h)    │ │
│  └──────┬───────┘  └─────┬────┘ │
└─────────┼─────────────────┼──────┘
          ▼                 ▼
   ┌────────────────────────────────┐
   │          PostgreSQL            │
   │  indexes_prices                │
   │  index_metadata                │
   │  index_analysis                │
   │  index_news                    │
   └────────────────────────────────┘
```

## Database Schema

- `indexes_prices`: Stores time-series price data for each index.
- `index_metadata`: Contains static information about each index.
- `index_analysis`: Holds analysis and insights.
- `index_news`: Aggregates related news articles.

## Reliability & Scaling

- **Docker:** Ensures consistent environments and easy scaling.
- **Scheduling:** Uses APScheduler for job scheduling and graceful shutdown.
- **Health checks:** HTTP `/health` and `/ready` endpoints are provided (port 8080) to verify DB connectivity.
- **Compliance:** Designed to respect data source terms of service.

## Quickstart — Local (Python)

- Create a virtualenv and install dependencies:

  pip install -r requirements.txt

- Provide DB connection via `.env` or environment variables (see `.env.example`). Example using Postgres:

  export DB_USER=postgres
  export DB_PASSWORD=postgres
  export DB_HOST=localhost
  export DB_PORT=5432
  export DB_NAME=market

- Run the service (starts scraper + health server):

  python -m app

The health endpoint will be available at `http://localhost:8080/health`.

## Quickstart — Docker

- Build and run with Docker Compose (includes Postgres service):

  docker compose up --build

- Or build and run manually:

  docker build -t market-collector:latest .
  docker run -d --name market-collector -e DATABASE_URL="postgresql+psycopg2://user:pass@host:5432/market" -p 8282:8080 market-collector:latest

## Fetching Index Groups (VN30, VNALL)

- HTTP-first fetch (falls back to Playwright if blocked):

  python -m app.data_scraper.fetch_group_auto VN30

- Fetch multiple groups (defaults to `VN30` and `VNALL`):

  python -m app.data_scraper.fetch_groups

## Systemd (host) — run container as a service

- Install the provided systemd unit (must run as root):

  sudo ./scripts/install_systemd.sh
  sudo systemctl start market-collector.service
  sudo systemctl status market-collector.service

The unit expects a container named `market-collector` (the `scripts/setup_ubuntu.sh` creates and runs this container).

## Files of interest

- `app/` — main application package (see `app/data_scraper/` for scrapers, `app/db/` for DB models, health endpoint)
- `app/data_scraper/fetch_group_playwright.py` — Playwright-backed group fetcher
- `app/data_scraper/fetch_group_auto.py` — HTTP-first fetch with Playwright fallback
- `Dockerfile`, `docker-compose.yml` — containerization
- `scripts/setup_ubuntu.sh` — helper to clone, build, and run using PAT
- `systemd/market-collector.service` — example systemd unit

## Notes & Next Steps

- Health checks currently validate DB connectivity. I can extend `/ready` to include scheduler/browser readiness.
- For production, use a secure credential method instead of embedding PATs in clone URLs. Use secrets/credential helpers.

- Database migrations: Alembic is configured and an initial migration has been added at `alembic/versions/0001_initial.py`.
  To create/apply migrations locally, ensure `DATABASE_URL` is set and run:

  ```bash
  pip install -r requirements.txt
  alembic upgrade head
  ```
  Review generated migrations before applying in production.

- Local secrets: the `scripts/setup_ubuntu.sh` script supports a local secrets file named `.market_collector_env`.
  Place a file with the following format in one of these locations (script checks in this order):

  - `scripts/.market_collector_env` (next to the script)
  - `./.market_collector_env` (current directory)
  - `~/.market_collector_env` (your home directory)

  Example contents (do NOT commit real secrets):

  ```ini
  GITHUB_PAT=ghp_xxx
  DB_CONN='postgresql+psycopg2://user:pass@host:5432/db'
  ```

  The repository ignores `.market_collector_env` to prevent accidental commits.

**Control API**

The service exposes simple HTTP control endpoints (on host port 8282 by default) to start/stop scrapers and change their intervals.

- **Start VN scraper:** `POST /control/vn/start`
- **Stop VN scraper:** `POST /control/vn/stop`
- **Set VN snapshot interval:** `POST /control/vn/interval` with JSON body `{"seconds": 15}`

- **Start Yahoo scheduler:** `POST /control/yahoo/start`
- **Stop Yahoo scheduler:** `POST /control/yahoo/stop`
- **Set Yahoo interval:** `POST /control/yahoo/interval` with JSON body `{"hours": 2}`

Examples (default port 8282):

```bash
curl -X POST http://localhost:8282/control/vn/start
curl -X POST http://localhost:8282/control/vn/interval -H "Content-Type: application/json" -d '{"seconds":15}'
curl -X POST http://localhost:8282/control/yahoo/interval -H "Content-Type: application/json" -d '{"hours":2}'
```

Notes:
- Data inserts deduplicate on `(index_code, timestamp)` so only new samples are stored.
- VN snapshots run by default every 15s and Yahoo fetches every 2 hours; use the API above to change them at runtime.
