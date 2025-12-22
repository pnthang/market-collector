Backend data collector for Market Analyze project. 
collect Yahoo Finance index data and related analysis/insights/news, using Python + Playwright + PostgreSQL, all running in Docker.

Overall architecture

Data acquisition strategy (what + how)

Scheduling & timing (15s + 2h)

Database schema design (PostgreSQL)

Playwright scraping approach

Docker setup

Reliability, scaling, and compliance considerations

1. High-Level Architecture
┌────────────┐
│   Cron /   │
│  Scheduler │
└─────┬──────┘
      │
┌─────▼───────────────────────────┐
│        Python Services           │
│                                  │
│  ┌──────────────┐  ┌──────────┐ │
│  │ Index Scraper│  │ Content  │ │
│  │ (15s)        │  │ Scraper  │ │
│  │ Playwright   │  │ (2h)     │ │
│  └──────┬───────┘  └─────┬────┘ │
│         │                 │      │
└─────────┼─────────────────┼──────┘
          ▼                 ▼
   ┌────────────────────────────────┐
   │          PostgreSQL              │
   │  indexes_prices                  │
   │  index_metadata                  │
   │  index_analysis                  │
   │  index_news                      │
   └────────────────────────────────┘

Add Grafana dashboards

Kafka for downstream analytics
