import pytest

from atomno_mcp_sudact import server
from atomno_mcp_sudact.errors import BackendError, BackendUnavailable


@pytest.mark.parametrize("transport", ["stdio", "http", "sse", "streamable-http"])
def test_cli_transport(monkeypatch, transport):
    seen = []
    monkeypatch.setattr(server.mcp, "run", lambda **kw: seen.append(kw))
    monkeypatch.setenv("MCP_SUDACT_LOG_LEVEL", "BAD")
    assert (
        server.main(["-t", transport, "--host", "127.0.0.2", "--port", "8123", "-l", "info"]) == 0
    )
    assert seen[0]["show_banner"] is False
    assert ("host" in seen[0]) == (transport != "stdio")
    if transport != "stdio":
        assert seen[0]["port"] == 8123


@pytest.mark.parametrize(
    "argv,env", [([], "BAD"), (["--port", "0"], "INFO"), (["--port", "65536"], "INFO")]
)
def test_cli_bad(monkeypatch, argv, env):
    monkeypatch.setenv("MCP_SUDACT_LOG_LEVEL", env)
    with pytest.raises(SystemExit) as ex:
        server.main(argv)
    assert ex.value.code == 2


async def test_missing(monkeypatch):
    monkeypatch.delenv("MCP_SUDACT_TOKEN", raising=False)
    assert (await server._call("search", {}))["error"] == "missing_token"


@pytest.mark.parametrize("error", [BackendError(401, "denied"), BackendUnavailable("timeout")])
async def test_errors(monkeypatch, error):
    monkeypatch.setenv("MCP_SUDACT_TOKEN", "SYNTHETIC")

    class Client:
        async def search(self, payload):
            raise error

    async def get():
        return Client()

    monkeypatch.setattr(server, "_get_client", get)
    out = await server._call("search", {})
    assert out["error"] in ("backend_error", "unavailable")
    if isinstance(error, BackendError):
        assert out["status"] == 401


async def test_search_validation_and_mapping(monkeypatch):
    seen = []

    async def call(endpoint, payload):
        seen.append((endpoint, payload))
        return {"cases": [], "warnings": ["coverage"]}

    monkeypatch.setattr(server, "_call", call)
    assert (await server._search({"query": "bad", "page": 1}))["error"] == "validation"
    out = await server.search_fas_decisions("тест", law="44-ФЗ")
    assert out["warnings"] == ["coverage"]
    assert seen[0][1]["court_type"] == "fas"
    await server.search_cases("тест", court_type="soyu", page=1)
    assert seen[-1][1]["page"] == 1
    assert (await server.get_citation())["error"] == "validation"
    await server.get_citation(case_id="fas:test")
    assert seen[-1][0] == "citation"
