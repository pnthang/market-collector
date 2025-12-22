from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text
import logging

from .db import engine
from . import vn_scraper
from . import yahoo_scraper
from pydantic import BaseModel

LOG = logging.getLogger("health")

app = FastAPI(title="market-collector-health")


def check_db() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        LOG.exception("DB health check failed")
        return False


@app.get("/health")
def health():
    db_ok = check_db()
    status = "ok" if db_ok else "fail"
    code = 200 if db_ok else 500
    return JSONResponse(status_code=code, content={"status": status, "db": db_ok})


@app.get("/ready")
def ready():
    db_ok = check_db()
    # check scraper readiness flag
    scraper_ready = getattr(vn_scraper, "SCRAPER_READY", False)
    ok = db_ok and scraper_ready
    code = 200 if ok else 500
    return JSONResponse(status_code=code, content={"status": "ok" if ok else "fail", "db": db_ok, "scraper_ready": scraper_ready})


def run(host: str = "0.0.0.0", port: int = 8080):
    import uvicorn

    uvicorn.run("app.health:app", host=host, port=port, log_level="info")


class IntervalSeconds(BaseModel):
    seconds: int


class IntervalHours(BaseModel):
    hours: int


@app.post('/control/vn/start')
def control_vn_start():
    vn_scraper.start_scraper()
    return {"status": "started"}


@app.post('/control/vn/stop')
def control_vn_stop():
    vn_scraper.stop_scraper()
    return {"status": "stopped"}


@app.post('/control/vn/interval')
def control_vn_interval(payload: IntervalSeconds):
    ok = vn_scraper.set_snapshot_interval(payload.seconds)
    return {"ok": ok}


@app.post('/control/yahoo/start')
def control_yahoo_start():
    yahoo_scraper.start_scheduler()
    return {"status": "started"}


@app.post('/control/yahoo/stop')
def control_yahoo_stop():
    yahoo_scraper.stop_scheduler()
    return {"status": "stopped"}


@app.post('/control/yahoo/interval')
def control_yahoo_interval(payload: IntervalHours):
    ok = yahoo_scraper.set_scheduler_interval(payload.hours)
    return {"ok": ok}
