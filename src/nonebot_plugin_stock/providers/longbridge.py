"""Longbridge OpenAPI 数据源适配。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from ..client import OpenApiException, load_sdk
from ..constants import LOCAL_TIMEZONE, MARKET_INFO, QUOTE_SOURCE_LABELS
from ..errors import StockConfigError
from .base import (
    ProviderError,
    ProviderUnavailableError,
    Quote,
    SymbolError,
)


class LongbridgeProvider:
    """把 Longbridge `SecurityQuote` 适配成统一的行情对象。"""

    key = "longbridge"
    label = QUOTE_SOURCE_LABELS[key]

    def __init__(
        self,
        get_context: Callable[[], Awaitable[Any]],
    ) -> None:
        """保存行情上下文获取函数。

        Args:
            get_context: 返回 Longbridge 异步行情上下文的协程函数。
        """
        self._get_context = get_context

    async def fetch(self, symbols: list[str]) -> tuple[list[Quote], list[SymbolError]]:
        """查询一批标的的 Longbridge 行情。"""
        if load_sdk() is None:
            raise ProviderUnavailableError("未安装 longbridge SDK")
        try:
            context = await self._get_context()
        except StockConfigError as error:
            raise ProviderUnavailableError(str(error)) from error

        try:
            raw_quotes = await context.quote(symbols)
        except OpenApiException as error:
            raise ProviderError(f"Longbridge 行情请求失败：{error}") from error
        except (OSError, RuntimeError, TimeoutError) as error:
            raise ProviderError(f"Longbridge 行情连接失败：{error}") from error

        quotes = [convert_quote(item) for item in raw_quotes]
        found = {quote.symbol for quote in quotes}
        errors = [
            SymbolError(symbol, "Longbridge 未返回该标的行情")
            for symbol in symbols
            if symbol not in found
        ]
        return quotes, errors


def convert_quote(raw: Any) -> Quote:
    """把 `SecurityQuote` 转换为统一行情对象。"""
    symbol = str(raw.symbol)
    market = symbol.rpartition(".")[2].upper()
    timestamp = raw.timestamp
    if timestamp is not None and timestamp.tzinfo is None:
        # Longbridge 的报价时间没有 tzinfo，但已经是东八区时间。
        timestamp = timestamp.replace(tzinfo=LOCAL_TIMEZONE)
    return Quote(
        symbol=symbol,
        source_key=LongbridgeProvider.key,
        source_label=LongbridgeProvider.label,
        currency=MARKET_INFO.get(market, ("", ""))[1],
        last_done=raw.last_done,
        prev_close=raw.prev_close,
        open=raw.open,
        high=raw.high,
        low=raw.low,
        volume=raw.volume,
        turnover=raw.turnover,
        trade_status=_trade_status(raw.trade_status),
        timestamp=timestamp,
    )


def _trade_status(value: object) -> str | None:
    """把交易状态枚举转换成可展示的字符串。"""
    if value is None:
        return None
    return str(getattr(value, "__name__", value)).rsplit(".", 1)[-1]
