"""Secret resolution: AWS Secrets Manager first, environment second.

In the prototype ``AWS_ENDPOINT_URL`` points at LocalStack, so the exact same
code path runs against real AWS later by just unsetting the endpoint.
Secrets are fetched at call time and are never placed into prompts or logs.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

from repurpora.settings import get_settings

log = logging.getLogger(__name__)

_CACHE: dict[str, Any] = {"at": 0.0, "data": None}
_TTL = 300


def _load_from_aws() -> dict[str, str]:
    s = get_settings()
    if not s.aws_endpoint_url and not os.getenv("AWS_ACCESS_KEY_ID"):
        return {}
    try:
        import boto3

        client = boto3.client(
            "secretsmanager",
            endpoint_url=s.aws_endpoint_url,
            region_name=s.aws_region,
        )
        raw = client.get_secret_value(SecretId=s.aws_secret_name)["SecretString"]
        return json.loads(raw)
    except Exception as exc:  # emulator down / not bootstrapped -> env fallback
        log.debug("secrets manager unavailable (%s); using env", type(exc).__name__)
        return {}


def get_secret(name: str, default: str | None = None) -> str | None:
    """Return secret ``name`` (UPPER_SNAKE). Vault value wins over env."""
    now = time.time()
    if _CACHE["data"] is None or now - _CACHE["at"] > _TTL:
        _CACHE["data"] = _load_from_aws()
        _CACHE["at"] = now
    return _CACHE["data"].get(name) or os.getenv(name) or default


def redact(text: str) -> str:
    """Remove any known secret values from text before it is logged/returned."""
    data = _CACHE["data"] or {}
    for v in list(data.values()) + [os.getenv(k, "") for k in _SENSITIVE_ENV]:
        if v and len(v) > 8 and v in text:
            text = text.replace(v, "[REDACTED]")
    return text


_SENSITIVE_ENV = (
    "SUPABASE_SECRET_KEY",
    "FIRECRAWL_API_KEY",
    "LANGSMITH_API_KEY",
    "OLLAMA_PROXY_TOKEN",
    "DATABASE_URL",
)
