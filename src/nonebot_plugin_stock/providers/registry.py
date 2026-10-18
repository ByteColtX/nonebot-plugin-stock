"""数据源注册表与 fallback 链路。"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from nonebot.log import logger

from ..constants import QUOTE_SOURCE_KEYS
from ..errors import StockSourceConfigError, StockSourceError
from .base import (
    ProviderError,
    ProviderUnavailableError,
    Quote,
    QuoteProvider,
    SymbolError,
)
from .longbridge import LongbridgeProvider
from .sina import SinaProvider
from .tencent import TencentProvider


@dataclass(frozen=True)
class QuoteResult:
    """一次成功的行情查询结果。

    Attributes:
        quotes: 已取到的行情，全部来自同一个数据源。
        symbol_errors: 该数据源取不到的标的及原因。
        provider_key: 实际提供数据的数据源键。
        provider_label: 实际提供数据的数据源名称。
    """

    quotes: list[Quote]
    symbol_errors: list[SymbolError]
    provider_key: str
    provider_label: str


def build_providers(
    keys: list[str],
    *,
    timeout: float,
    get_longbridge_context: Callable[[], Awaitable[Any]],
) -> list[QuoteProvider]:
    """按优先级构建数据源链路。

    Args:
        keys: 数据源键列表，第一个为主源。
        timeout: 单个数据源的超时秒数。
        get_longbridge_context: Longbridge 行情上下文获取函数。

    Returns:
        数据源实例列表，顺序与 `keys` 一致且已去重。

    Raises:
        StockSourceConfigError: 列表为空或包含未知数据源。
    """
    if not keys:
        raise StockSourceConfigError.empty()

    unknown = [key for key in keys if key not in QUOTE_SOURCE_KEYS]
    if unknown:
        raise StockSourceConfigError.unknown(unknown)

    providers: list[QuoteProvider] = []
    for key in dict.fromkeys(keys):
        if key == "longbridge":
            providers.append(LongbridgeProvider(get_longbridge_context))
        elif key == "tencent":
            providers.append(TencentProvider(timeout=timeout))
        else:
            providers.append(SinaProvider(timeout=timeout))
    return providers


async def fetch_quotes(
    providers: list[QuoteProvider],
    symbols: list[str],
    *,
    timeout: float,
) -> QuoteResult:
    """按优先级依次尝试数据源，返回第一个成功的结果。

    Args:
        providers: 数据源链路。
        symbols: 归一化的 `CODE.MARKET` 标的列表。
        timeout: 单个数据源的超时秒数。

    Returns:
        成功数据源返回的行情结果。

    Raises:
        StockSourceError: 所有数据源都不可用。
    """
    attempted: list[str] = []
    symbol_errors: dict[str, str] = {}

    for provider in providers:
        attempted.append(provider.label)
        try:
            quotes, errors = await asyncio.wait_for(
                provider.fetch(symbols), timeout=timeout
            )
        except ProviderUnavailableError as error:
            logger.warning(f"跳过行情数据源 {provider.label}：{error}")
            continue
        except ProviderError as error:
            logger.warning(f"行情数据源 {provider.label} 不可用：{error}")
            continue
        except asyncio.TimeoutError:
            logger.warning(f"行情数据源 {provider.label} 超时（{timeout} 秒）")
            continue
        except Exception as error:
            logger.warning(
                f"行情数据源 {provider.label} 处理失败：{error}", exc_info=True
            )
            continue

        for item in errors:
            symbol_errors.setdefault(item.symbol, item.reason)
        if not quotes:
            logger.warning(f"行情数据源 {provider.label} 未返回可用行情")
            continue

        if len(attempted) > 1:
            logger.info(f"行情数据源已降级到 {provider.label}")
        return QuoteResult(
            quotes=quotes,
            symbol_errors=errors,
            provider_key=provider.key,
            provider_label=provider.label,
        )

    raise StockSourceError(
        attempted,
        tuple(SymbolError(symbol, reason) for symbol, reason in symbol_errors.items()),
    )
