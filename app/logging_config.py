import logging
import sys

def configure_logging(level: str = "INFO"):
    levelno = getattr(logging, level.upper(), logging.INFO)
    handler = logging.StreamHandler(stream=sys.stdout)
    fmt = "%(asctime)s %(levelname)s %(name)s - %(message)s"
    formatter = logging.Formatter(fmt)
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.setLevel(levelno)
    # avoid duplicate handlers
    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        root.addHandler(handler)
    # reduce noisy third-party libs
    logging.getLogger("playwright").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)