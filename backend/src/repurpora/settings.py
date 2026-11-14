"""Central, typed configuration.

Every value comes from the environment (or a gitignored ``.env``). Secrets are
*not* read here directly for runtime use - see :mod:`repurpora.vault`, which
prefers AWS Secrets Manager (LocalStack in the prototype) and falls back to env.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
# export .env into os.environ so boto3 / langsmith / aegra see the same values
load_dotenv(BACKEND_DIR / ".env", override=False)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BACKEND_DIR / ".env", BACKEND_DIR.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- runtime -----------------------------------------------------------
    env_mode: str = "development"
    log_level: str = "INFO"

    # --- LLM (Ollama, hosted on AWS EC2 in prod / local GPU container in proto)
    ollama_base_url: str = "http://localhost:11434"
    ollama_proxy_token: str | None = None  # bearer token enforced by Caddy proxy
    llm_model_primary: str = "qwen2.5:7b-instruct"  # planner / synthesizer
    llm_model_fast: str = "qwen2.5:3b-instruct"  # worker notes / judge / guard
    embed_model: str = "nomic-embed-text"
    embed_dim: int = 768
    llm_temperature: float = 0.1
    llm_num_ctx: int = 8192
    llm_keep_alive: str = "30m"
    llm_timeout_s: float = 180.0

    # --- data sources ------------------------------------------------------
    mock_api_url: str = "http://localhost:8081"
    use_live_ctgov: bool = True
    firecrawl_api_key: str | None = None
    use_live_web: bool = True

    # --- storage -----------------------------------------------------------
    supabase_url: str | None = None
    supabase_secret_key: str | None = None
    supabase_publishable_key: str | None = None
    supabase_jwks_url: str | None = None
    database_url: str | None = None  # Postgres (Supabase session pooler) - used by Aegra
    app_database_url: str | None = None  # app pool (RAG/audit/usage) - Supabase transaction pooler :6543
    reports_bucket: str = "reports"

    # --- AWS (LocalStack emulator in prototype) ----------------------------
    aws_endpoint_url: str | None = None  # e.g. http://localhost:4566 -> LocalStack
    aws_region: str = "ap-south-1"
    aws_secret_name: str = "repurpora/app"
    aws_reports_bucket: str = "repurpora-reports"
    aws_log_group: str = "/repurpora/audit"

    # --- cache ---------------------------------------------------------------
    redis_url: str | None = None
    tool_cache_ttl_s: int = 3600

    # --- guardrails / budgets ------------------------------------------------
    max_workers_per_query: int = 6
    max_redrafts: int = 1
    max_input_chars: int = 4000
    context_token_budget: int = 6000
    evidence_coverage_threshold: float = 0.75
    require_human_approval: bool = False  # HITL interrupt before archiving

    # --- auth ------------------------------------------------------------------
    auth_disabled: bool = False

    reports_dir: Path = BACKEND_DIR / "reports_out"
    internal_docs_dir: Path = BACKEND_DIR / "data" / "internal_docs"


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.reports_dir.mkdir(parents=True, exist_ok=True)
    return s
