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
        from .config import LOG_FILE
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