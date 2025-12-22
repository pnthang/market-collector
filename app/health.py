from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text
import logging

from .db import engine
from . import vn_scraper

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
