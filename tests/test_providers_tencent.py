from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import httpx
import pytest

from nonebot_plugin_stock.providers.base import ProviderError
from nonebot_plugin_stock.providers.tencent import (
    TencentProvider,
    parse_quote,
    quote_code,
)


def build_us_body() -> str:
    values = [""] * 40
    values[0] = "200"
    values[1] = "苹果"
    values[2] = "AAPL.OQ"
    values[3] = "343.46"
    values[4] = "342.00"
    values[5] = "346.09"
    values[30] = "2026-10-16 16:00:02"
    values[31] = "1.46"
    values[32] = "0.43"
    values[33] = "347.82"
    values[34] = "340.46"
    values[35] = "USD"
    values[36] = "59946368"
    values[37] = "20621913459"
    return "~".join(values)


def build_hk_body() -> str:
    values = [""] * 40
    values[0] = "100"
    values[1] = "腾讯控股"
    values[2] = "00700"
    values[3] = "417.800"
    values[4] = "417.800"
    values[5] = "424.000"
    values[30] = "2026/10/16 16:08:22"
    values[31] = "0.000"
    values[32] = "0.00"
    values[33] = "428.800"
    values[34] = "415.800"
    values[35] = "417.800"
    values[36] = "18752869.0"
    values[37] = "7901198756.124"
    return "~".join(values)


def build_domestic_body() -> str:
    values = [""] * 40
    values[0] = "1"
    values[1] = "贵州茅台"
    values[2] = "600519"
    values[3] = "1329.00"
    values[4] = "1312.97"
    values[5] = "1311.57"
    values[30] = "20261016161447"
    values[31] = "16.03"
    values[32] = "1.22"
    values[33] = "1329.88"
    values[34] = "1301.68"
    values[35] = "1329.00/38502/5075528306"
    values[36] = "38502"
    values[37] = "507553"
    return "~".join(values)


def request_codes(request: httpx.Request) -> list[str]:
    """腾讯接口把代码写在路径里（/q=usAAPL,hk00700）。"""
    path = request.url.path
    if "q=" not in path:
        return []
    return [code for code in path.split("q=", 1)[1].split(",") if code]


def make_transport(
    payload: dict[str, str], calls: list[httpx.Request] | None = None
) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(request)
        codes = request_codes(request)
        body = "\n".join(
            f'v_{code}="{payload.get(code, "")}";' for code in codes if code
        )
        return httpx.Response(200, content=body.encode("gbk"))

    return httpx.MockTransport(handler)


def test_quote_code_maps_each_market() -> None:
    assert quote_code("AAPL.US") == "usAAPL"
    assert quote_code("BRK.B.US") == "usBRK.B"
    assert quote_code("700.HK") == "hk00700"
    assert quote_code("600519.SH") == "sh600519"
    assert quote_code("000568.SZ") == "sz000568"
    assert quote_code("430047.BJ") == "bj430047"
    assert quote_code("700.SG") is None
    assert quote_code("AAPL") is None


def test_parse_us_quote_uses_reported_currency() -> None:
    quote = parse_quote("AAPL.US", build_us_body())

    assert quote is not None
    assert quote.source_key == "tencent"
    assert quote.currency == "USD"
    assert quote.last_done == Decimal("343.46")
    assert quote.prev_close == Decimal("342.00")
    assert quote.open == Decimal("346.09")
    assert quote.high == Decimal("347.82")
    assert quote.low == Decimal("340.46")
    assert quote.volume == 59946368
    assert quote.turnover == Decimal("20621913459")
    assert quote.trade_status is None
    assert quote.timestamp == datetime(
        2026, 10, 16, 16, 0, 2, tzinfo=ZoneInfo("Asia/Shanghai")
    )


def test_parse_hk_quote_normalizes_units_and_timestamp() -> None:
    quote = parse_quote("700.HK", build_hk_body())

    assert quote is not None
    assert quote.currency == "HKD"
    assert quote.last_done == Decimal("417.800")
    assert quote.volume == 18752869
    assert quote.turnover == Decimal("7901198756.124")
    assert quote.timestamp == datetime(
        2026, 10, 16, 16, 8, 22, tzinfo=ZoneInfo("Asia/Shanghai")
    )


def test_parse_domestic_quote_converts_lots_and_wan() -> None:
    quote = parse_quote("600519.SH", build_domestic_body())

    assert quote is not None
    assert quote.currency == "CNY"
    assert quote.volume == 3850200
    assert quote.turnover == Decimal("5075528306")
    assert quote.timestamp == datetime(
        2026, 10, 16, 16, 14, 47, tzinfo=ZoneInfo("Asia/Shanghai")
    )


def test_parse_quote_rejects_short_or_empty_body() -> None:
    assert parse_quote("AAPL.US", "") is None
    assert parse_quote("AAPL.US", "200~苹果~AAPL.OQ~343.46") is None


@pytest.mark.asyncio
async def test_fetch_returns_quotes_and_symbol_errors() -> None:
    calls: list[httpx.Request] = []
    provider = TencentProvider(
        transport=make_transport(
            {"usAAPL": build_us_body(), "hk00700": build_hk_body()}, calls
        )
    )

    quotes, errors = await provider.fetch(["AAPL.US", "700.HK", "700.SG"])

    assert [quote.symbol for quote in quotes] == ["AAPL.US", "700.HK"]
    assert [(error.symbol, error.reason) for error in errors] == [
        ("700.SG", "腾讯行情不支持该市场或标的格式")
    ]
    assert request_codes(calls[0]) == ["usAAPL", "hk00700"]


@pytest.mark.asyncio
async def test_fetch_reports_missing_symbols() -> None:
    provider = TencentProvider(transport=make_transport({}))

    quotes, errors = await provider.fetch(["AAPL.US"])

    assert quotes == []
    assert [(error.symbol, error.reason) for error in errors] == [
        ("AAPL.US", "腾讯行情未返回该标的")
    ]


@pytest.mark.asyncio
async def test_fetch_skips_request_when_no_symbol_is_supported() -> None:
    calls: list[httpx.Request] = []
    provider = TencentProvider(transport=make_transport({}, calls))

    quotes, errors = await provider.fetch(["700.SG"])

    assert quotes == []
    assert len(errors) == 1
    assert calls == []


@pytest.mark.asyncio
async def test_fetch_wraps_http_errors() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    provider = TencentProvider(transport=httpx.MockTransport(handler))

    with pytest.raises(ProviderError, match="请求失败"):
        await provider.fetch(["AAPL.US"])
