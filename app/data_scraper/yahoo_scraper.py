"""Yahoo Finance scraper: discover indices, fetch quotes, news, and analysis.

This module uses the public Yahoo JSON quote API for current quotes and
Playwright to scrape the news and analysis pages when necessary.
"""
from typing import List, Dict, Optional
import logging
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
try:
    import yfinance as yf
    HAVE_YF = True
except Exception:
    HAVE_YF = False
    yf = None

try:
    import pandas as pd
except Exception:
    pd = None

from .playwright_manager import BrowserManager
from ..db import SessionLocal, init_db
from ..db.models import IndexMetadata, IndexPrice, IndexNews, IndexAnalysis, IndexTracking
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.events import EVENT_JOB_ERROR

from ..config import MARKET_TZ
from ..utils import is_market_open_at

_YAHOO_SCHEDULER = None
_YAHOO_PRICE_INTERVAL = 15
# When True, force market hours checks to use US/Eastern regardless of MARKET_TZ
FORCE_US_EASTERN = False

def set_force_us_eastern(enabled: bool):
    global FORCE_US_EASTERN
    FORCE_US_EASTERN = bool(enabled)
    LOG.info("Force US/Eastern market hours: %s", FORCE_US_EASTERN)
    return FORCE_US_EASTERN

LOG = logging.getLogger("yahoo_scraper")


YAHOO_WORLD_INDICES = "https://finance.yahoo.com/world-indices/"
YAHOO_QUOTE_API = "https://query1.finance.yahoo.com/v7/finance/quote"


