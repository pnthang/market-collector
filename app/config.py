import os
from dotenv import load_dotenv

load_dotenv()

# Compose DATABASE_URL from individual env vars when not provided directly.
_database_url = os.getenv("DATABASE_URL")
if not _database_url:
	db_user = os.getenv("DB_USER", os.getenv("POSTGRES_USER", "postgres"))
	db_pass = os.getenv("DB_PASSWORD", os.getenv("POSTGRES_PASSWORD", "postgres"))
	db_host = os.getenv("DB_HOST", "localhost")
	db_port = os.getenv("DB_PORT", "5432")
	db_name = os.getenv("DB_NAME", os.getenv("POSTGRES_DB", "market"))
	_database_url = f"postgresql+psycopg2://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"

DATABASE_URL = _database_url
MARKET_TZ = os.getenv("MARKET_TZ", "Asia/Ho_Chi_Minh")
SNAPSHOT_INTERVAL = int(os.getenv("SNAPSHOT_INTERVAL", "15"))
DRY_RUN = os.getenv("DRY_RUN", "false").lower() in ("1", "true", "yes")

# Optional DB pool settings
DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "5"))
DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "10"))
DB_POOL_PRE_PING = os.getenv("DB_POOL_PRE_PING", "true").lower() in ("1", "true", "yes")

# API token for protecting control endpoints. If empty, auth is disabled.
API_TOKEN = os.getenv("API_TOKEN", "")
