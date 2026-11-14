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


def get_llm(role: Role = "primary", temperature: float | None = None, json_mode: bool = False):
    """Chat model for a role. Model names and temperature come from the admin-managed runtime config."""
    from repurpora import runtime_config

    cfg = runtime_config.get()
    model = cfg.llm_model_primary if role == "primary" else cfg.llm_model_fast
    temp = cfg.llm_temperature if temperature is None else temperature
    return _build_llm(role, model, round(float(temp), 3), json_mode)


@lru_cache(maxsize=16)
def _build_llm(role: Role, model: str, temp: float, json_mode: bool):
    """Provider-agnostic: Ollama (default) or any OpenAI-compatible API."""
    s = get_settings()
    # hard output caps stop runaway generations (e.g. a small model looping inside a JSON string)
    max_out = 400 if json_mode else (1400 if role == "primary" else 512)
    if s.llm_provider.lower() in ("openai", "openai_compatible", "vllm"):
        from langchain_openai import ChatOpenAI

        kw = {"response_format": {"type": "json_object"}} if json_mode else {}
        return ChatOpenAI(model=model, temperature=temp, base_url=s.openai_base_url, max_tokens=max_out,
                          api_key=get_secret("OPENAI_API_KEY") or s.openai_api_key or "not-needed",
                          timeout=s.llm_timeout_s, model_kwargs=kw, tags=[f"model:{model}", f"role:{role}"])
    return ChatOllama(
        model=model,
        base_url=s.ollama_base_url,
        temperature=temp,
        num_ctx=s.llm_num_ctx,
        num_predict=max_out,
        keep_alive=s.llm_keep_alive,
        format="json" if json_mode else None,
        client_kwargs=_client_kwargs(),
        tags=[f"model:{model}", f"role:{role}"],
    )


@lru_cache(maxsize=1)
def get_embeddings():
    s = get_settings()
    if s.embed_provider.lower() in ("openai", "openai_compatible"):
        from langchain_openai import OpenAIEmbeddings

        return OpenAIEmbeddings(model=s.embed_model, base_url=s.openai_base_url, dimensions=s.embed_dim,
                                api_key=get_secret("OPENAI_API_KEY") or s.openai_api_key or "not-needed")
    return OllamaEmbeddings(model=s.embed_model, base_url=s.ollama_base_url, client_kwargs=_client_kwargs())


def llm_available() -> bool:
    import httpx

    s = get_settings()
    if s.llm_provider.lower() != "ollama":
        return True
    try:
        r = httpx.get(f"{s.ollama_base_url.rstrip('/')}/api/tags", timeout=4,
                      headers=_client_kwargs().get("headers"))
        return r.status_code == 200
    except Exception:
        return False
