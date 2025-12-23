#!/usr/bin/env python3
"""Simple migration helper: find old `app.*` wrapper imports and suggest replacements.

Run from repo root: `python3 scripts/migrate_imports.py`.
It prints suggested `sed` commands; review before applying.
"""
import re
import sys
from pathlib import Path

REPLACEMENTS = {
    # old -> new
    r"from\s+app\.vn_scraper\b": "from app.data_scraper.vn_scraper",
    r"import\s+app\.vn_scraper\b": "import app.data_scraper.vn_scraper",
    r"from\s+app\.yahoo_scraper\b": "from app.data_scraper.yahoo_scraper",
    r"import\s+app\.yahoo_scraper\b": "import app.data_scraper.yahoo_scraper",
    r"from\s+app\.playwright_manager\b": "from app.data_scraper.playwright_manager",
    r"import\s+app\.playwright_manager\b": "import app.data_scraper.playwright_manager",
    r"from\s+app\.logging_config\b": "from app.logs.logging_config",
    r"import\s+app\.logging_config\b": "import app.logs.logging_config",
    r"from\s+app\.models\b": "from app.db.models",
    r"import\s+app\.models\b": "import app.db.models",
    r"from\s+app\.celery_app\b": "from app.queue.celery_app",
    r"import\s+app\.celery_app\b": "import app.queue.celery_app",
    r"from\s+app\.health\b": "from app.system.health",
    r"import\s+app\.health\b": "import app.system.health",
    r"from\s+app\.db\b": "from app.db",
}

def scan(root: Path):
    py_files = list(root.rglob('*.py'))
    suggestions = []
    for p in py_files:
        try:
            text = p.read_text()
        except Exception:
            continue
        for old_pat, new_text in REPLACEMENTS.items():
            if re.search(old_pat, text):
                suggestions.append((p, old_pat, new_text))
    return suggestions

def main():
    root = Path('.').resolve()
    print(f"Scanning {root} for old imports...")
    found = scan(root)
    if not found:
        print("No matches found.")
        return 0
    by_file = {}
    for p, old_pat, new_text in found:
        by_file.setdefault(p, []).append((old_pat, new_text))

    for p, changes in sorted(by_file.items()):
        print(f"\nFile: {p}")
        for old_pat, new_text in changes:
            print(f"  - pattern: {old_pat}  -> replace with: {new_text}")
        # Print a conservative sed suggestion for manual review
        for old_pat, new_text in changes:
            # sed expression: replace the specific module part
            mod_old = re.sub(r"from\\s+|import\\s+", "", old_pat).strip('\\b')
            # fallback generic suggestion
            print(f"    suggested (review): sed -E -i 's/{old_pat}/{new_text}/g' {p}")

    return 0

if __name__ == '__main__':
    sys.exit(main())
