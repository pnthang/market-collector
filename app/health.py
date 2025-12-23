from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text
import logging
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Callable
import os

from .db import engine
from . import vn_scraper
from . import yahoo_scraper
from pydantic import BaseModel
from .config import API_TOKEN

LOG = logging.getLogger("health")

app = FastAPI(title="market-collector-health")


# Middleware to enforce simple token auth on all endpoints except /health
class TokenAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, token: str):
        super().__init__(app)
        self.token = token

    async def dispatch(self, request: Request, call_next: Callable):
        # allow unauthenticated health check
        if request.url.path == "/health":
            return await call_next(request)

        # if no token configured, skip auth
        if not self.token:
            return await call_next(request)

        # try header `x-api-token` or `Authorization: Bearer ...`
        token = request.headers.get("x-api-token")
        if not token:
            auth = request.headers.get("authorization") or request.headers.get("Authorization")
            if auth and auth.lower().startswith("bearer "):
                token = auth.split(None, 1)[1].strip()

        if token != self.token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API token")

        return await call_next(request)


# attach middleware
app.add_middleware(TokenAuthMiddleware, token=API_TOKEN)


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


@app.post('/control/vn/snapshot')
def control_vn_snapshot(force: bool = False):
    """Trigger an immediate one-time snapshot from the running VN scraper.

    If `force` is true, bypasses the market-hours check so snapshots can be
    performed for testing outside market hours. Returns a simple OK/fail
    payload.
    """
    # ensure scraper instance exists
    inst = getattr(vn_scraper, "SCRAPER_INSTANCE", None)
    if inst is None:
        return {"ok": False, "reason": "scraper not running"}

    # optionally bypass market-hours check for testing
    if force:
        from . import utils

        orig = utils.is_market_open_at
        try:
            utils.is_market_open_at = lambda now, tz=None: True
            inst._take_snapshot()
        finally:
            utils.is_market_open_at = orig
    else:
        inst._take_snapshot()

    return {"ok": True}
