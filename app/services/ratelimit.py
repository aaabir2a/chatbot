"""Per-API-key rate limiting via slowapi."""
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings


def _api_key_identifier(request) -> str:
    """Rate-limit bucket = the API key (fallback to client IP if absent)."""
    key = request.headers.get(settings.api_key_header)
    return key or get_remote_address(request)


limiter = Limiter(key_func=_api_key_identifier, default_limits=[])

# Reusable decorator argument so endpoints share one configurable limit.
RATE_LIMIT = settings.rate_limit
