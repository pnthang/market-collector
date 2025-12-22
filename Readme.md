
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
- **Scheduling:** Uses cron or similar tools for reliable, repeatable scraping.
- **Compliance:** Designed to respect data source terms of service.

## Future Enhancements

- **Grafana Dashboards:** For real-time data visualization.
- **Kafka Integration:** For streaming data to downstream analytics.


Let us know if you want to contribute or need more technical details!
