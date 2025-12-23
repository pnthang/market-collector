Docker Quickstart — Market Collector

1) Copy env and edit credentials:

```bash
cp .env.docker.example .env
# edit .env and set DB_PASSWORD and SECRET_TOKEN
```

2) Build and start containers:

```bash
docker compose -f docker-compose.full.yml up --build -d
```

3) Initialize the database (runs an init_job container defined in compose):

```bash
docker compose -f docker-compose.full.yml run --rm init_db
```

4) (Optional) Start the Celery worker if not started by compose:

```bash
docker compose -f docker-compose.full.yml up -d worker
```

5) Tail logs:

```bash
docker compose -f docker-compose.full.yml logs -f --tail=200
```

6) Smoke test the API (use `SECRET_TOKEN` from `.env`):

```bash
curl -H "Authorization: Token $SECRET_TOKEN" http://localhost:8000/health
```

Notes
- Ensure Playwright dependencies are installed in the image. If your `Dockerfile` does not run `playwright install chromium`, add it to the image build or run `docker compose run --rm web playwright install chromium` once.
- If you prefer Docker Compose v2 CLI, replace `docker compose` with `docker-compose`.
