"""Fetch index group data (e.g., VN30) from iboard-query.ssi.com.vn and store constituents.

Usage:
    python -m app.fetch_group VN30

This script calls the public endpoint at:
    https://iboard-query.ssi.com.vn/stock/group/{GROUP}

It parses the JSON and writes to `index_metadata` and `index_constituents`.
"""
import sys
import logging
from typing import Any, Dict

import requests
from sqlalchemy.exc import IntegrityError

from .db import init_db, SessionLocal
from .models import IndexMetadata, IndexConstituent

LOG = logging.getLogger("fetch_group")


def fetch_group(group: str) -> Dict[str, Any]:
    url = f"https://iboard-query.ssi.com.vn/stock/group/{group}"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    return resp.json()


def save_group(group: str, payload: Dict[str, Any]):
    session = SessionLocal()
    # payload structure may vary; attempt to extract common fields
    meta = payload.get("group") or payload.get("meta") or {}
    name = meta.get("name") or group
    description = meta.get("description") or None

    im = session.query(IndexMetadata).filter_by(code=group).one_or_none()
    if not im:
        im = IndexMetadata(code=group, name=name, description=description, source="iboard-query")
        session.add(im)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()

    # constituents often under payload['data'] or payload['items']
    items = payload.get("data") or payload.get("items") or payload.get("constituents") or []
    if isinstance(items, dict):
        # maybe 'items' keyed
        items = items.get("items") or []

    for it in items:
        symbol = it.get("symbol") or it.get("code") or it.get("s")
        name = it.get("name") or it.get("companyName")
        price = it.get("lastPrice") or it.get("price")
        weight = it.get("weight")
        shares = it.get("shares")
        market_cap = it.get("marketCap") or it.get("mktCap")

        if not symbol:
            continue

        cons = IndexConstituent(
            index_code=group,
            symbol=symbol,
            name=name,
            weight=float(weight) if weight is not None else None,
            shares=float(shares) if shares is not None else None,
            market_cap=float(market_cap) if market_cap is not None else None,
            price=float(price) if price is not None else None,
            change=None,
            change_percent=None,
        )
        session.add(cons)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
    except Exception:
        LOG.exception("Error saving constituents")
    finally:
        session.close()


def main(argv):
    if len(argv) < 1:
        print("Usage: python -m app.fetch_group GROUP")
        return 1
    group = argv[0]
    init_db()
    payload = fetch_group(group)
    save_group(group, payload)
    print("Saved group", group)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sys.exit(main(sys.argv[1:]))
