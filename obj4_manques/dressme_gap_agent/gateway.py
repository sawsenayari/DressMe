"""Bounded OpenAI-compatible gateway client with sanitized failure categories."""

from __future__ import annotations

import time
from typing import Any

from .config import AgentConfig


class GatewayCallError(RuntimeError):
    def __init__(self, message: str, category: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.category = category
        self.status_code = status_code


class OpenAICompatibleGateway:
    """Application-owned timeout/retry policy for an OpenAI-compatible client."""

    def __init__(self, client: Any, config: AgentConfig) -> None:
        self._client = client
        self._config = config

    def complete(self, messages: list[dict[str, Any]], *, model: str, **kwargs: Any) -> Any:
        temperature = kwargs.pop("temperature", self._config.temperature)
        max_tokens = kwargs.pop("max_tokens", self._config.max_tokens)
        if not 0 <= temperature <= 2 or not 1 <= max_tokens <= 4096:
            raise ValueError("Per-call generation settings are outside the supported bounds.")
        for attempt in range(self._config.max_retries + 1):
            try:
                return self._client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                )
            except Exception as exc:
                category, message = self._classify_failure(exc)
                if attempt < self._config.max_retries and category in {
                    "timeout", "rate_limit", "upstream_unavailable"
                }:
                    delay = self._retry_delay(exc, attempt)
                    if delay is not None:
                        time.sleep(delay)
                        continue
                status = getattr(exc, "status_code", None)
                raise GatewayCallError(message, category, status if isinstance(status, int) else None) from exc
        raise GatewayCallError("The LLM request failed.", "provider_error")

    @staticmethod
    def _classify_failure(exc: Exception) -> tuple[str, str]:
        error_name = type(exc).__name__.casefold()
        status = getattr(exc, "status_code", None)
        if "timeout" in error_name or "timedout" in error_name:
            return "timeout", "The LLM request timed out."
        if status == 429:
            return "rate_limit", "The gateway/provider rate limit was reached."
        if status in {401, 403}:
            return "authentication", "The gateway/provider rejected authentication."
        if status == 404:
            return "route_not_found", "The configured gateway route or model was not found."
        if status == 413:
            return "request_too_large", "The request exceeded a gateway/provider payload limit."
        if status == 400:
            return "invalid_request", "The gateway/provider rejected the request format."
        if isinstance(status, int) and status >= 500:
            return "upstream_unavailable", "The gateway/provider is temporarily unavailable."
        return "provider_error", "The LLM request failed. Check the local 9Router and model combo."

    def _retry_delay(self, exc: Exception, attempt: int) -> float | None:
        max_delay = 2.0
        response = getattr(exc, "response", None)
        headers = getattr(response, "headers", None)
        retry_after = headers.get("retry-after") if headers is not None else None
        if retry_after is not None:
            try:
                delay = float(retry_after)
            except (TypeError, ValueError):
                return None
            return delay if 0 <= delay <= max_delay else None
        return min(self._config.retry_backoff_seconds * (2**attempt), max_delay)
