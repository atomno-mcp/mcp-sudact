"""MCP tools for the existing Sudact hosted REST contract."""

from __future__ import annotations

import argparse
import asyncio
import atexit
import logging
import os
from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field, ValidationError

from . import __version__
from .client import SudactClient
from .config import Settings
from .contracts import Anonymization, Citation, Court, Instance, Search
from .errors import BackendError, SudactError

logger = logging.getLogger("atomno_mcp_sudact")
LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
mcp = FastMCP(
    name="atomno-mcp-sudact",
    version=__version__,
    strict_input_validation=True,
    mask_error_details=True,
    instructions=(
        "Court practice and FAS case cards via the existing hosted API. "
        "Coverage/text depend on the connected service, not a complete court corpus. "
        "Only instance=any. source/collegium are not request filters. "
        "FAS returns case cards, not necessarily full rulings. "
        "Errors are not empty results. Single-attempt calls: timeout does not prove "
        "the backend did not account for the request. Requires MCP_SUDACT_TOKEN."
    ),
)
_client: SudactClient | None = None
_client_lock = asyncio.Lock()


async def _get_client() -> SudactClient:
    global _client
    async with _client_lock:
        if _client is None:
            _client = SudactClient(Settings.from_env())
            atexit.register(_close_client)
    return _client


def _close_client() -> None:
    if _client is not None:
        try:
            asyncio.run(_client.aclose())
        except RuntimeError:
            pass


async def _call(endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
    if not Settings.from_env().has_token:
        return {
            "error": "missing_token",
            "message_ru": "Не задан MCP_SUDACT_TOKEN действующей услуги.",
        }
    client = await _get_client()
    try:
        return await (client.search(payload) if endpoint == "search" else client.citation(payload))
    except BackendError as exc:
        logger.warning("Hosted %s HTTP %s", endpoint, exc.status_code)
        return {"error": "backend_error", "status": exc.status_code, "message": exc.detail}
    except SudactError as exc:
        logger.warning("Hosted %s unavailable", endpoint)
        return {"error": "unavailable", "message": str(exc)}


async def _search(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        request = Search.model_validate(payload)
    except ValidationError:
        return {
            "error": "validation",
            "message_ru": "Проверьте даты, фильтры ФАС и page/limit. Только instance=any.",
        }
    return await _call("search", request.model_dump(exclude_none=True))


@mcp.tool
async def search_cases(
    query: Annotated[
        str, Field(min_length=3, description="Текст документа или правового вопроса.")
    ],
    court_type: Annotated[
        Court, Field(description="Раздел API, не гарантия корпуса: any/vs/arbitr/soyu/ks/fas.")
    ] = "any",
    instance: Annotated[
        Instance, Field(description="Только any; прочие инстанции API не подтверждает.")
    ] = "any",
    norms: Annotated[
        list[str] | None, Field(description="Статьи закона; способ проверки определяет backend.")
    ] = None,
    date_from: Annotated[str | None, Field(description="Дата с, YYYY-MM-DD.")] = None,
    date_to: Annotated[str | None, Field(description="Дата по, YYYY-MM-DD.")] = None,
    limit: Annotated[
        int, Field(ge=1, le=50, description="Максимум1..50, не обещание количества.")
    ] = 10,
    page: Annotated[
        int | None,
        Field(
            ge=1,
            le=5,
            description="Один vs/arbitr/soyu/ks; page*limit<=50, без ФАС-фильтров. При обёртке норм backend422: запрос без page. Без смешения корпусов/fallback.",
        ),
    ] = None,
    fas_body: Annotated[str | None, Field(description="Орган ФАС; court_type=any/fas.")] = None,
    fas_law: Annotated[str | None, Field(description="44-ФЗ/223-ФЗ/135-ФЗ/38-ФЗ.")] = None,
    fas_act_type: Annotated[
        str | None,
        Field(
            description="решение/предписание/постановление/постановление о штрафе/определение/предупреждение/жалоба/уведомление."
        ),
    ] = None,
) -> dict[str, Any]:
    """Поиск подключённых источников с исходными provenance/предупреждениями.

    Доступ к разделам soyu/ks определяется услугой; полный корпус не гарантируется.
    source/collegium не поддерживаются как фильтры API. Даты/лимиты/метаданные не переписываются.
    """
    return await _search(
        dict(
            query=query,
            court_type=court_type,
            instance=instance,
            norms=norms or [],
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            page=page,
            fas_body=fas_body,
            fas_law=fas_law,
            fas_act_type=fas_act_type,
        )
    )


@mcp.tool
async def search_fas_decisions(
    query: Annotated[str, Field(min_length=3, description="Текст или номер дела ФАС.")],
    body: Annotated[str | None, Field(description="Орган ФАС.")] = None,
    law: Annotated[str | None, Field(description="44-ФЗ/223-ФЗ/135-ФЗ/38-ФЗ.")] = None,
    act_type: Annotated[str | None, Field(description="Вид акта ФАС, например решение.")] = None,
    date_from: Annotated[str | None, Field(description="Дата карточки с, YYYY-MM-DD.")] = None,
    date_to: Annotated[str | None, Field(description="Дата карточки по, YYYY-MM-DD.")] = None,
    limit: Annotated[int, Field(ge=1, le=50)] = 10,
) -> dict[str, Any]:
    """Карточки базы решений ФАС через /v1/search court_type=fas.

    Не обещает полный текст решения. Источник, дата сведений и предупреждения
    сохраняются. Текст карточки можно запросить через get_citation.
    """
    return await _search(
        dict(
            query=query,
            court_type="fas",
            fas_body=body,
            fas_law=law,
            fas_act_type=act_type,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
        )
    )


@mcp.tool
async def get_citation(
    url: Annotated[str | None, Field(description="URL из выдачи поиска.")] = None,
    case_id: Annotated[str | None, Field(description="case_id из выдачи, включая fas:.")] = None,
    include_full_text: bool = True,
    anonymize_level: Anonymization = "none",
) -> dict[str, Any]:
    """Текст акта или карточки; полный текст доступен не для каждой записи.

    Нужен url/case_id. Анонимизация и её ограничения определяются backend.
    """
    try:
        payload = Citation.model_validate(
            dict(
                url=url,
                case_id=case_id,
                include_full_text=include_full_text,
                anonymize_level=anonymize_level,
            )
        )
    except ValidationError:
        return {"error": "validation", "message_ru": "Нужно указать url или case_id."}
    return await _call("citation", payload.model_dump(exclude_none=True))


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="atomno-mcp-sudact", description="MCP-клиент Sudact hosted API."
    )
    parser.add_argument(
        "--version", "-V", action="version", version=f"atomno-mcp-sudact {__version__}"
    )
    parser.add_argument(
        "--transport", "-t", choices=("stdio", "http", "sse", "streamable-http"), default="stdio"
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--log-level", "-l", type=str.upper, choices=LOG_LEVELS, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    level = args.log_level or os.environ.get("MCP_SUDACT_LOG_LEVEL", "WARNING").upper()
    if level not in LOG_LEVELS:
        parser.error("MCP_SUDACT_LOG_LEVEL: допустимы DEBUG/INFO/WARNING/ERROR/CRITICAL")
    if not 1 <= args.port <= 65535:
        parser.error("--port: допустимо1..65535")
    logging.basicConfig(level=getattr(logging, level))
    kwargs: dict[str, Any] = {"transport": args.transport, "show_banner": False}
    if args.transport != "stdio":
        kwargs.update(host=args.host, port=args.port, log_level=level)
    mcp.run(**kwargs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
