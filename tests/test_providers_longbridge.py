from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from longbridge.openapi import OpenApiException

from nonebot_plugin_stock.errors import StockConfigError
from nonebot_plugin_stock.providers import base
from nonebot_plugin_stock.providers.longbridge import LongbridgeProvider, convert_quote
from nonebot_plugin_stock.providers.registry import build_providers


def make_security_quote(**overrides: object) -> SimpleNamespace:
    values = {
        "symbol": "AAPL.US",
        "last_done": "195.25",
        "prev_close": "190.00",
        "open": "191",
        "high": "196.5",
        "low": "189.75",
        "volume": 1234567,
        "turnover": "987654.3",
        "trade_status": SimpleNamespace(__name__="Normal"),
        "timestamp": datetime(2026, 8, 22, 9, 30, 1),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_convert_quote_normalizes_status_and_timezone() -> None:
    quote = convert_quote(make_security_quote())

    assert quote.symbol == "AAPL.US"
    assert quote.source_key == "longbridge"
    assert quote.source_label == base.SOURCE_LABELS["longbridge"]
    assert quote.currency == "USD"
    assert quote.trade_status == "Normal"
    assert quote.timestamp == datetime(
        2026, 8, 22, 9, 30, 1, tzinfo=ZoneInfo("Asia/Shanghai")
    )


def test_convert_quote_handles_missing_status_and_timestamp() -> None:
    quote = convert_quote(make_security_quote(trade_status=None, timestamp=None))

    assert quote.trade_status is None
    assert quote.timestamp is None


@pytest.mark.asyncio
async def test_fetch_returns_quotes_and_reports_missing_symbols() -> None:
    async def quote(_symbols: list[str]) -> list[SimpleNamespace]:
        return [make_security_quote()]

    async def get_context() -> SimpleNamespace:
        return SimpleNamespace(quote=quote)

    provider = LongbridgeProvider(get_context)
    quotes, errors = await provider.fetch(["AAPL.US", "TSLA.US"])

    assert [item.symbol for item in quotes] == ["AAPL.US"]
    assert [(error.symbol, error.reason) for error in errors] == [
        ("TSLA.US", "Longbridge 未返回该标的行情")
    ]


@pytest.mark.asyncio
async def test_fetch_skips_when_credentials_are_missing() -> None:
    async def get_context() -> SimpleNamespace:
        raise StockConfigError

    provider = LongbridgeProvider(get_context)

    with pytest.raises(base.ProviderUnavailableError, match="未配置 Longbridge 凭证"):
        await provider.fetch(["AAPL.US"])


@pytest.mark.asyncio
async def test_fetch_wraps_openapi_errors() -> None:
    async def quote(_symbols: list[str]) -> list[SimpleNamespace]:
        raise OpenApiException("quote", 1, "trace-id", "boom")

    async def get_context() -> SimpleNamespace:
        return SimpleNamespace(quote=quote)

    provider = LongbridgeProvider(get_context)

    with pytest.raises(base.ProviderError, match="Longbridge 行情请求失败"):
        await provider.fetch(["AAPL.US"])


def test_build_providers_keeps_order_and_deduplicates() -> None:
    async def get_context() -> None:
        return None

    providers = build_providers(
        ["tencent", "sina", "tencent"],
        timeout=3.0,
        get_longbridge_context=get_context,
    )

    assert [provider.key for provider in providers] == ["tencent", "sina"]


def test_build_providers_supports_longbridge() -> None:
    async def get_context() -> None:
        return None

    providers = build_providers(
        ["longbridge", "tencent"],
        timeout=3.0,
        get_longbridge_context=get_context,
    )

    assert [provider.key for provider in providers] == ["longbridge", "tencent"]
