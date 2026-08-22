"""Longbridge 配置读取和客户端缓存。"""

import asyncio
from collections.abc import Callable
from typing import Any

from longbridge.openapi import AsyncQuoteContext, Config, HttpClient

from .errors import StockConfigError


class QuoteContextState:
    """保存当前事件循环使用的行情上下文。"""

    value: AsyncQuoteContext | None = None


class HttpClientState:
    """保存调用 Longbridge 内部 HTTP 行情接口的客户端。"""

    value: HttpClient | None = None


def get_config_value(name: str, config: object) -> str | None:
    """从 NoneBot 配置对象读取并清理一个配置项。"""
    value = getattr(config, name, None)
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def build_client(
    get_value: Callable[[str], str | None],
    factory: Callable[..., Any],
) -> Any:
    """使用配置读取函数和 SDK 工厂创建 Longbridge 客户端。"""
    config_values = {
        "app_key": get_value("longbridge_app_key"),
        "app_secret": get_value("longbridge_app_secret"),
        "access_token": get_value("longbridge_access_token"),
    }
    if any(not value for value in config_values.values()):
        raise StockConfigError
    return factory(**config_values)


async def get_quote_context(
    state: QuoteContextState,
    lock: asyncio.Lock,
    build_config: Callable[[], Config],
    create: Callable[[Config, asyncio.AbstractEventLoop], AsyncQuoteContext],
) -> AsyncQuoteContext:
    """获取或创建 Longbridge 异步行情上下文。"""
    if state.value is not None:
        return state.value

    async with lock:
        if state.value is None:
            state.value = create(build_config(), asyncio.get_running_loop())
    return state.value


async def get_http_client(
    state: HttpClientState,
    lock: asyncio.Lock,
    build_client_instance: Callable[[], HttpClient],
) -> HttpClient:
    """获取或创建 Longbridge 内部 HTTP 客户端。"""
    if state.value is not None:
        return state.value

    async with lock:
        if state.value is None:
            state.value = build_client_instance()
    return state.value
