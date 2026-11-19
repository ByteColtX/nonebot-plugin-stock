"""Longbridge SDK 边界、配置读取和客户端缓存。"""

import asyncio
from collections.abc import Awaitable, Callable
from functools import lru_cache
from importlib import import_module
from types import ModuleType
from typing import Any

from nonebot.log import logger

from .constants import DEFAULT_OAUTH_CALLBACK_PORT, MAX_PORT, MIN_PORT
from .errors import StockConfigError, StockSdkMissingError

AUTH_METHOD_APIKEY = "apikey"
AUTH_METHOD_OAUTH = "oauth"
AUTH_METHOD_ALIASES = {
    "apikey": AUTH_METHOD_APIKEY,
    "api_key": AUTH_METHOD_APIKEY,
    "key": AUTH_METHOD_APIKEY,
    "oauth": AUTH_METHOD_OAUTH,
    "oauth2": AUTH_METHOD_OAUTH,
    "oauth2.0": AUTH_METHOD_OAUTH,
}


class QuoteContextState:
    """保存当前事件循环使用的行情上下文。"""

    value: Any = None


class HttpClientState:
    """保存调用 Longbridge 内部 HTTP 行情接口的客户端。"""

    value: Any = None


class OAuthState:
    """保存配置与 HTTP 客户端共享的 OAuth 授权句柄。"""

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


def auth_method(get_value: Callable[[str], str | None]) -> str:
    """确定 Longbridge 认证方式。

    显式配置 `LONGBRIDGE_AUTH_METHOD` 时以配置为准；否则自动选择：
    配置了 `LONGBRIDGE_OAUTH_CLIENT_ID` 时优先 OAuth 2.0，
    没有 OAuth 配置时回退到传统 API Key。

    Args:
        get_value: 按配置项名称读取并清理文本的函数。

    Returns:
        `apikey` 或 `oauth`。

    Raises:
        StockConfigError: 显式配置了无法识别的认证方式。
    """
    raw = get_value("longbridge_auth_method")
    if raw is None:
        if get_value("longbridge_oauth_client_id") is not None:
            return AUTH_METHOD_OAUTH
        return AUTH_METHOD_APIKEY
    method = AUTH_METHOD_ALIASES.get(raw.casefold())
    if method is None:
        raise StockConfigError.invalid_auth_method(raw)
    return method


def oauth_client_id(get_value: Callable[[str], str | None]) -> str | None:
    """读取 OAuth 2.0 客户端 ID。"""
    return get_value("longbridge_oauth_client_id")


def oauth_callback_port(get_value: Callable[[str], str | None]) -> int:
    """读取 OAuth 回调端口，非法值回退到默认端口。

    Args:
        get_value: 按配置项名称读取并清理文本的函数。

    Returns:
        `redirect_uri` 中登记的本地回调端口。
    """
    raw = get_value("longbridge_oauth_callback_port")
    if raw is None:
        return DEFAULT_OAUTH_CALLBACK_PORT
    try:
        port = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_OAUTH_CALLBACK_PORT
    return min(max(port, MIN_PORT), MAX_PORT)


async def get_quote_context(
    state: QuoteContextState,
    lock: asyncio.Lock,
    build_config: Callable[[], Awaitable[Any]],
    create: Callable[[Any, asyncio.AbstractEventLoop], Any],
) -> Any:
    """获取或创建 Longbridge 异步行情上下文。

    配置可能需要在首次使用时完成 OAuth 授权，因此构建函数是异步的。
    """
    if state.value is not None:
        return state.value

    async with lock:
        if state.value is None:
            config = await build_config()
            state.value = create(config, asyncio.get_running_loop())
    return state.value


async def get_http_client(
    state: HttpClientState,
    lock: asyncio.Lock,
    build_client_instance: Callable[[], Awaitable[Any]],
) -> Any:
    """获取或创建 Longbridge 内部 HTTP 客户端。"""
    if state.value is not None:
        return state.value

    async with lock:
        if state.value is None:
            state.value = await build_client_instance()
    return state.value


async def get_oauth(
    state: OAuthState,
    lock: asyncio.Lock,
    authorize: Callable[[], Awaitable[Any]],
) -> Any:
    """获取或创建 OAuth 授权句柄。

    授权句柄同时提供给 `Config` 和 `HttpClient`，因此单独缓存并复用；
    首次授权需要等待浏览器回调，后续启动会直接复用 SDK 缓存的令牌。
    """
    if state.value is not None:
        return state.value

    async with lock:
        if state.value is None:
            state.value = await authorize()
    return state.value
