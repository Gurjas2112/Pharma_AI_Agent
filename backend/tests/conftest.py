import os

import pytest

# tests must never hit paid / remote services unless explicitly marked
os.environ.setdefault("USE_LIVE_CTGOV", "false")
os.environ.setdefault("USE_LIVE_WEB", "false")
os.environ.setdefault("MOCK_API_URL", "http://127.0.0.1:9")  # force in-process mock fallback


def _localstack_up() -> bool:
    import httpx

    try:
        return httpx.get("http://localhost:4566/_localstack/health", timeout=2).status_code == 200
    except Exception:
        return False


requires_localstack = pytest.mark.skipif(not _localstack_up(), reason="LocalStack not running")
