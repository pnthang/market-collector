from flask import Flask, jsonify
from sqlalchemy import text
import logging

from .db import engine

LOG = logging.getLogger("health")

app = Flask(__name__)


def check_db() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        LOG.exception("DB health check failed")
        return False


@app.route("/health")
def health():
    db_ok = check_db()
    status = "ok" if db_ok else "fail"
    code = 200 if db_ok else 500
    return jsonify({"status": status, "db": db_ok}), code


@app.route("/ready")
def ready():
    # same as /health for now; can include scheduler/playwright checks
    return health()


def run(host="0.0.0.0", port=8080):
    app.run(host=host, port=port)
