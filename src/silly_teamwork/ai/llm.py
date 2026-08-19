from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

import httpx
from pydantic import SecretStr

from silly_teamwork.core.config import get_settings

DEFAULT_MIMO_BASE_URL = "https://api.xiaomimimo.com/v1"

ChatMessage = dict[str, str]


class AIProviderError(RuntimeError):
    """Base error for AI provider failures."""


class AIConfigurationError(AIProviderError):
    """Raised when the LLM provider is not fully configured."""


class AIResponseError(AIProviderError):
    """Raised when the LLM provider returns an unexpected response."""


class LLMProvider(Protocol):
    """Minimal LLM provider interface used by the AI service."""

    async def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        max_tokens: int | None = None,
        temperature: float = 0.2,
    ) -> str:
        """Return a plain-text completion for the given chat messages."""
        ...


class MiMoProvider:
    """Xiaomi MiMo provider using the OpenAI-compatible chat completions API."""

    def __init__(
        self,
        *,
        api_key: SecretStr | str | None = None,
        base_url: str = "",
        model: str = "",
        timeout_seconds: float = 30,
        max_tokens: int = 2000,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        settings = get_settings()
        if api_key is None:
            resolved_api_key = settings.ai_llm_api_key.get_secret_value()
        elif isinstance(api_key, SecretStr):
            resolved_api_key = api_key.get_secret_value()
        else:
            resolved_api_key = api_key
        self._api_key = SecretStr(resolved_api_key)
        self._base_url = (base_url or settings.ai_llm_base_url or DEFAULT_MIMO_BASE_URL).rstrip(
            "/"
        )
        self._model = model or settings.ai_llm_model
        self._timeout_seconds = timeout_seconds
        self._max_tokens = max_tokens
        self._client = client

    async def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        max_tokens: int | None = None,
        temperature: float = 0.2,
    ) -> str:
        api_key = self._api_key.get_secret_value()
        if not api_key:
            raise AIConfigurationError("MiMo API key is not configured")
        if not self._model:
            raise AIConfigurationError("MiMo model is not configured")

        payload: dict[str, object] = {
            "model": self._model,
            "messages": [dict(message) for message in messages],
            "temperature": temperature,
            "max_tokens": max_tokens if max_tokens is not None else self._max_tokens,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self._base_url}/chat/completions"

        if self._client is not None:
            response = await self._client.post(url, json=payload, headers=headers)
        else:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.post(url, json=payload, headers=headers)

        if response.status_code >= 400:
            raise AIResponseError(
                f"MiMo API returned HTTP {response.status_code}: {response.text[:500]}"
            )

        try:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise AIResponseError("Unexpected MiMo API response shape") from error
        if not isinstance(content, str):
            raise AIResponseError("MiMo API response content is not a string")
        return content


class MockProvider:
    """In-memory LLM provider for tests and local development without a real API key."""

    def __init__(
        self,
        responses: Sequence[str] | None = None,
        default_response: str = "{}",
    ) -> None:
        self._responses = list(responses or [])
        self._default_response = default_response
        self.calls: list[list[ChatMessage]] = []

    async def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        max_tokens: int | None = None,
        temperature: float = 0.2,
    ) -> str:
        self.calls.append(list(messages))
        if self._responses:
            return self._responses.pop(0)
        return self._default_response


def create_llm_provider() -> LLMProvider:
    """Create the configured provider, falling back to MockProvider when AI is disabled."""
    settings = get_settings()
    if settings.ai_llm_enabled:
        return MiMoProvider(
            api_key=settings.ai_llm_api_key,
            base_url=settings.ai_llm_base_url,
            model=settings.ai_llm_model,
            timeout_seconds=settings.ai_llm_timeout_seconds,
            max_tokens=settings.ai_llm_max_tokens,
        )
    return MockProvider()
