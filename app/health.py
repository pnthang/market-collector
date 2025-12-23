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
from fastapi.responses import HTMLResponse, PlainTextResponse
from .config import LOG_FILE
import io
import os
from typing import List
import base64
import tempfile
import time
from .playwright_manager import BrowserManager
from .db import SessionLocal
from .models import IndexTracking

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


@app.post('/control/yahoo/interval_seconds')
def control_yahoo_interval_seconds(payload: IntervalSeconds):
    ok = yahoo_scraper.set_price_interval(payload.seconds)
    return {"ok": ok}


@app.post('/control/yahoo/price_run')
def control_yahoo_price_run():
    ok = yahoo_scraper.run_price_once()
    return {"ok": ok}


@app.post('/control/yahoo/force_eastern')
def control_yahoo_force_eastern(enable: bool = True):
    """Toggle forcing US/Eastern for market-hours checks used by the Yahoo price job.

    Use `?enable=true` or `?enable=false` as a query parameter.
    """
    try:
        val = yahoo_scraper.set_force_us_eastern(bool(enable))
        return JSONResponse(content={"ok": True, "force_us_eastern": val})
    except Exception:
        LOG.exception("Failed to set force_eastern flag")
        return JSONResponse(status_code=500, content={"ok": False})


@app.get('/control/yahoo/fetch')
def control_yahoo_fetch(symbol: str, period: str = '1mo', interval: str = '1d', limit: int = 200):
    """Fetch realtime + history for a single Yahoo symbol.

    Protected by the same token middleware. Returns JSON with keys `realtime` and `history`.
    """
    if not symbol:
        return JSONResponse(status_code=400, content={"ok": False, "reason": "missing symbol"})
    try:
        realtime = yahoo_scraper.fetch_realtime(symbol)
        history = yahoo_scraper.fetch_history(symbol, period=period, interval=interval)
        # limit history entries and convert timestamps to ISO
        hist_out = []
        for rec in history[-limit:]:
            r = rec.copy()
            ts = r.get('timestamp')
            if hasattr(ts, 'isoformat'):
                r['timestamp'] = ts.isoformat()
            else:
                r['timestamp'] = str(ts)
            hist_out.append(r)
        return JSONResponse(content={"ok": True, "symbol": symbol, "realtime": realtime, "history": hist_out})
    except Exception:
        LOG.exception("Error fetching yahoo data for %s", symbol)
        return JSONResponse(status_code=500, content={"ok": False, "reason": "fetch failed"})


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



