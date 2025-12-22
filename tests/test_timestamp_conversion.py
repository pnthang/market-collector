from datetime import datetime
import pytz

from app.utils import is_market_open_at


def test_timestamp_tz_naive():
    # naive datetime should be localized to the provided timezone
    dt = datetime(2025, 12, 22, 14, 0)
    assert is_market_open_at(dt, "Asia/Ho_Chi_Minh")
