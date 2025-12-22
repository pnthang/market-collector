import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./market_collector.db")
MARKET_TZ = os.getenv("MARKET_TZ", "Asia/Ho_Chi_Minh")
SNAPSHOT_INTERVAL = int(os.getenv("SNAPSHOT_INTERVAL", "15"))
DRY_RUN = os.getenv("DRY_RUN", "false").lower() in ("1", "true", "yes")
