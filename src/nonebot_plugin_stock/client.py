"""Longbridge SDK 边界、配置读取和客户端缓存。"""

import asyncio
from collections.abc import Callable
from functools import lru_cache
from importlib import import_module
from types import ModuleType
from typing import Any

from nonebot.log import logger

from .errors import StockConfigError, StockSdkMissingError


class QuoteContextState:
    """保存当前事件循环使用的行情上下文。"""

    value: Any = None


class HttpClientState:
    """保存调用 Longbridge 内部 HTTP 行情接口的客户端。"""

    value: Any = None


@lru_cache(maxsize=1)
def load_sdk() -> ModuleType | None:
    """返回 longbridge SDK 模块，未安装时返回 None（只探测一次）。"""
    try:
        return import_module("longbridge.openapi")
    except ImportError:
        logger.info("未安装 longbridge SDK，Longbridge 数据源与榜单不可用")
        return None


def require_sdk() -> ModuleType:
    """返回 longbridge SDK 模块，未安装时抛出异常。

    Raises:
        StockSdkMissingError: SDK 未安装。
    """
    sdk = load_sdk()
    if sdk is None:
        raise StockSdkMissingError
    return sdk


class MissingSdkError(Exception):
    """SDK 缺失时的占位异常，不会被真正抛出。"""


def _openapi_exception() -> type[Exception]:
    """返回 SDK 的 `OpenApiException`，SDK 缺失时返回占位异常。"""
    sdk = load_sdk()
    return getattr(sdk, "OpenApiException", MissingSdkError) if sdk else MissingSdkError


# 命令处理层用它写 except 子句：SDK 可用时是真异常，缺失时永远不会命中。
OpenApiException: type[Exception] = _openapi_exception()


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
    build_config: Callable[[], Any],
    create: Callable[[Any, asyncio.AbstractEventLoop], Any],
) -> Any:
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
    build_client_instance: Callable[[], Any],
) -> Any:
    """获取或创建 Longbridge 内部 HTTP 客户端。"""
    if state.value is not None:
        return state.value

    async with lock:
        if state.value is None:
            state.value = build_client_instance()
    return state.value
