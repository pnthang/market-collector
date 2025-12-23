This folder contains compatibility packages to help transition to a
more modular project layout.

New packages added:

- `app.db` (re-exports `app/db.py` and `app/models.py`)
- `app.data_scraper` (aggregates scrapers: `vn_scraper`, `yahoo_scraper`, etc.)
- `app.queue` (re-exports Celery app)
- `app.system` (re-exports `health` and `logging_config`)
- `app.logs` (re-exports logging helpers)
- `app.ml` (re-exports ML helpers)

These are thin wrappers that import the existing top-level modules so you can
start depending on a clearer package layout while keeping older import paths
functional. Next steps to finish the reorganization:

1. Gradually move implementations into their target subpackages (copy then
   update imports).
2. Remove legacy top-level modules once all internal imports and external
   consumers reference the new package paths.
3. Add package-level tests for the new modules.
