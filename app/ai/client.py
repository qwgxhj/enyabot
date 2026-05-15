from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
from loguru import logger

from app.config.model_config import ModelConfig

# Retryable HTTP status codes
_RETRY_STATUSES = {429, 500, 502, 503, 504}
_MAX_RETRIES = 3
_BASE_DELAY = 1.0  # seconds


class AIClient:
    def __init__(self):
        self._http = httpx.AsyncClient(timeout=60)

    async def chat(self, messages: list[dict[str, Any]], model_config: ModelConfig, tools: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model_config.model_name,
            "messages": messages,
            "temperature": model_config.temperature,
            "max_tokens": model_config.max_tokens,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        headers = {
            "Authorization": f"Bearer {model_config.api_key}",
            "Content-Type": "application/json",
        }
        url = f"{model_config.base_url.rstrip('/')}/chat/completions"

        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                response = await self._http.post(url, headers=headers, json=payload)
                if response.status_code in _RETRY_STATUSES and attempt < _MAX_RETRIES - 1:
                    delay = _BASE_DELAY * (2 ** attempt)
                    retry_after = response.headers.get("retry-after")
                    if retry_after:
                        try:
                            delay = max(delay, float(retry_after))
                        except ValueError:
                            pass
                    logger.warning(f"AIClient got {response.status_code}, retrying in {delay:.1f}s (attempt {attempt + 1}/{_MAX_RETRIES})")
                    await asyncio.sleep(delay)
                    continue
                response.raise_for_status()
                return response.json()
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout) as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES - 1:
                    delay = _BASE_DELAY * (2 ** attempt)
                    logger.warning(f"AIClient network error ({type(exc).__name__}), retrying in {delay:.1f}s (attempt {attempt + 1}/{_MAX_RETRIES})")
                    await asyncio.sleep(delay)
                else:
                    raise
            except httpx.HTTPStatusError:
                raise

        raise last_exc  # type: ignore[misc]

    async def close(self):
        await self._http.aclose()
