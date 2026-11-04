import httpx
import pytest

from atomno_mcp_sudact import server
from atomno_mcp_sudact.client import SudactClient
from atomno_mcp_sudact.config import Settings
from atomno_mcp_sudact.errors import BackendUnavailable


def test_public_mcp_court_choices_exclude_unavailable_ks():
    from typing import get_type_hints

    from pydantic import TypeAdapter
    choices = TypeAdapter(get_type_hints(server.search_cases, include_extras=True)["court_type"]).json_schema()["enum"]
    assert "ks" not in choices


async def test_new_tools_forward_once_and_preserve_result(monkeypatch):
    calls = []
    result = {"court_resolution": {"status": "ambiguous", "complete_directory": False},
              "search_meta": {"partial_errors": [{"source": "ras", "error": "index_unavailable"}]}}

    async def call(endpoint, payload):
        calls.append((endpoint, payload))
        return result

    monkeypatch.setattr(server, "_call", call)
    assert await server.get_search_capabilities() is result
    assert calls == [("capabilities", {})]
    assert await server.resolve_court_name("Суд", "arbitr", case_number="А40-1/2024") is result
    assert calls[-1][0] == "resolve_court"
    assert calls[-1][1]["case_number"] == "А40-1/2024"
    count = len(calls)
    assert (await server.resolve_court_name("Суд", "fas"))["error"] == "validation"
    assert (await server.search_cases(court_type="vs", court="Суд", case_number="123"))["error"] == "validation"
    assert len(calls) == count
    assert await server.search_cases(case_number="А40-1/2024", court_type="arbitr") is result
    assert calls[-1][1]["query"] == ""


async def test_capabilities_get_resolver_post_single_attempt():
    calls = []

    def respond(request):
        calls.append((request.method, request.url.path))
        return httpx.Response(200, json={"unchanged": True})

    client = SudactClient(Settings("http://synthetic", None, 1))
    await client._client.aclose()
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(respond), base_url="http://synthetic")
    assert await client.capabilities({}) == {"unchanged": True}
    assert await client.resolve_court({"name": "Суд", "court_type": "arbitr"}) == {"unchanged": True}
    assert calls == [("GET", "/v1/capabilities"), ("POST", "/v1/resolve-court")]
    await client.aclose()


async def test_capabilities_timeout_not_retried():
    attempts = []

    def respond(request):
        attempts.append(request)
        raise httpx.ReadTimeout("synthetic timeout", request=request)

    client = SudactClient(Settings("http://synthetic", None, 1))
    await client._client.aclose()
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(respond), base_url="http://synthetic")
    with pytest.raises(BackendUnavailable):
        await client.capabilities({})
    assert len(attempts) == 1
    await client.aclose()


@pytest.mark.parametrize("caps", [None, {}, {"contract": "sudact-search-controls-v1", "sections": []}])
async def test_old_or_malformed_backend_never_receives_new_filter_post(monkeypatch, caps):
    monkeypatch.setenv("MCP_SUDACT_TOKEN", "SYNTHETIC_STAGE_TEST")
    calls = []

    def respond(request):
        calls.append((request.method, request.url.path))
        if request.method == "GET":
            return httpx.Response(404) if caps is None else httpx.Response(200, json=caps)
        return httpx.Response(200, json={"old_style_ok": True})

    client = SudactClient(Settings("http://synthetic", None, 1))
    await client._client.aclose()
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(respond), base_url="http://synthetic")
    async def get_client(): return client
    monkeypatch.setattr(server, "_get_client", get_client)
    assert (await server.search_cases(court_type="arbitr", case_number="А40-1/2024"))["error"] == "unsupported_backend"
    assert calls == [("GET", "/v1/capabilities")]
    assert (await server.resolve_court_name("Суд", "arbitr"))["error"] == "unsupported_backend"
    assert all(method == "GET" for method, _ in calls)
    assert await server.search_cases("обычный запрос") == {"old_style_ok": True}
    assert calls[-1] == ("POST", "/v1/search")
    await client.aclose()


async def test_capability_is_rechecked_after_backend_rollback(monkeypatch):
    monkeypatch.setenv("MCP_SUDACT_TOKEN", "SYNTHETIC_STAGE_TEST")
    gets, posts = [], []
    modern = {"contract": "sudact-search-controls-v1", "sections": {
        "arbitr": {"filters": ["case_number"], "instance": ["any"]}}}

    def respond(request):
        if request.method == "GET":
            gets.append(request)
            return httpx.Response(200, json=modern) if len(gets) == 1 else httpx.Response(404)
        posts.append(request)
        return httpx.Response(200, json={"cases": [], "search_meta": {
            "filter_contract": "sudact-search-controls-v1", "applied_filters": {"case_number": "А40-1/2024"}}})

    client = SudactClient(Settings("http://synthetic", None, 1))
    await client._client.aclose()
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(respond), base_url="http://synthetic")
    async def get_client(): return client
    monkeypatch.setattr(server, "_get_client", get_client)
    assert (await server.search_cases(court_type="arbitr", case_number="А40-1/2024"))["cases"] == []
    assert (await server.search_cases(court_type="arbitr", case_number="А40-1/2024"))["error"] == "unsupported_backend"
    assert len(gets) == 2 and len(posts) == 1
    await client.aclose()


@pytest.mark.parametrize("status", [401, 403, 429, 500, 502, 503, 504])
async def test_handshake_denial_preserves_status_without_search_post(monkeypatch, status):
    monkeypatch.setenv("MCP_SUDACT_TOKEN", "SYNTHETIC_STAGE_TEST")
    calls = []

    def respond(request):
        calls.append(request.method)
        return httpx.Response(status, json={"error": "synthetic_denial"})

    client = SudactClient(Settings("http://synthetic", None, 1))
    await client._client.aclose()
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(respond), base_url="http://synthetic")
    async def get_client(): return client
    monkeypatch.setattr(server, "_get_client", get_client)
    result = await server.search_cases(court_type="soyu", case_number="2-1/2024")
    assert result["error"] == "backend_error" and result["status"] == status
    assert calls == ["GET"]
    await client.aclose()


async def test_handshake_timeout_no_post_and_incompatible_post_response_no_retry(monkeypatch):
    monkeypatch.setenv("MCP_SUDACT_TOKEN", "SYNTHETIC_STAGE_TEST")
    calls = []
    mode = "timeout"

    def respond(request):
        calls.append(request.method)
        if mode == "timeout":
            raise httpx.ReadTimeout("synthetic", request=request)
        if request.method == "GET":
            return httpx.Response(200, json={"contract": "sudact-search-controls-v1", "sections": {
                "arbitr": {"filters": ["case_number"], "instance": ["any"]}}})
        return httpx.Response(200, json={"cases": []})  # models a rollback after the GET

    client = SudactClient(Settings("http://synthetic", None, 1))
    await client._client.aclose()
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(respond), base_url="http://synthetic")
    async def get_client(): return client
    monkeypatch.setattr(server, "_get_client", get_client)
    result = await server.search_cases(court_type="arbitr", case_number="А40-1/2024")
    assert result["error"] == "unavailable" and calls == ["GET"]
    mode = "incompatible"
    result = await server.search_cases(court_type="arbitr", case_number="А40-1/2024")
    assert result["error"] == "incompatible_response" and result["post_sent"] is True
    assert calls == ["GET", "GET", "POST"]
    await client.aclose()
