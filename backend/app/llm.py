"""LLM access with provider fallback, model fallback and key rotation.

`generate_json` walks `LLM_PROVIDER_ORDER`. Within a provider it walks the model
list (`GEMINI_MODELS`, `GROQ_MODELS`) and, for each model, rotates through the keys:

  * 429 (quota)      -> that key is cooled down *for that model*; try the next key, then the next model
  * 404 (retired)    -> this model is unavailable to the key; skip to the next model
  * 5xx / timeout    -> short cooldown, try the next key / model
  * 401 / 403        -> key is bad, long cooldown

`user` may be a callable taking a character budget (or None) so a provider with a
small context/rate limit (Groq free tier) can be sent a trimmed prompt.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable

import httpx

from .config import get_settings
from .keys import KeyPool

log = logging.getLogger("llm")

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
GROQ_BASE = "https://api.groq.com/openai/v1"

UserPrompt = str | Callable[[int | None], str]


class LLMError(Exception):
    """Every provider, model and key failed."""


@dataclass
class LLMResult:
    text: str
    provider: str
    model: str
    key_label: str


_pools: dict[str, KeyPool] = {}


def _pool(provider: str) -> KeyPool:
    if provider not in _pools:
        s = get_settings()
        keys = {"gemini": s.gemini_keys, "groq": s.groq_keys}.get(provider, [])
        _pools[provider] = KeyPool(provider, keys)
    return _pools[provider]


def _models(provider: str) -> list[str]:
    s = get_settings()
    return {"gemini": s.gemini_models, "groq": s.groq_models}.get(provider, [])


async def _call_gemini(client: httpx.AsyncClient, key: str, model: str, system: str, user: str,
                       temperature: float, max_tokens: int) -> httpx.Response:
    config: dict = {
        "temperature": temperature,
        "maxOutputTokens": max_tokens,
        "responseMimeType": "application/json",
    }
    budget = get_settings().gemini_thinking_budget
    if budget >= 0 and model.startswith("gemini-2.5"):
        config["thinkingConfig"] = {"thinkingBudget": budget}
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": config,
    }
    return await client.post(f"{GEMINI_BASE}/models/{model}:generateContent", json=body,
                             headers={"x-goog-api-key": key})


async def _call_groq(client: httpx.AsyncClient, key: str, model: str, system: str, user: str,
                     temperature: float, max_tokens: int) -> httpx.Response:
    body = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "temperature": temperature,
        "max_tokens": min(max_tokens, get_settings().groq_max_tokens),
        "response_format": {"type": "json_object"},
    }
    return await client.post(f"{GROQ_BASE}/chat/completions", json=body,
                             headers={"Authorization": f"Bearer {key}"})


def _extract_text(provider: str, response: httpx.Response) -> str:
    data = response.json()
    if provider == "gemini":
        candidates = data.get("candidates") or []
        if not candidates:
            raise ValueError(f"no candidates ({data.get('promptFeedback', {}).get('blockReason', 'empty')})")
        if candidates[0].get("finishReason") == "MAX_TOKENS":
            raise ValueError("output truncated (MAX_TOKENS)")
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
    else:
        choice = (data.get("choices") or [{}])[0]
        if choice.get("finish_reason") == "length":
            raise ValueError("output truncated (length)")
        text = choice.get("message", {}).get("content") or ""
    if not text.strip():
        raise ValueError("empty response")
    return text


_CALLERS = {"gemini": _call_gemini, "groq": _call_groq}


def _budget(provider: str) -> int | None:
    return get_settings().groq_max_prompt_chars if provider == "groq" else None


async def generate_json(system: str, user: UserPrompt, *, temperature: float = 0.2,
                        max_tokens: int | None = None) -> LLMResult:
    """Return the model's JSON text. Raises LLMError if every provider/model/key fails."""
    settings = get_settings()
    max_tokens = max_tokens or settings.llm_max_tokens
    errors: list[str] = []
    timeout = httpx.Timeout(settings.llm_timeout, connect=settings.http_connect_timeout)

    async with httpx.AsyncClient(timeout=timeout) as client:
        for provider in settings.llm_provider_order:
            caller = _CALLERS.get(provider)
            pool = _pool(provider)
            if not caller or not len(pool):
                continue
            prompt = user(_budget(provider)) if callable(user) else user

            for model in _models(provider):
                for label, key in pool.candidates(scope=model):
                    try:
                        response = await caller(client, key, model, system, prompt, temperature, max_tokens)
                    except httpx.TimeoutException:
                        errors.append(f"{label}/{model}: timed out")
                        pool.penalize(label, 20, scope=model)
                        continue
                    except httpx.HTTPError as exc:
                        errors.append(f"{label}/{model}: {type(exc).__name__}")
                        pool.penalize(label, 20, scope=model)
                        continue

                    status = response.status_code
                    if status == 200:
                        try:
                            result = LLMResult(_extract_text(provider, response), provider, model, label)
                            log.info("generated via %s (%s)", model, label)
                            return result
                        except ValueError as exc:
                            errors.append(f"{label}/{model}: {exc}")
                            continue

                    errors.append(f"{label}/{model}: HTTP {status}")
                    if status in (401, 403):
                        pool.penalize(label, 3600, scope=model)
                    elif status == 429:
                        pool.penalize(label, 300, scope=model)
                    elif status >= 500:
                        pool.penalize(label, 20, scope=model)
                    elif status in (400, 404, 413):
                        break  # this model won't take the request: try the next model, not another key

    detail = settings.redact("; ".join(errors)) or "no provider configured"
    log.warning("all LLM attempts failed: %s", detail)
    raise LLMError(detail)
