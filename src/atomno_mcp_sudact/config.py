"""Конфигурация тонкого клиента из переменных окружения.

Клиент stateless: вся логика на бэкенде. Настройки:
    MCP_SUDACT_API_BASE  — базовый URL hosted-бэкенда (default: публичный прод).
    MCP_SUDACT_TOKEN     — API-ключ (заголовок X-API-Key). Без него — 401 на защищённых.
    MCP_SUDACT_TIMEOUT   — таймаут HTTP в секундах (default 60).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_API_BASE = "https://api.atomno-mcp.ru/sudact"
DEFAULT_TIMEOUT = 60.0


@dataclass(frozen=True)
class Settings:
    api_base: str
    token: str | None
    timeout: float

    @classmethod
    def from_env(cls) -> Settings:
        base = (os.environ.get("MCP_SUDACT_API_BASE") or DEFAULT_API_BASE).rstrip("/")
        token = os.environ.get("MCP_SUDACT_TOKEN") or None
        try:
            timeout = float(os.environ.get("MCP_SUDACT_TIMEOUT") or DEFAULT_TIMEOUT)
        except ValueError:
            timeout = DEFAULT_TIMEOUT
        return cls(api_base=base, token=token, timeout=timeout)

    @property
    def has_token(self) -> bool:
        return bool(self.token)
