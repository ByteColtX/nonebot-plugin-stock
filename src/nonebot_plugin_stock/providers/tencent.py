"""腾讯行情数据源（qt.gtimg.cn，免凭证）。"""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal

import httpx

from ..constants import MARKET_INFO, QUOTE_SOURCE_LABELS
from .base import (
    Quote,
    SymbolError,
    market_code,
    parse_decimal,
    parse_int,
    parse_timestamp,
)
from .http import DEFAULT_TIMEOUT, get_text

QUOTE_URL = "https://qt.gtimg.cn/q={codes}"
LINE_PATTERN = re.compile(r'v_([\w.\-]+)="([^"]*)";')
MARKET_PREFIXES = {"US": "us", "HK": "hk", "SH": "sh", "SZ": "sz", "BJ": "bj"}
DOMESTIC_MARKETS = frozenset({"SH", "SZ", "BJ"})
US_HK_TIMESTAMP_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S")
DOMESTIC_TIMESTAMP_FORMAT = "%Y%m%d%H%M%S"
INDEX_LAST_DONE = 3
INDEX_PREV_CLOSE = 4
INDEX_OPEN = 5
INDEX_TIMESTAMP = 30
INDEX_HIGH = 33
INDEX_LOW = 34
INDEX_CURRENCY = 35
INDEX_VOLUME = 36
INDEX_TURNOVER = 37
INDEX_FIELDS_MIN = 38
DOMESTIC_DETAIL = 35
DOMESTIC_DETAIL_PARTS = 3
LOT_SIZE = 100
WAN_UNIT = 10_000


def quote_code(symbol: str) -> str | None:
    """将标准标的转换为腾讯行情接口使用的代码。"""
    code, _, market = symbol.rpartition(".")
    if not code or not market:
        return None
    prefix = MARKET_PREFIXES.get(market)
    if prefix is None:
        return None
    if market == "HK":
        code = code.zfill(5)
    return f"{prefix}{code}"


def parse_quote(symbol: str, body: str) -> Quote | None:
    """解析腾讯行情返回的单条行情文本。"""
    if not body:
        return None
    fields = body.split("~")
    if len(fields) < INDEX_FIELDS_MIN:
        return None

    market = market_code(symbol)
    volume, turnover = _size_fields(fields, market)
    return Quote(
        symbol=symbol,
        source_key=TencentProvider.key,
        source_label=TencentProvider.label,
        currency=_currency(fields, market),
        last_done=parse_decimal(fields[INDEX_LAST_DONE]),
        prev_close=parse_decimal(fields[INDEX_PREV_CLOSE]),
        open=parse_decimal(fields[INDEX_OPEN]),
        high=parse_decimal(fields[INDEX_HIGH]),
        low=parse_decimal(fields[INDEX_LOW]),
        volume=volume,
        turnover=turnover,
        trade_status=None,
        timestamp=_timestamp(fields, market),
    )


def _size_fields(fields: list[str], market: str) -> tuple[int | None, Decimal | None]:
    """按市场口径归一化成交量和成交额。"""
    if market in DOMESTIC_MARKETS:
        detail = fields[DOMESTIC_DETAIL].split("/")
        if len(detail) >= DOMESTIC_DETAIL_PARTS:
            lots = parse_int(detail[1])
            volume = lots * LOT_SIZE if lots is not None else None
            return volume, parse_decimal(detail[2])
        lots = parse_int(fields[INDEX_VOLUME])
        volume = lots * LOT_SIZE if lots is not None else None
        turnover = parse_decimal(fields[INDEX_TURNOVER])
        if turnover is not None:
            turnover = turnover * WAN_UNIT
        return volume, turnover

    return parse_int(fields[INDEX_VOLUME]), parse_decimal(fields[INDEX_TURNOVER])


def _currency(fields: list[str], market: str) -> str:
    """优先取接口返回的货币，否则按市场推断。"""
    if market == "US":
        reported = fields[INDEX_CURRENCY].strip().upper()
        if len(reported) == 3 and reported.isalpha():
            return reported
    return MARKET_INFO.get(market, ("", ""))[1]


def _timestamp(fields: list[str], market: str) -> datetime | None:
    """按市场格式解析行情时间。"""
    if market in DOMESTIC_MARKETS:
        return parse_timestamp(fields[INDEX_TIMESTAMP], DOMESTIC_TIMESTAMP_FORMAT)
    return parse_timestamp(fields[INDEX_TIMESTAMP], *US_HK_TIMESTAMP_FORMATS)


class TencentProvider:
    """腾讯行情数据源，覆盖美、港、A 股。"""

    key = "tencent"
    label = QUOTE_SOURCE_LABELS[key]

    def __init__(
        self,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        """保存请求参数。

        Args:
            timeout: 请求超时秒数。
            transport: 自定义传输层，测试时注入 MockTransport。
        """
        self._timeout = timeout
        self._transport = transport

    async def fetch(self, symbols: list[str]) -> tuple[list[Quote], list[SymbolError]]:
        """查询一批标的的腾讯行情。"""
        codes: dict[str, str] = {}
        errors: list[SymbolError] = []
        for symbol in symbols:
            code = quote_code(symbol)
            if code is None:
                errors.append(SymbolError(symbol, "腾讯行情不支持该市场或标的格式"))
            else:
                codes[code] = symbol
        if not codes:
            return [], errors

        text = await get_text(
            QUOTE_URL.format(codes=",".join(codes)),
            timeout=self._timeout,
            transport=self._transport,
        )
        rows = dict(LINE_PATTERN.findall(text))
        quotes: list[Quote] = []
        for code, symbol in codes.items():
            quote = parse_quote(symbol, rows.get(code, ""))
            if quote is None:
                errors.append(SymbolError(symbol, "腾讯行情未返回该标的"))
            else:
                quotes.append(quote)
        return quotes, errors
