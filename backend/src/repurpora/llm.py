"""LLM + embedding factories (Ollama, hosted on AWS EC2 behind a bearer-token proxy).

Model routing (reference image 13 - "route to the best model for the job"):
  * ``primary`` (qwen2.5 7B)  - planner, synthesizer
  * ``fast``    (qwen2.5 3B)  - worker notes, judge, guard classifier
An exact-match LLM response cache (Redis or in-memory) cuts repeat-query cost.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Literal

from langchain_core.globals import set_llm_cache
from langchain_ollama import ChatOllama, OllamaEmbeddings

from repurpora.settings import get_settings
from repurpora.vault import get_secret

log = logging.getLogger(__name__)
Role = Literal["primary", "fast"]


def _client_kwargs() -> dict:
    token = get_secret("OLLAMA_PROXY_TOKEN") or get_settings().ollama_proxy_token
    kw: dict = {"timeout": get_settings().llm_timeout_s}
    if token:
        kw["headers"] = {"Authorization": f"Bearer {token}"}
    return kw


def _init_cache() -> None:
    s = get_settings()
    try:
        if s.redis_url:
            import redis
            from langchain_community.cache import RedisCache

            client = redis.Redis.from_url(s.redis_url, socket_timeout=1.5)
            client.ping()
            set_llm_cache(RedisCache(redis_=client, ttl=24 * 3600))
            log.info("LLM cache: redis")
            return
    except Exception as exc:
        log.warning("redis LLM cache unavailable (%s)", type(exc).__name__)
    from langchain_core.caches import InMemoryCache

    set_llm_cache(InMemoryCache(maxsize=512))


_init_cache()


@lru_cache(maxsize=8)
def get_llm(role: Role = "primary", temperature: float | None = None, json_mode: bool = False) -> ChatOllama:
    s = get_settings()
    model = s.llm_model_primary if role == "primary" else s.llm_model_fast
    return ChatOllama(
        model=model,
        base_url=s.ollama_base_url,
        temperature=s.llm_temperature if temperature is None else temperature,
        num_ctx=s.llm_num_ctx,
        keep_alive=s.llm_keep_alive,
        format="json" if json_mode else None,
        client_kwargs=_client_kwargs(),
        tags=[f"model:{model}", f"role:{role}"],
    )


@lru_cache(maxsize=1)
def get_embeddings() -> OllamaEmbeddings:
    s = get_settings()
    return OllamaEmbeddings(model=s.embed_model, base_url=s.ollama_base_url, client_kwargs=_client_kwargs())


def llm_available() -> bool:
    import httpx

    s = get_settings()
    try:
        r = httpx.get(f"{s.ollama_base_url.rstrip('/')}/api/tags", timeout=4,
                      headers=_client_kwargs().get("headers"))
        return r.status_code == 200
    except Exception:
        return False
