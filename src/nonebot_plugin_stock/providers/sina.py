"""新浪行情数据源（hq.sinajs.cn，免凭证，需要 Referer）。"""

from __future__ import annotations

import re

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

QUOTE_URL = "https://hq.sinajs.cn/list={codes}"
REQUEST_HEADERS = {"Referer": "https://finance.sina.com.cn"}
LINE_PATTERN = re.compile(r'var hq_str_([\w.\-]+)="([^"]*)";')
DOMESTIC_MARKETS = frozenset({"SH", "SZ", "BJ"})
US_TIMESTAMP_FORMATS = ("%Y-%m-%d %H:%M:%S",)
HK_TIMESTAMP_FORMAT = "%Y/%m/%d %H:%M:%S"
DOMESTIC_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
US_FIELDS_MIN = 31
US_LAST_DONE = 1
US_TIMESTAMP = 3
US_OPEN = 5
US_HIGH = 6
US_LOW = 7
US_VOLUME = 10
US_PREV_CLOSE = 26
US_TURNOVER = 30
HK_FIELDS_MIN = 19
HK_OPEN = 2
HK_PREV_CLOSE = 3
HK_HIGH = 4
HK_LOW = 5
HK_LAST_DONE = 6
HK_TURNOVER = 11
HK_VOLUME = 12
HK_DATE = 17
HK_TIME = 18
DOMESTIC_FIELDS_MIN = 32
DOMESTIC_OPEN = 1
DOMESTIC_PREV_CLOSE = 2
DOMESTIC_LAST_DONE = 3
DOMESTIC_HIGH = 4
DOMESTIC_LOW = 5
DOMESTIC_VOLUME = 8
DOMESTIC_TURNOVER = 9
DOMESTIC_DATE = 30
DOMESTIC_TIME = 31


def quote_code(symbol: str) -> str | None:
    """将标准标的转换为新浪行情接口使用的代码。"""
    code, _, market = symbol.rpartition(".")
    if not code or not market:
        return None
    if market == "US":
        # 新浪不提供 BRK.B 这类带分隔符的美股代码。
        if "." in code or "-" in code:
            return None
        return f"gb_{code.lower()}"
    if market == "HK":
        return f"rt_hk{code.zfill(5)}"
    if market in DOMESTIC_MARKETS:
        return f"{market.lower()}{code}"
    return None


def parse_quote(symbol: str, body: str) -> Quote | None:
    """解析新浪行情返回的单条行情文本。"""
    if not body:
        return None
    fields = body.split(",")
    market = market_code(symbol)
    if market == "US":
        return _parse_us(symbol, fields)
    if market == "HK":
        return _parse_hk(symbol, fields)
    if market in DOMESTIC_MARKETS:
        return _parse_domestic(symbol, fields)
    return None


def _currency(market: str) -> str:
    """按市场推断计价货币。"""
    return MARKET_INFO.get(market, ("", ""))[1]


def _parse_us(symbol: str, fields: list[str]) -> Quote | None:
    """解析新浪美股行情。"""
    if len(fields) < US_FIELDS_MIN:
        return None
    return Quote(
        symbol=symbol,
        source_key=SinaProvider.key,
        source_label=SinaProvider.label,
        currency=_currency("US"),
        last_done=parse_decimal(fields[US_LAST_DONE]),
        prev_close=parse_decimal(fields[US_PREV_CLOSE]),
        open=parse_decimal(fields[US_OPEN]),
        high=parse_decimal(fields[US_HIGH]),
        low=parse_decimal(fields[US_LOW]),
        volume=parse_int(fields[US_VOLUME]),
        turnover=parse_decimal(fields[US_TURNOVER]),
        timestamp=parse_timestamp(fields[US_TIMESTAMP], *US_TIMESTAMP_FORMATS),
    )


def _parse_hk(symbol: str, fields: list[str]) -> Quote | None:
    """解析新浪港股行情。"""
    if len(fields) < HK_FIELDS_MIN:
        return None
    return Quote(
        symbol=symbol,
        source_key=SinaProvider.key,
        source_label=SinaProvider.label,
        currency=_currency("HK"),
        last_done=parse_decimal(fields[HK_LAST_DONE]),
        prev_close=parse_decimal(fields[HK_PREV_CLOSE]),
        open=parse_decimal(fields[HK_OPEN]),
        high=parse_decimal(fields[HK_HIGH]),
        low=parse_decimal(fields[HK_LOW]),
        volume=parse_int(fields[HK_VOLUME]),
        turnover=parse_decimal(fields[HK_TURNOVER]),
        timestamp=parse_timestamp(
            f"{fields[HK_DATE]} {fields[HK_TIME]}", HK_TIMESTAMP_FORMAT
        ),
    )


def _parse_domestic(symbol: str, fields: list[str]) -> Quote | None:
    """解析新浪 A 股行情。"""
    if len(fields) < DOMESTIC_FIELDS_MIN:
        return None
    market = market_code(symbol)
    return Quote(
        symbol=symbol,
        source_key=SinaProvider.key,
        source_label=SinaProvider.label,
        currency=_currency(market),
        last_done=parse_decimal(fields[DOMESTIC_LAST_DONE]),
        prev_close=parse_decimal(fields[DOMESTIC_PREV_CLOSE]),
        open=parse_decimal(fields[DOMESTIC_OPEN]),
        high=parse_decimal(fields[DOMESTIC_HIGH]),
        low=parse_decimal(fields[DOMESTIC_LOW]),
        volume=parse_int(fields[DOMESTIC_VOLUME]),
        turnover=parse_decimal(fields[DOMESTIC_TURNOVER]),
        timestamp=parse_timestamp(
            f"{fields[DOMESTIC_DATE]} {fields[DOMESTIC_TIME]}",
            DOMESTIC_TIMESTAMP_FORMAT,
        ),
    )


class SinaProvider:
    """新浪行情数据源，覆盖美、港、A 股。"""

    key = "sina"
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
        """查询一批标的的新浪行情。"""
        codes: dict[str, str] = {}
        errors: list[SymbolError] = []
        for symbol in symbols:
            code = quote_code(symbol)
            if code is None:
                errors.append(SymbolError(symbol, "新浪行情不支持该市场或标的格式"))
            else:
                codes[code] = symbol
        if not codes:
            return [], errors

        text = await get_text(
            QUOTE_URL.format(codes=",".join(codes)),
            headers=REQUEST_HEADERS,
            timeout=self._timeout,
            transport=self._transport,
        )
        rows = dict(LINE_PATTERN.findall(text))
        quotes: list[Quote] = []
        for code, symbol in codes.items():
            quote = parse_quote(symbol, rows.get(code, ""))
            if quote is None:
                errors.append(SymbolError(symbol, "新浪行情未返回该标的"))
            else:
                quotes.append(quote)
        return quotes, errors