@app.get('/control/vn/cache')
def control_vn_cache():
    """Return a JSON-serializable copy of the scraper's in-memory cache for debugging."""
    inst = getattr(vn_scraper, "SCRAPER_INSTANCE", None)
    if inst is None:
        return JSONResponse(content={"ok": False, "reason": "scraper not running", "cache": {}})

    def _make_safe(obj):
        # recursively make simple JSON-serializable representation
        if isinstance(obj, dict):
            return {k: _make_safe(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_make_safe(v) for v in obj]
        try:
            # test JSON-serializable
            import json

            json.dumps(obj)
            return obj
        except Exception:
            return str(obj)

    safe_cache = {k: _make_safe(v) for k, v in inst.cache.items()} if getattr(inst, 'cache', None) else {}
    return JSONResponse(content={"ok": True, "cache": safe_cache})


class TrackPayload(BaseModel):
    symbol: str
    name: str = None


@app.get('/control/yahoo/track')
def control_yahoo_track_list():
    try:
        session = SessionLocal()
        rows = session.query(IndexTracking).order_by(IndexTracking.created_at.desc()).all()
        out = [{"symbol": r.symbol, "name": r.name} for r in rows]
        return JSONResponse(content={"ok": True, "tracked": out})
    except Exception:
        LOG.exception("Failed to list tracked symbols")
        return JSONResponse(status_code=500, content={"ok": False})
    finally:
        try:
            session.close()
        except Exception:
            pass


@app.post('/control/yahoo/track')
def control_yahoo_track_add(payload: TrackPayload):
    sym = payload.symbol.strip()
    if not sym:
        return JSONResponse(status_code=400, content={"ok": False, "reason": "missing symbol"})
    try:
        session = SessionLocal()
        exists = session.query(IndexTracking).filter_by(symbol=sym).one_or_none()
        if exists:
            return JSONResponse(content={"ok": True, "message": "already tracked"})
        row = IndexTracking(symbol=sym, name=payload.name)
        session.add(row)
        session.commit()
        return JSONResponse(content={"ok": True})
    except Exception:
        LOG.exception("Failed to add tracked symbol %s", sym)
        session.rollback()
        return JSONResponse(status_code=500, content={"ok": False})
    finally:
        try:
            session.close()
        except Exception:
            pass


@app.delete('/control/yahoo/track')
def control_yahoo_track_delete(symbol: str):
    if not symbol:
        return JSONResponse(status_code=400, content={"ok": False, "reason": "missing symbol"})
    try:
        session = SessionLocal()
        row = session.query(IndexTracking).filter_by(symbol=symbol).one_or_none()
        if not row:
            return JSONResponse(content={"ok": True, "message": "not found"})
        session.delete(row)
        session.commit()
        return JSONResponse(content={"ok": True})
    except Exception:
        LOG.exception("Failed to delete tracked symbol %s", symbol)
        session.rollback()
        return JSONResponse(status_code=500, content={"ok": False})
    finally:
        try:
            session.close()
        except Exception:
            pass



@app.get('/control/vn/inspect')
def control_vn_inspect(headful: bool = False, wait: int = 3):
    """Open a temporary Playwright page and return inspection data.

    - `headful`: when true, enables images/resource loading.
    - `wait`: additional seconds to wait after load for websocket activity.
    """
    bm = BrowserManager(disable_images=not headful)
    try:
        bm.start()
        page = bm.new_page()
        webs = []

        def _on_ws(ws):
            try:
                webs.append(getattr(ws, 'url', str(ws)))
            except Exception:
                webs.append(str(ws))

        page.on("websocket", _on_ws)
        page.goto("https://iboard.ssi.com.vn/", timeout=60000)
        try:
            page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            # ignore load wait errors
            pass
        # allow some extra time for websockets to open
        time.sleep(max(0, int(wait)))

        title = page.title()
        url = page.url
        html_snippet = page.content()[:2000]
        try:
            screenshot_bytes = page.screenshot()
            b64 = base64.b64encode(screenshot_bytes).decode('ascii')
            tf = tempfile.NamedTemporaryFile(prefix="mc-inspect-", suffix=".png", delete=False)
            tf.write(screenshot_bytes)
            tf.flush()
            tf.close()
            screenshot_file = tf.name
        except Exception:
            screenshot_file = None
            b64 = None

        return JSONResponse(content={
            "ok": True,
            "title": title,
            "url": url,
            "websockets": webs,
            "html_snippet": html_snippet,
            "screenshot_file": screenshot_file,
            "screenshot_base64": b64,
        })
    except Exception:
        LOG.exception("Inspect failed")
        return JSONResponse(status_code=500, content={"ok": False, "reason": "inspect failed"})
    finally:
        try:
            bm.stop()
        except Exception:
            pass



@app.get('/dashboard')
def dashboard():
        html = """
        <!doctype html>
        <html>
        <head>
            <meta charset="utf-8" />
            <title>Market Collector Dashboard</title>
            <style>body{font-family:system-ui,Segoe UI,Roboto,Helvetica,Arial;margin:16px}button{margin:4px}</style>
        </head>
        <body>
            <h2>Market Collector — Dashboard</h2>
            <div>
                <button onclick="fetch('/control/vn/snapshot', {method:'POST'}).then(r=>r.json()).then(j=>alert(JSON.stringify(j)))">Snapshot (now)</button>
                <button onclick="fetch('/control/vn/snapshot?force=true', {method:'POST'}).then(r=>r.json()).then(j=>alert(JSON.stringify(j)))">Snapshot (force)</button>
            </div>
            <div style="margin-top:12px">
                <label>Set snapshot interval (seconds): </label>
                <input id="interval" type="number" value="15" style="width:80px"/>
                <button onclick="setInterval()">Set</button>
            </div>
            <div style="margin-top:12px">
                <label>Yahoo price interval (seconds): </label>
                <input id="yahoo_interval" type="number" value="15" style="width:80px"/>
                <button onclick="setYahooInterval()">Set</button>
                <button onclick="runYahooNow()">Run Now</button>
            </div>
            <div style="margin-top:12px">
                <h3>Logs</h3>
                <label>Lines: </label><input id="lines" type="number" value="200" style="width:80px"/>
                <button onclick="loadLogs()">Refresh</button>
                <pre id="logs" style="height:400px;overflow:auto;border:1px solid #ddd;padding:8px;background:#f9f9f9"></pre>
            </div>
            <div style="margin-top:12px">
                <h3>Tracked Symbols</h3>
                <input id="track_symbol" placeholder="e.g. ^GSPC or AAPL" style="width:180px" />
                <input id="track_name" placeholder="optional name" style="width:200px" />
                <button onclick="addTrack()">Add</button>
                <button onclick="loadTracked()">Refresh</button>
                <ul id="tracked_list"></ul>
            </div>
            <script>
                function setInterval(){
                    const seconds = parseInt(document.getElementById('interval').value||'15',10);
                    fetch('/control/vn/interval', {method:'POST', headers:{'content-type':'application/json'}, body:JSON.stringify({seconds})}).then(r=>r.json()).then(j=>alert(JSON.stringify(j)));
                }
                function setYahooInterval(){
                    const seconds = parseInt(document.getElementById('yahoo_interval').value||'15',10);
                    fetch('/control/yahoo/interval_seconds', {method:'POST', headers:{'content-type':'application/json','x-api-token': window._api_token||''}, body:JSON.stringify({seconds})}).then(r=>r.json()).then(j=>alert(JSON.stringify(j)));
                }

                function runYahooNow(){
                    fetch('/control/yahoo/price_run', {method:'POST', headers:{'x-api-token': window._api_token||''}}).then(r=>r.json()).then(j=>alert(JSON.stringify(j)));
                }
                function loadLogs(){
                    const lines = parseInt(document.getElementById('lines').value||'200',10);
                    fetch('/dashboard/logs?lines='+lines).then(r=>r.text()).then(t=>{document.getElementById('logs').textContent = t});
                }
                loadLogs();
                setInterval(loadLogs, 15000);
                function loadTracked(){
                    fetch('/control/yahoo/track', {headers: { 'x-api-token': window._api_token || ''}})
                        .then(r=>r.json()).then(j=>{
                            const ul = document.getElementById('tracked_list'); ul.innerHTML='';
                            if(j && j.tracked){
                                j.tracked.forEach(s=>{
                                    const li = document.createElement('li');
                                    li.textContent = s.symbol + (s.name? (' - '+s.name):'');
                                    const btn = document.createElement('button'); btn.textContent='Delete'; btn.style.marginLeft='8px';
                                    btn.onclick = ()=>{ if(confirm('Delete '+s.symbol+'?')) fetch('/control/yahoo/track?symbol='+encodeURIComponent(s.symbol), {method:'DELETE', headers:{'x-api-token': window._api_token||''}}).then(()=>loadTracked()) };
                                    li.appendChild(btn);
                                    ul.appendChild(li);
                                })
                            }
                        })
                }
                function addTrack(){
                    const symbol = document.getElementById('track_symbol').value.trim();
                    const name = document.getElementById('track_name').value.trim();
                    if(!symbol) { alert('symbol required'); return }
                    fetch('/control/yahoo/track', {method:'POST', headers:{'content-type':'application/json','x-api-token': window._api_token||''}, body:JSON.stringify({symbol,name})}).then(()=>{document.getElementById('track_symbol').value='';document.getElementById('track_name').value='';loadTracked()})
                }
                loadTracked();
            </script>
        </body>
        </html>
        """
        return HTMLResponse(content=html)


def _tail_file(path: str, lines: int = 200) -> str:
        if not path or not os.path.exists(path):
                return ""
        # simple tail implementation
        avg_line_len = 200
        to_read = lines * avg_line_len
        try:
                with open(path, 'rb') as f:
                        try:
                                f.seek(-to_read, os.SEEK_END)
                        except OSError:
                                f.seek(0, os.SEEK_SET)
                        data = f.read().decode(errors='replace')
                parts = data.splitlines()
                return '\n'.join(parts[-lines:])
        except Exception:
                return ''


@app.get('/dashboard/logs')
def dashboard_logs(lines: int = 200):
    # Try to read recent logs from DB first
    try:
        from .db import SessionLocal
        from .models import LogEntry

        session = SessionLocal()
        try:
            q = session.query(LogEntry).order_by(LogEntry.created_at.desc()).limit(lines).all()
            # format entries newest-last
            q = list(reversed(q))
            out_lines: List[str] = []
            for e in q:
                ts = e.created_at.isoformat() if e.created_at is not None else ""
                out_lines.append(f"{ts} {e.level} {e.logger} - {e.message}")
            if out_lines:
                return PlainTextResponse(content="\n".join(out_lines))
        finally:
            try:
                session.close()
            except Exception:
                pass
    except Exception:
        # DB unavailable or models not ready, fall back to file
        pass

    txt = _tail_file(LOG_FILE, lines=lines)
    return PlainTextResponse(content=txt)
