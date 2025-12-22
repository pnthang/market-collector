# vnindex-todo.md
# Public VN Index Scraper (iBoard SSI – No Login)

## Goal
Build a Dockerized Python service that:
- Scrapes **public VN index data** from https://iboard.ssi.com.vn/
- Uses **Playwright WebSocket interception**
- Collects index snapshots every **15 seconds**
- Runs **only during Vietnam market hours**
- Stores data in **PostgreSQL**
- Requires **NO LOGIN, NO API KEYS**

---

## 1. Project Initialization

- [ ] Initialize Python 3.11 project
- [ ] Create folder structure:
  - app/
  - app/scraper/
  - app/db/
  - app/utils/
- [ ] Create requirements.txt:
  - playwright
  - psycopg2-binary
  - sqlalchemy
  - apscheduler
  - pytz
  - python-dotenv
- [ ] Install Playwright Chromium
- [ ] Configure logging (stdout)

---

## 2. Docker Setup

- [ ] Create Dockerfile
  - python:3.11-slim
  - Install Playwright system deps
  - Install Chromium
- [ ] Create docker-compose.yml
  - scraper service
  - postgres service
  - shm_size >= 1gb
- [ ] Set timezone support (Asia/Ho_Chi_Minh)
- [ ] Add .dockerignore

---

## 3. Configuration & Environment

- [ ] Create `.env.example`
- [ ] Define env variables:
  - DB_HOST
  - DB_PORT
  - DB_NAME
  - DB_USER
  - DB_PASSWORD
  - MARKET_TZ=Asia/Ho_Chi_Minh
- [ ] Load env vars in Python config module

---

## 4. Database Schema

### Tables

- [ ] Create `indexes` table
  - code (VNINDEX, VN30, HNXINDEX, UPCOM, etc.)
  - name
- [ ] Create `index_prices` table
  - index_code
  - price
  - change
  - change_percent
  - timestamp (UTC)
- [ ] Add index on (index_code, timestamp)
- [ ] Add DB initialization script

---

## 5. Market Hours Logic (Vietnam)

- [ ] Implement market hours checker:
  - Morning: 09:00 – 11:30
  - Afternoon: 13:00 – 15:00
- [ ] Skip weekends
- [ ] Timezone-aware logic (Asia/Ho_Chi_Minh)
- [ ] Prevent scraping outside market hours

---

## 6. Playwright Browser Manager

- [ ] Create reusable Playwright browser factory
- [ ] Use Chromium (headless)
- [ ] Disable images, fonts, media
- [ ] Randomize user agent
- [ ] Single browser instance
- [ ] Graceful shutdown & restart

---

## 7. WebSocket Interception (Core Task)

- [ ] Open https://iboard.ssi.com.vn/
- [ ] Attach WebSocket listeners:
  - page.on("websocket")
  - ws.on("framereceived")
- [ ] Log all WebSocket frames (debug mode)
- [ ] Identify index-related messages
- [ ] Parse JSON payloads
- [ ] Extract:
  - index code
  - last price
  - change
  - percent change
  - event timestamp

---

## 8. Index Discovery (Dynamic)

- [ ] Auto-discover index codes from WebSocket data
- [ ] Store new indexes in `indexes` table
- [ ] Do NOT hardcode index list
- [ ] Ignore non-index messages

---

## 9. Snapshot Logic (15s)

- [ ] Maintain in-memory cache of last index values
- [ ] Every 15 seconds:
  - Take latest value per index
  - Normalize data
  - Convert timestamps to UTC
- [ ] Avoid duplicate inserts
- [ ] Batch insert into PostgreSQL

---

## 10. Scheduler & Runtime Loop

- [ ] Use APScheduler or async loop
- [ ] Start scraping only during market hours
- [ ] Reconnect WebSocket if disconnected
- [ ] Keep browser alive throughout session
- [ ] Restart browser on fatal errors

---

## 11. Error Handling & Stability

- [ ] Catch Playwright timeouts
- [ ] Handle WebSocket disconnects
- [ ] Auto-retry with backoff
- [ ] Log raw frames on parse errors
- [ ] Continue running on partial failures

---

## 12. Performance Considerations

- [ ] One browser, one page
- [ ] No page reload loops
- [ ] No DOM scraping
- [ ] No polling HTTP endpoints
- [ ] Batch DB inserts

---

## 13. Validation & Testing

- [ ] Validate numeric fields
- [ ] Validate timestamps
- [ ] Dry-run mode (no DB write)
- [ ] Local test with short runtime

---

## 14. Documentation

- [ ] Create README.md
- [ ] Document:
  - How WebSocket scraping works
  - Market hours logic
  - Database schema
  - Docker usage
- [ ] Add example SQL queries

---

## 15. Future Enhancements (Optional)

- [ ] Add historical backfill
- [ ] Add Prometheus metrics
- [ ] Add Grafana dashboards
- [ ] Export to Parquet
- [ ] Multi-market support

---

## Constraints

- NO login
- NO private APIs
- NO scraping behind auth
- ONLY public WebSocket data
- Respect reasonable resource usage
