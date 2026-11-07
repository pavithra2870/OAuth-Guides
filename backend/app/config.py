"""Central configuration, read from the environment (and the repo-root .env).

Everything tunable lives here: key pools, model names, provider order and
timeouts. Secrets are never logged; use `settings.redact()` on any text that
might contain one.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")


def _str(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _float(name: str, default: float) -> float:
    try:
        return float(_str(name) or default)
    except ValueError:
        return default


def _list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in (_str(name) or default).split(",") if item.strip()]


def key_pool(prefix: str, names_var: str) -> list[str]:
    """Return the API keys for a provider, in rotation order.

    `names_var` may hold explicit variable names (e.g. "GEMINI2,GEMINI1").
    If empty, every `<PREFIX><number>` variable is used, sorted by number.
    """
    names = _list(names_var)
    if not names:
        pattern = re.compile(rf"^{prefix}(\d+)$")
        found = [(int(m.group(1)), n) for n in os.environ if (m := pattern.match(n))]
        names = [n for _, n in sorted(found)]
    return [v for n in names if (v := _str(n))]


@dataclass(frozen=True)
class Settings:
    # keys
    gemini_keys: list[str]
    groq_keys: list[str]
    tavily_keys: list[str]
    database_url: str
    # model controls
    llm_provider_order: list[str]
    gemini_models: list[str]  # tried in order; the next one is the fallback
    groq_models: list[str]
    groq_max_prompt_chars: int  # Groq's free tier allows ~8k tokens per minute: send it a trimmed prompt
    groq_max_tokens: int
    # timeouts / limits (seconds)
    http_connect_timeout: float
    http_read_timeout: float
    check_timeout: float
    generation_deadline: float
    sse_heartbeat: float
    status_cache_ttl: float
    llm_timeout: float
    llm_max_tokens: int
    gemini_thinking_budget: int  # tokens; -1 = leave to the model
    # research / generation
    guide_fresh_days: float
    search_results_per_query: int
    max_sources: int
    source_char_limit: int
    daily_cap_per_ip: int
    daily_cap_global: int
    # server
    cors_origins: list[str]

    def secrets(self) -> list[str]:
        values = [*self.gemini_keys, *self.groq_keys, *self.tavily_keys, self.database_url]
        return [v for v in values if v]

    def redact(self, text: str) -> str:
        """Mask any secret (and the password inside DATABASE_URL) in `text`."""
        for secret in sorted(self.secrets(), key=len, reverse=True):
            text = text.replace(secret, "***")
        match = re.match(r"^\w+://[^:/@]+:([^@]+)@", self.database_url)
        if match:
            text = text.replace(match.group(1), "***")
        return text

    def public_summary(self) -> dict:
        """Safe-to-expose view of the configuration (no secrets)."""
        return {
            "providers": self.llm_provider_order,
            "models": {"gemini": self.gemini_models, "groq": self.groq_models},
            "keys": {
                "gemini": len(self.gemini_keys),
                "groq": len(self.groq_keys),
                "tavily": len(self.tavily_keys),
            },
            "database": "postgres" if self.database_url else "sqlite (local)",
        }


@lru_cache
def get_settings() -> Settings:
    return Settings(
        gemini_keys=key_pool("GEMINI", "GEMINI_KEYS"),
        groq_keys=key_pool("GROQ", "GROQ_KEYS"),
        tavily_keys=key_pool("TAVILY", "TAVILY_KEYS"),
        database_url=_str("DATABASE_URL"),
        llm_provider_order=_list("LLM_PROVIDER_ORDER", "gemini,groq"),
        gemini_models=_list("GEMINI_MODELS", "gemini-3.5-flash,gemini-3.6-flash,gemini-3-flash-preview,gemini-3.1-flash-lite"),
        groq_models=_list("GROQ_MODELS", "openai/gpt-oss-120b,openai/gpt-oss-20b"),
        groq_max_prompt_chars=int(_float("GROQ_MAX_PROMPT_CHARS", 12000)),
        groq_max_tokens=int(_float("GROQ_MAX_TOKENS", 4500)),
        http_connect_timeout=_float("HTTP_CONNECT_TIMEOUT", 5),
        http_read_timeout=_float("HTTP_READ_TIMEOUT", 30),
        check_timeout=_float("CHECK_TIMEOUT", 15),
        generation_deadline=_float("GENERATION_DEADLINE", 150),
        sse_heartbeat=_float("SSE_HEARTBEAT", 10),
        status_cache_ttl=_float("STATUS_CACHE_TTL", 30),
        llm_timeout=_float("LLM_TIMEOUT", 120),
        llm_max_tokens=int(_float("LLM_MAX_TOKENS", 24000)),
        gemini_thinking_budget=int(_float("GEMINI_THINKING_BUDGET", 1024)),
        guide_fresh_days=_float("GUIDE_FRESH_DAYS", 30),
        search_results_per_query=int(_float("SEARCH_RESULTS_PER_QUERY", 5)),
        max_sources=int(_float("MAX_SOURCES", 10)),
        source_char_limit=int(_float("SOURCE_CHAR_LIMIT", 9000)),
        daily_cap_per_ip=int(_float("DAILY_CAP_PER_IP", 10)),
        daily_cap_global=int(_float("DAILY_CAP_GLOBAL", 150)),
        cors_origins=_list("CORS_ORIGINS", "http://localhost:5173"),
    )
