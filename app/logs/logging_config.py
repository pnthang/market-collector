import logging
import sys

def configure_logging(level: str = "INFO"):
    levelno = getattr(logging, level.upper(), logging.INFO)
    fmt = "%(asctime)s %(levelname)s %(name)s - %(message)s"
    formatter = logging.Formatter(fmt)
    # console handler
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.setLevel(levelno)
    # avoid duplicate handlers
    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        root.addHandler(handler)
    # add optional file handler (append)
    try:
        from ..config import LOG_FILE
        if LOG_FILE:
            fh = logging.FileHandler(LOG_FILE)
            fh.setFormatter(formatter)
            # avoid duplicate file handlers
            if not any(isinstance(h, logging.FileHandler) for h in root.handlers):
                root.addHandler(fh)
    except Exception:
        pass
    # reduce noisy third-party libs
    logging.getLogger("playwright").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    # ensure DB tables exist and add DB log handler
    try:
        from ..db import init_db, SessionLocal
        from ..db.models import LogEntry

        init_db()

        class DBLogHandler(logging.Handler):
            def __init__(self):
                super().__init__()
                self.setFormatter(formatter)

            def emit(self, record: logging.LogRecord) -> None:
                try:
                    session = SessionLocal()
                    # format message using handler's formatter
                    msg = self.format(record)
                    entry = LogEntry(level=record.levelname, logger=record.name, message=msg)
                    session.add(entry)
                    session.commit()
                except Exception:
                    try:
                        session.rollback()
                    except Exception:
                        pass
                finally:
                    try:
                        session.close()
                    except Exception:
                        pass

        # avoid adding duplicate DB handlers
        if not any(isinstance(h, logging.Handler) and h.__class__.__name__ == 'DBLogHandler' for h in root.handlers):
            root.addHandler(DBLogHandler())
    except Exception:
        # if DB logging setup fails, continue silently (console logging still works)
        pass
