<!-- mcp-name: io.github.atomno-mcp/mcp-sudact -->

# atomno-mcp-sudact

MCP-сервер судебной практики России: ищет судебные решения по тексту, статье закона, суду, инстанции и дате и отдаёт полный текст выбранного дела. Для юристов и юридических компаний — подключается к Cursor, Claude и любому клиенту MCP.

Russian court practice search for AI agents.

[![Glama](https://img.shields.io/badge/Glama-listed-7c3aed.svg)](https://glama.ai/mcp/servers/atomno-mcp/mcp-sudact)

<a href="https://glama.ai/mcp/servers/atomno-mcp/mcp-sudact">
  <img width="380" height="200" src="https://glama.ai/mcp/servers/atomno-mcp/mcp-sudact/badge" alt="mcp-sudact MCP server" />
</a>

[![PyPI](https://img.shields.io/pypi/v/atomno-mcp-sudact)](https://pypi.org/project/atomno-mcp-sudact/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](./LICENSE)
[![MCP](https://img.shields.io/badge/MCP-compatible-blue)](https://modelcontextprotocol.io)

> Работает через интернет-сервис atomno-mcp: поиск, кэш и скрытие персональных данных — на нашей стороне, ничего парсить и поднимать не нужно. Нужен только ключ (тариф Pro) —
> [atomno-mcp.ru/pricing](https://atomno-mcp.ru/pricing#sudact-pro).

## Быстрый старт

```bash
pipx install atomno-mcp-sudact
# или: uvx atomno-mcp-sudact
```

## Конфигурация (env vars)

| Переменная | Описание | Где взять | Обязательна |
|---|---|---|---|
| `MCP_SUDACT_TOKEN` | API-ключ (заголовок `X-API-Key`) | [atomno-mcp.ru/pricing](https://atomno-mcp.ru/pricing#sudact-pro) | да |
| `MCP_SUDACT_API_BASE` | Базовый URL бэкенда | по умолчанию прод | нет |
| `MCP_SUDACT_TIMEOUT` | Таймаут HTTP, сек (default 60) | — | нет |

## Использование в Cursor (`mcp.json`)

```json
{
  "mcpServers": {
    "sudact": {
      "command": "uvx",
      "args": ["atomno-mcp-sudact"],
      "env": { "MCP_SUDACT_TOKEN": "ваш-ключ" }
    }
  }
}
```

## Использование в Claude Desktop (`claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "sudact": {
      "command": "uvx",
      "args": ["atomno-mcp-sudact"],
      "env": { "MCP_SUDACT_TOKEN": "ваш-ключ" }
    }
  }
}
```

## Тулзы

| Тул | Вход | Выход | Описание |
|---|---|---|---|
| `search_cases` | `query`, `court_type`, `instance`, `norms`, `date_from`, `date_to`, `limit` | `total_found` + список дел (`case_id`, `url`, …) | Полнотекстовый поиск как на sudact.ru |
| `get_citation` | `url` \| `case_id`, `include_full_text`, `anonymize_level` | Полный текст решения (+ опц. анонимизация) | Полный текст решения по карточке/ id |

## Disclaimer

Проект не аффилирован с sudact.ru. Данные — из открытых источников; используете на свой риск.
Полнотекстовый доступ предоставляется как hosted-сервис по подписке.

## Лицензия

MIT — см. [LICENSE](./LICENSE).
