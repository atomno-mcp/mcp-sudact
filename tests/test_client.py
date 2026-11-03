"""Тесты тонкого HTTP-клиента (на моках respx)."""

from __future__ import annotations

import httpx
import pytest
import respx

from atomno_mcp_sudact.client import SudactClient
from atomno_mcp_sudact.config import Settings
from atomno_mcp_sudact.errors import BackendError, BackendUnavailable

BASE = "https://api.example.test/sudact"


def _settings(token: str | None = "test-key") -> Settings:
    return Settings(api_base=BASE, token=token, timeout=5.0)


@pytest.fixture
async def client():
    c = SudactClient(_settings())
    yield c
    await c.aclose()


@respx.mock
async def test_search_happy_path(client: SudactClient) -> None:
    route = respx.post(f"{BASE}/v1/search").mock(
        return_value=httpx.Response(200, json={"total_found": 364, "cases": []})
    )
    out = await client.search({"query": "злоупотребление правом", "limit": 10})
    assert out["total_found"] == 364
    assert route.called
    sent = route.calls.last.request
    assert sent.headers["X-API-Key"] == "test-key"


@respx.mock
async def test_citation_happy_path(client: SudactClient) -> None:
    respx.post(f"{BASE}/v1/citation").mock(
        return_value=httpx.Response(200, json={"case_id": "А45-21421/2021", "full_text": "..."})
    )
    out = await client.citation({"url": "https://sudact.ru/x", "include_full_text": True})
    assert out["case_id"] == "А45-21421/2021"


@respx.mock
async def test_backend_4xx_raises(client: SudactClient) -> None:
    respx.post(f"{BASE}/v1/search").mock(
        return_value=httpx.Response(401, json={"message_ru": "нужен ключ"})
    )
    with pytest.raises(BackendError) as ei:
        await client.search({"query": "тест"})
    assert ei.value.status_code == 401
    assert "нужен ключ" in ei.value.detail


@respx.mock
async def test_backend_5xx_raises(client: SudactClient) -> None:
    respx.post(f"{BASE}/v1/search").mock(return_value=httpx.Response(502, text="bad gateway"))
    with pytest.raises(BackendError) as ei:
        await client.search({"query": "тест"})
    assert ei.value.status_code == 502


@respx.mock
async def test_timeout_maps_to_unavailable(client: SudactClient) -> None:
    respx.post(f"{BASE}/v1/search").mock(side_effect=httpx.TimeoutException("slow"))
    with pytest.raises(BackendUnavailable):
        await client.search({"query": "тест"})


@respx.mock
async def test_no_token_omits_header() -> None:
    c = SudactClient(_settings(token=None))
    try:
        route = respx.post(f"{BASE}/v1/search").mock(
            return_value=httpx.Response(200, json={"total_found": 0, "cases": []})
        )
        await c.search({"query": "тест"})
        assert "X-API-Key" not in route.calls.last.request.headers
    finally:
        await c.aclose()


@pytest.mark.parametrize("status", [429, 502, 503, 504, 302])
@respx.mock
async def test_single_attempt_status(client, status):
    route = respx.post(f"{BASE}/v1/search").mock(
        return_value=httpx.Response(status, json={"detail": "fixture"})
    )
    with pytest.raises(BackendError):
        await client.search({"query": "тест"})
    assert route.call_count == 1


@respx.mock
async def test_single_attempt_timeout(client):
    route = respx.post(f"{BASE}/v1/search").mock(side_effect=httpx.ReadTimeout("fixture"))
    with pytest.raises(BackendUnavailable):
        await client.search({"query": "тест"})
    assert route.call_count == 1


@pytest.mark.parametrize("body", ["<html>error</html>", "[]", "null"])
@respx.mock
async def test_invalid_json_not_empty(client, body):
    respx.post(f"{BASE}/v1/search").mock(return_value=httpx.Response(200, text=body))
    with pytest.raises(BackendError):
        await client.search({"query": "тест"})


@respx.mock
async def test_preserve_response(client):
    expected = {
        "cases": [],
        "total_found": 0,
        "warnings": ["source unavailable"],
        "provenance": {"source": "fas", "date_kind": "card"},
        "limit_applied": 10,
    }
    respx.post(f"{BASE}/v1/search").mock(return_value=httpx.Response(200, json=expected))
    assert await client.search({"query": "тест"}) == expected
