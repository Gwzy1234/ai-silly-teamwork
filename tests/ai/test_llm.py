from __future__ import annotations

import json

import httpx
import pytest

from silly_teamwork.ai.llm import (
    AIConfigurationError,
    MiMoProvider,
    MockProvider,
)


@pytest.mark.asyncio
async def test_mock_provider_returns_canned_response() -> None:
    provider = MockProvider(
        responses=[
            '{"risk_level": "low"}',
            '{"summary": "ok"}',
        ]
    )

    first = await provider.complete([{"role": "user", "content": "hello"}])
    second = await provider.complete([{"role": "user", "content": "world"}])

    assert first == '{"risk_level": "low"}'
    assert second == '{"summary": "ok"}'
    assert len(provider.calls) == 2


@pytest.mark.asyncio
async def test_mock_provider_uses_default_response() -> None:
    provider = MockProvider(default_response="{}")
    response = await provider.complete([])
    assert response == "{}"


@pytest.mark.asyncio
async def test_mimo_provider_sends_openai_compatible_request() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://api.xiaomimimo.com/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer test-key"
        body = json.loads(request.read().decode())
        assert body["model"] == "test-model"
        assert body["max_tokens"] == 100
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "ok"}}]},
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = MiMoProvider(
            api_key="test-key",
            base_url="https://api.xiaomimimo.com/v1",
            model="test-model",
            client=client,
        )
        response = await provider.complete(
            [{"role": "user", "content": "hello"}],
            max_tokens=100,
        )

    assert response == "ok"


@pytest.mark.asyncio
async def test_mimo_provider_requires_api_key() -> None:
    provider = MiMoProvider(
        api_key="",
        base_url="https://api.xiaomimimo.com/v1",
        model="test-model",
    )
    with pytest.raises(AIConfigurationError):
        await provider.complete([{"role": "user", "content": "hello"}])
