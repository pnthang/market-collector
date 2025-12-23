"""Compatibility wrapper re-exporting the health module from app.system."""
from .system.health import app, LOG  # noqa: F401



# Middleware to enforce simple token auth on all endpoints except /health
class TokenAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, token: str):
        super().__init__(app)
        """Compatibility wrapper re-exporting the health module from app.system."""
        from .system.health import app, LOG  # noqa: F401,F403
        if since:
            """Compatibility wrapper re-exporting the health module from app.system."""
            from .system.health import app, LOG  # noqa: F401,F403
            except Exception:
