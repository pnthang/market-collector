from datetime import datetime, time as dtime
import pytz


def is_market_open_at(now: datetime, tz_str: str = "Asia/Ho_Chi_Minh") -> bool:
    tz = pytz.timezone(tz_str)
    if now.tzinfo is None:
        now = tz.localize(now)
    else:
        now = now.astimezone(tz)
    if now.weekday() >= 5:
        return False
    morning_start = dtime(9, 0)
    morning_end = dtime(11, 30)
    afternoon_start = dtime(13, 0)
    afternoon_end = dtime(15, 0)
    cur = now.time()
    return (morning_start <= cur <= morning_end) or (afternoon_start <= cur <= afternoon_end)
