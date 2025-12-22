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

from .playwright_manager import BrowserManager
from .db import SessionLocal, init_db
from .models import IndexMetadata, IndexPrice, IndexNews, IndexAnalysis
from datetime import datetime

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
    params = {"symbols": ",".join(symbols)}
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=0.3, status_forcelist=(429, 500, 502, 503, 504))
    session.mount("https://", HTTPAdapter(max_retries=retries))
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
        objs.append(IndexPrice(index_code=prefixed, source='yahoo', price=q['price'], change=q['change'], change_percent=q['percent'], timestamp=q['timestamp']))
    try:
        session.bulk_save_objects(objs)
        session.commit()
    except Exception:
        session.rollback()
        for o in objs:
            try:
                session.add(o)
                session.commit()
            except Exception:
                session.rollback()
    finally:
        session.close()


def save_news_analysis(symbol: str, payload: Dict[str, List[Dict]]):
    session = SessionLocal()
    try:
        prefixed = f"US:{symbol}"
        for n in payload.get('news', []):
            if not n.get('url'):
                continue
            if session.query(IndexNews).filter_by(url=n['url']).one_or_none():
                continue
            session.add(IndexNews(index_code=prefixed, headline=n.get('headline'), url=n.get('url')))
        for a in payload.get('analysis', []):
            if not a.get('url'):
                continue
            if session.query(IndexAnalysis).filter_by(url=a['url']).one_or_none():
                continue
            session.add(IndexAnalysis(index_code=prefixed, title=a.get('title'), url=a.get('url')))
        session.commit()
    except Exception:
        session.rollback()
        LOG.exception("Error saving news/analysis for %s", symbol)
    finally:
        session.close()


def run_one_cycle(limit: Optional[int] = None):
    init_db()
    symbols = discover_indices(limit=limit)
    quotes = fetch_quotes(symbols)
    save_quotes(quotes)
    for s in symbols:
        try:
            payload = scrape_news_and_analysis(s)
            save_news_analysis(s, payload)
            time.sleep(1)
        except Exception:
            LOG.exception("Error scraping %s", s)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    run_one_cycle(limit=10)
