# TODO – Yahoo Finance Index Data Collector

## Goal
Build a Dockerized Python service that uses Playwright to collect:
1. All Yahoo Finance index prices every 15 seconds during US market hours (9:30 AM–4:00 PM EST)
2. Index-related Analysis, Insights, and News every 2 hours
3. Store all data in PostgreSQL

---

## 1. Project Setup

- [ ] Initialize Python project (Python 3.11)
- [ ] Create virtual environment support
- [ ] Add requirements.txt:
  - playwright
  - psycopg2-binary
  - sqlalchemy
  - pandas
  - apscheduler
  - pytz
  - python-dotenv
- [ ] Install Playwright Chromium
- [ ] Configure logging (stdout + file)

---

## 2. Docker Setup

- [ ] Create Dockerfile
  - Base image: python:3.11-slim
  - Install Playwright dependencies
  - Install Chromium
  - Set timezone support
- [ ] Create docker-compose.yml
  - Service: scraper
  - Service: postgres (v15)
  - Configure environment variables
  - Configure shared network
- [ ] Add .dockerignore

---

## 3. Configuration Management

- [ ] Create `.env.example`
- [ ] Define environment variables:
  - DB_HOST
  - DB_PORT
  - DB_NAME
  - DB_USER
  - DB_PASSWORD
  - MARKET_TIMEZONE=US/Eastern
- [ ] Load env variables in Python

---

## 4. Database Design

- [ ] Create SQLAlchemy models:
  - index_metadata
  - index_prices
  - index_analysis
  - index_news
- [ ] Create database initialization script
- [ ] Add indexes on (symbol, timestamp)
- [ ] Support batch inserts

---

## 5. Yahoo Finance Index Discovery

- [ ] Create scraper to fetch all available Yahoo Finance indexes
- [ ] Scrape from:
  - https://finance.yahoo.com/world-indices/
- [ ] Extract:
  - index symbol
  - index name
  - exchange
  - currency
- [ ] Store metadata in index_metadata table
- [ ] Cache index list locally (do not fetch every run)

---

## 6. Index Price Scraper (15s)

- [ ] Create Playwright browser manager
- [ ] Use headless Chromium
- [ ] Disable images and fonts for performance
- [ ] Rotate user agents
- [ ] Navigate to Yahoo Finance index pages
- [ ] Prefer XHR/network interception over DOM scraping
- [ ] Extract:
  - symbol
  - price
  - change
  - percent change
  - volume (if available)
  - timestamp (UTC)
- [ ] Validate numeric fields
- [ ] Batch insert into index_prices
- [ ] Handle transient failures with retries

---

## 7. Market Hours Logic

- [ ] Implement US market hours checker
- [ ] Convert EST to UTC (DST aware)
- [ ] Ensure price scraper only runs:
  - Weekdays
  - 9:30 AM – 4:00 PM EST
- [ ] Skip execution outside market hours

---

## 8. Analysis & Insights Scraper (2h)

- [ ] Scrape index analysis pages:
  - https://finance.yahoo.com/quote/{SYMBOL}/analysis
- [ ] Extract:
  - title
  - summary
  - source
  - publish timestamp
  - article URL
- [ ] Store in index_analysis table
- [ ] Deduplicate by URL

---

## 9. News Scraper (2h)

- [ ] Scrape index news pages:
  - https://finance.yahoo.com/quote/{SYMBOL}/news
- [ ] Scroll to load dynamic content
- [ ] Extract:
  - headline
  - summary
  - publisher
  - publish timestamp
  - article URL
- [ ] Store in index_news table
- [ ] Deduplicate by URL

---

## 10. Scheduler

- [ ] Use APScheduler
- [ ] Configure jobs:
  - Index prices: every 15 seconds (market hours only)
  - News & analysis: every 2 hours
- [ ] Ensure scheduler starts on container startup
- [ ] Graceful shutdown handling

---

## 11. Error Handling & Resilience

- [ ] Implement retry logic with exponential backoff
- [ ] Catch Playwright timeouts
- [ ] Log all failures
- [ ] Continue execution on partial failures
- [ ] Add basic health check endpoint or log heartbeat

---

## 12. Performance & Storage Optimization

- [ ] Batch DB inserts
- [ ] Optional: partition index_prices by date
- [ ] Optional: TimescaleDB compatibility
- [ ] Limit browser instances

---

## 13. Testing & Validation

- [ ] Add unit tests for:
  - Market hours logic
  - Timestamp conversion
  - Data validation
- [ ] Add dry-run mode (no DB writes)
- [ ] Validate schema migrations

---

## 14. Documentation

- [ ] Create README.md
- [ ] Document:
  - Architecture
  - Setup steps
  - Environment variables
  - Running locally
  - Running with Docker
- [ ] Add example queries

---

## 15. Future Enhancements (Optional)

- [ ] Grafana dashboard
- [ ] Kafka or Redis integration
- [ ] Alerting on scraper failures
- [ ] Cloud deployment (ECS / GCP / K8s)
- [ ] API layer for querying data
