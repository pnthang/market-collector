from datetime import datetime
import pytz

from app.utils import is_market_open_at


def test_market_open_morning():
    tz = pytz.timezone("Asia/Ho_Chi_Minh")
    dt = tz.localize(datetime(2025, 12, 22, 9, 30))
    assert is_market_open_at(dt, "Asia/Ho_Chi_Minh")


def test_market_closed_weekend():
    tz = pytz.timezone("Asia/Ho_Chi_Minh")
    dt = tz.localize(datetime(2025, 12, 21, 10, 0))  # Sunday
    assert not is_market_open_at(dt, "Asia/Ho_Chi_Minh")