def discover_indices(limit: Optional[int] = None) -> List[str]:
    """Scrape the world indices page and return a list of symbols (e.g., ^GSPC, ^DJI)."""
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=0.5, status_forcelist=(429, 500, 502, 503, 504))
    session.mount("https://", HTTPAdapter(max_retries=retries))
    resp = session.get(YAHOO_WORLD_INDICES, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    symbols = []
    for a in soup.select("a[href*='/quote/']"):
        href = a.get('href')
        if not href:
            continue
        parts = href.split('/quote/')
        if len(parts) < 2:
            continue
        sym = parts[1].split('?')[0].strip('/')
        if sym and sym not in symbols:
            symbols.append(sym)
            if limit and len(symbols) >= limit:
                break
    LOG.info("Discovered %d index symbols", len(symbols))
    return symbols


def fetch_quotes(symbols: List[str]) -> List[Dict]:
    """Fetch current quote data via Yahoo public API for multiple symbols."""
    if not symbols:
        return []

    # Prefer yfinance when available (more reliable for some tickers)
    if HAVE_YF and pd is not None:
        try:
            # yfinance.download returns a DataFrame; for multiple tickers columns are a MultiIndex
            df = yf.download(tickers=symbols, period='1d', interval='1m', group_by='ticker', threads=True, progress=False, show_errors=False)
            results = []
            # multiple tickers -> MultiIndex columns
            if isinstance(df.columns, pd.MultiIndex):
                for sym in symbols:
                    try:
                        if sym not in df.columns.levels[0]:
                            continue
                        sym_df = df[sym].dropna()
                        if sym_df.empty:
                            continue
                        last = sym_df.iloc[-1]
                        price = last.get('Close')
                        ts = sym_df.index[-1]
                        dt = ts.to_pydatetime() if hasattr(ts, 'to_pydatetime') else datetime.utcnow()
                        results.append({
                            'symbol': sym,
                            'price': float(price) if price is not None else None,
                            'change': None,
                            'percent': None,
                            'timestamp': dt,
                        })
                    except Exception:
                        LOG.exception("Error parsing yfinance data for %s", sym)
                        continue
            else:
                # single ticker
                if not df.empty:
                    last = df.iloc[-1]
                    price = last.get('Close')
                    ts = df.index[-1]
                    dt = ts.to_pydatetime() if hasattr(ts, 'to_pydatetime') else datetime.utcnow()
                    results.append({
                        'symbol': symbols[0],
                        'price': float(price) if price is not None else None,
                        'change': None,
                        'percent': None,
                        'timestamp': dt,
                    })
            if results:
                LOG.info("Fetched %d quotes via yfinance", len(results))
                return results
        except Exception:
            LOG.exception("yfinance fetch failed, falling back to API")

    # Fallback to HTTP quote API
    params = {"symbols": ",".join(symbols)}
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=0.3, status_forcelist=(429, 500, 502, 503, 504))
    session.mount("https://", HTTPAdapter(max_retries=retries))
    LOG.info("Fetching %d symbols from Yahoo API", len(symbols))
    resp = session.get(YAHOO_QUOTE_API, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    results = []
    for r in data.get('quoteResponse', {}).get('result', []):
        sym = r.get('symbol')
        price = r.get('regularMarketPrice')
        change = r.get('regularMarketChange')
        pct = r.get('regularMarketChangePercent')
        ts = r.get('regularMarketTime')
        dt = datetime.utcfromtimestamp(ts) if ts else datetime.utcnow()
        results.append({
            'symbol': sym,
            'price': float(price) if price is not None else None,
            'change': float(change) if change is not None else None,
            'percent': float(pct) if pct is not None else None,
            'timestamp': dt,
        })
    return results


def scrape_news_and_analysis(symbol: str, timeout: int = 15) -> Dict[str, List[Dict]]:
    """Use Playwright to scrape simple lists of news and analysis items for a symbol.

    Returns dict with keys 'news' and 'analysis', each a list of items.
    """
    manager = BrowserManager()
    manager.start()
    page = manager.new_page()
    out = {"news": [], "analysis": []}

    try:
        # News
        news_url = f"https://finance.yahoo.com/quote/{symbol}/news"
        page.goto(news_url, timeout=60_000)
        page.wait_for_timeout(1000)
        # articles: headlines often in 'h3' anchors
        items = page.locator("article h3 a").all()
        for it in items[:10]:
            try:
                title = it.inner_text()
                href = it.get_attribute('href')
                url = href if href.startswith('http') else f"https://finance.yahoo.com{href}"
                out['news'].append({'headline': title, 'url': url})
            except Exception:
                continue

        # Analysis
        analysis_url = f"https://finance.yahoo.com/quote/{symbol}/analysis"
        page.goto(analysis_url, timeout=60_000)
        page.wait_for_timeout(1000)
        # try to find analysis headlines (similar pattern)
        items = page.locator("h3 a").all()
        for it in items[:10]:
            try:
                title = it.inner_text()
                href = it.get_attribute('href')
                url = href if href.startswith('http') else f"https://finance.yahoo.com{href}"
                out['analysis'].append({'title': title, 'url': url})
            except Exception:
                continue
    finally:
        manager.stop()
    return out


def save_quotes(quotes: List[Dict]):
    if not quotes:
        return
    LOG.info("Saving %d quotes to DB", len(quotes))
    session = SessionLocal()
    now = datetime.utcnow()
    objs = []
    for q in quotes:
        symbol = q['symbol']
        prefixed = f"US:{symbol}"
        # upsert metadata simple using prefixed code
        if session.query(IndexMetadata).filter_by(code=prefixed).one_or_none() is None:
            session.add(IndexMetadata(code=prefixed, name=symbol, source='yahoo'))
            session.commit()
        objs.append({
            'index_code': prefixed,
            'source': 'yahoo',
            'price': q['price'],
            'change': q['change'],
            'change_percent': q['percent'],
            'timestamp': q['timestamp'],
        })
    try:
        # dedupe before insert
        codes = list({o['index_code'] for o in objs})
        timestamps = list({o['timestamp'] for o in objs})
        existing = set()
        if codes and timestamps:
            qres = session.query(IndexPrice.index_code, IndexPrice.timestamp).filter(IndexPrice.index_code.in_(codes), IndexPrice.timestamp.in_(timestamps)).all()
            existing = {(c, t) for c, t in qres}
        new_objs = [IndexPrice(**o) for o in objs if (o['index_code'], o['timestamp']) not in existing]
        if not new_objs:
            LOG.info("No new quote rows after dedupe")
            return
        session.bulk_save_objects(new_objs)
        session.commit()
        LOG.info("Inserted %d quote rows", len(new_objs))
    except Exception:
        session.rollback()
        for o in objs:
            try:
                ip = IndexPrice(index_code=o['index_code'], source=o['source'], price=o['price'], change=o['change'], change_percent=o['change_percent'], timestamp=o['timestamp'])
                session.add(ip)
                session.commit()
            except Exception:
                session.rollback()
    finally:
        session.close()


def to_iso(val) -> Optional[str]:
    if val is None:
        return None
    try:
        if isinstance(val, (int, float)):
            return datetime.utcfromtimestamp(int(val)).isoformat()
        if isinstance(val, datetime):
            return val.isoformat()
        # last-resort string
        return str(val)
    except Exception:
        return None


def fetch_realtime(symbol: str) -> Dict:
    """Return a detailed realtime dict for `symbol` using yfinance when available.

    Fields mirror the structure requested in the issue: price, change_percent, name,
    close (previous close), after_hours, after_hours_time, 52-week high/low, volume, etc.
    """
    t = None
    info = {}
    fi = None
    price = None
    prev_close = None
    change_percent = None

    if HAVE_YF:
        try:
            t = yf.Ticker(symbol)
            info = t.info or {}
            fi = getattr(t, 'fast_info', None) or {}
        except Exception:
            LOG.exception("yfinance info error for %s", symbol)

    # price candidates
    price = info.get('regularMarketPrice') or (fi.get('last_price') if fi else None)
    prev_close = info.get('previousClose') or (fi.get('previous_close') if fi else None)
    change_percent = info.get('regularMarketChangePercent') or None

    if price is None and t is not None:
        try:
            h = t.history(period='1d', interval='1m')
            if not h.empty:
                price = float(h['Close'].iloc[-1])
        except Exception:
            LOG.debug("yfinance history fallback failed for %s", symbol)

    result = {
        "symbol": symbol,
        "price": price,
        "change_percent": change_percent,
        "name": info.get("shortName") or info.get("longName"),
        "close": prev_close,
        "after_hours": info.get("postMarketPrice") or info.get("postMarketChange") or None,
        "after_hours_time": to_iso(info.get("postMarketTime") or info.get("postMarketDateTime")),
        "high52": info.get("fiftyTwoWeekHigh") or None,
        "low52": info.get("fiftyTwoWeekLow") or None,
        "volume": info.get("volume") or (fi.get('volume') if fi else info.get('volume')),
        "avgVolume": info.get("averageVolume") or None,
        "marketCap": info.get("marketCap") or None,
        "open": info.get("open") or (fi.get('open') if fi else info.get('open')),
        "bid": info.get("bid") or (fi.get('bid') if fi else info.get('bid')),
        "ask": info.get("ask") or (fi.get('ask') if fi else info.get('ask')),
        "dayHigh": info.get("dayHigh") or None,
        "dayLow": info.get("dayLow") or None,
        "peRatio": info.get("trailingPE") or info.get("forwardPE") or None,
        "eps": info.get("trailingEps") or info.get("epsTrailingTwelveMonths") or None,
        "exchange": info.get("exchange") or info.get("exchangeName") or None,
        "currency": info.get("currency") or None,
    }

    return result


def fetch_history(symbol: str, period: str = '1mo', interval: str = '1d') -> List[Dict]:
    """Fetch historical OHLCV records for `symbol` using yfinance if available.

    Returns list of records with keys: timestamp, open, high, low, close, volume
    """
    records: List[Dict] = []
    if not HAVE_YF:
        LOG.warning("yfinance not available; cannot fetch history for %s", symbol)
        return records
    try:
        t = yf.Ticker(symbol)
        df = t.history(period=period, interval=interval)
        if df is None or df.empty:
            return records
        for idx, row in df.iterrows():
            try:
                ts = idx.to_pydatetime() if hasattr(idx, 'to_pydatetime') else datetime.utcfromtimestamp(int(idx))
                records.append({
                    "timestamp": ts,
                    "open": float(row['Open']),
                    "high": float(row['High']),
                    "low": float(row['Low']),
                    "close": float(row['Close']),
                    "volume": int(row['Volume'])
                })
            except Exception:
                continue
    except Exception:
        LOG.exception("Failed to fetch history for %s", symbol)
    return records


def _yahoo_job(limit: Optional[int] = None):
    try:
        run_one_cycle(limit=limit)
    except Exception:
        LOG.exception("Yahoo scheduled job failed")


def _yahoo_price_job():
    """Fetch prices for tracked symbols (or discovered ones) during market hours."""
    now = datetime.utcnow()
    tz_to_use = 'US/Eastern' if FORCE_US_EASTERN else MARKET_TZ
    if not is_market_open_at(now, tz_to_use):
        LOG.info("Yahoo price job: market closed (%s) — skipping", tz_to_use)
        return

    session = SessionLocal()
    try:
        tracked = session.query(IndexTracking).order_by(IndexTracking.created_at.desc()).all()
        if tracked:
            symbols = [t.symbol for t in tracked]
        else:
            symbols = discover_indices()
    finally:
        try:
            session.close()
        except Exception:
            pass

    if not symbols:
        LOG.info("Yahoo price job: no symbols to fetch")
        return

    try:
        quotes = fetch_quotes(symbols)
        save_quotes(quotes)
        LOG.info("Yahoo price job: fetched %d symbols", len(quotes))
    except Exception:
        LOG.exception("Yahoo price job failed")
