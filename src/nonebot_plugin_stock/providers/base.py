"""行情数据源的公共契约：领域数据类、协议与异常。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, DecimalException
from typing import Protocol

from ..constants import LOCAL_TIMEZONE, QUOTE_SOURCE_LABELS

SOURCE_LABELS = QUOTE_SOURCE_LABELS


@dataclass(frozen=True)
class Quote:
    """归一化后的单个标的行情快照。

    Attributes:
        symbol: 归一化的 `CODE.MARKET` 标的代码。
        source_key: 数据源键，如 `tencent`。
        source_label: 展示给用户的数据源名称。
        currency: 计价货币代码，未知时为空字符串。
        last_done: 最新价。
        prev_close: 昨收价。
        open: 开盘价。
        high: 最高价。
        low: 最低价。
        volume: 成交量，统一为「股」。
        turnover: 成交额，统一为计价货币金额。
        trade_status: 交易状态；免费源不提供时为 None。
        timestamp: 行情时间，带时区。
    """

    symbol: str
    source_key: str
    source_label: str
    currency: str = ""
    last_done: Decimal | None = None
    prev_close: Decimal | None = None
    open: Decimal | None = None
    high: Decimal | None = None
    low: Decimal | None = None
    volume: int | None = None
    turnover: Decimal | None = None
    trade_status: str | None = None
    timestamp: datetime | None = None


@dataclass(frozen=True)
class SymbolError:
    """单个标的在当前数据源上取不到行情的原因。"""

    symbol: str
    reason: str


class ProviderError(RuntimeError):
    """数据源整体不可用（网络、HTTP、整包解析或超时）。"""


class ProviderUnavailableError(ProviderError):
    """数据源未配置，应在链路中被跳过。"""


class QuoteProvider(Protocol):
    """行情数据源协议。"""

    key: str
    label: str

    async def fetch(self, symbols: list[str]) -> tuple[list[Quote], list[SymbolError]]:
        """查询一批标的的行情。

        Args:
            symbols: 归一化的 `CODE.MARKET` 标的列表。

        Returns:
            已取到的行情和逐标的的失败原因。

        Raises:
            ProviderError: 数据源整体不可用。
        """
        ...


def market_code(symbol: str) -> str:
    """返回标的代码中的市场后缀。"""
    return symbol.rpartition(".")[2].upper()


def parse_decimal(value: object) -> Decimal | None:
    """将数据源返回的文本数值解析为 Decimal。"""
    if value is None:
        return None
    text = str(value).strip()
    if not text or text in {"-", "--"}:
        return None
    try:
        return Decimal(text)
    except (DecimalException, ValueError):
        return None


def parse_int(value: object) -> int | None:
    """将数据源返回的文本数值解析为整数。"""
    number = parse_decimal(value)
    if number is None:
        return None
    try:
        return int(number)
    except (OverflowError, ValueError):
        return None


def parse_timestamp(value: object, *formats: str) -> datetime | None:
    """按给定格式解析行情时间，并补齐东八区时区。"""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=LOCAL_TIMEZONE)
        except ValueError:
            continue
    return None
