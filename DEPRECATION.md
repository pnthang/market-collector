DEPRECATION: compatibility wrappers removed
=========================================

Summary
-------
Thin compatibility wrapper modules under `app/` were removed to prefer the
new, clearer package layout. This change may break code that imports the old
top-level modules (for example `from app.vn_scraper import ...`).

What was removed
----------------
- `app/vn_scraper.py`
- `app/yahoo_scraper.py`
- `app/ml.py` (thin wrapper)
- `app/playwright_manager.py`
- `app/logging_config.py`
- `app/db.py` (thin wrapper)
- `app/models.py` (thin wrapper)
- `app/celery_app.py` (thin wrapper)
- `app/health.py` (thin wrapper)

Recommended replacements
------------------------
Update imports to the new package locations. Examples:

- `from app.vn_scraper import X`  ->  `from app.data_scraper.vn_scraper import X`
- `from app.yahoo_scraper import X` ->  `from app.data_scraper.yahoo_scraper import X`
- `from app.ml import X`            ->  `from app.ml import X` (use `app.ml` package or `app.ml.core`)
- `from app.playwright_manager import BrowserManager` -> `from app.data_scraper.playwright_manager import BrowserManager`
- `from app.logging_config import configure_logging` -> `from app.logs.logging_config import configure_logging`
- `from app.db import SessionLocal, Base` -> `from app.db import SessionLocal, Base` (use `app.db` package)
- `from app.models import IndexPrice` -> `from app.db.models import IndexPrice`
- `from app.celery_app import celery` -> `from app.queue.celery_app import celery`
- `from app.health import app` -> `from app.system.health import app`

Migration help
--------------
Use `scripts/migrate_imports.py` to scan your codebase and get suggested
replacement commands. It's conservative and prints suggested `sed` commands
you can review and apply manually.

Support
-------
If you need assistance migrating a large codebase, I can:

- run the migration script and produce a patch/PR for the replacements,
- or keep the thin wrappers in place for one more release cycle.

Contact: repository maintainer
