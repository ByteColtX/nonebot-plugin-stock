from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import httpx
import pytest

from nonebot_plugin_stock.providers.base import ProviderError
from nonebot_plugin_stock.providers.sina import (
    SinaProvider,
    parse_quote,
    quote_code,
)


def build_us_body() -> str:
    values = [""] * 36
    values[0] = "苹果"
    values[1] = "343.4600"
    values[2] = "0.43"
    values[3] = "2026-10-17 07:59:51"
    values[4] = "1.4600"
    values[5] = "346.0850"
    values[6] = "347.8200"
    values[7] = "340.4600"
    values[10] = "59946368"
    values[26] = "342.0000"
    values[30] = "20629491159.0000"
    return ",".join(values)


def build_hk_body() -> str:
    values = [""] * 25
    values[0] = "TENCENT"
    values[1] = "腾讯控股"
    values[2] = "424.000"
    values[3] = "417.800"
    values[4] = "428.800"
    values[5] = "415.800"
    values[6] = "417.800"
    values[7] = "-0.000"
    values[8] = "-0.000"
    values[11] = "7901198756.124"
    values[12] = "18752869"
    values[17] = "2026/10/16"
    values[18] = "16:08:22"
    return ",".join(values)


def build_domestic_body() -> str:
    values = [""] * 34
    values[0] = "贵州茅台"
    values[1] = "1311.570"
    values[2] = "1312.970"
    values[3] = "1329.000"
    values[4] = "1329.880"
    values[5] = "1301.680"
    values[8] = "3850175"
    values[9] = "5075528306.000"
    values[30] = "2026-10-16"
    values[31] = "15:34:59"
    return ",".join(values)


def request_codes(request: httpx.Request) -> list[str]:
    """新浪接口把代码写在路径里（/list=gb_aapl,rt_hk00700）。"""
    path = request.url.path
    if "list=" not in path:
        return []
    return [code for code in path.split("list=", 1)[1].split(",") if code]


def make_transport(
    payload: dict[str, str], calls: list[httpx.Request] | None = None
) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(request)
        codes = request_codes(request)
        body = "\n".join(
            f'var hq_str_{code}="{payload.get(code, "")}";' for code in codes if code
        )
        return httpx.Response(200, content=body.encode("gbk"))

    return httpx.MockTransport(handler)


def test_quote_code_maps_each_market() -> None:
    assert quote_code("AAPL.US") == "gb_aapl"
    assert quote_code("700.HK") == "rt_hk00700"
    assert quote_code("600519.SH") == "sh600519"
    assert quote_code("000568.SZ") == "sz000568"
    assert quote_code("430047.BJ") == "bj430047"
    assert quote_code("BRK.B.US") is None
    assert quote_code("BRK-B.US") is None
    assert quote_code("700.SG") is None
    assert quote_code("AAPL") is None


def test_parse_us_quote() -> None:
    quote = parse_quote("AAPL.US", build_us_body())

    assert quote is not None
    assert quote.source_key == "sina"
    assert quote.currency == "USD"
    assert quote.last_done == Decimal("343.4600")
    assert quote.prev_close == Decimal("342.0000")
    assert quote.open == Decimal("346.0850")
    assert quote.high == Decimal("347.8200")
    assert quote.low == Decimal("340.4600")
    assert quote.volume == 59946368
    assert quote.turnover == Decimal("20629491159.0000")
    assert quote.timestamp == datetime(
        2026, 10, 17, 7, 59, 51, tzinfo=ZoneInfo("Asia/Shanghai")
    )


def test_parse_hk_quote() -> None:
    quote = parse_quote("700.HK", build_hk_body())

    assert quote is not None
    assert quote.currency == "HKD"
    assert quote.last_done == Decimal("417.800")
    assert quote.volume == 18752869
    assert quote.turnover == Decimal("7901198756.124")
    assert quote.timestamp == datetime(
        2026, 10, 16, 16, 8, 22, tzinfo=ZoneInfo("Asia/Shanghai")
    )


def test_parse_domestic_quote() -> None:
    quote = parse_quote("600519.SH", build_domestic_body())

    assert quote is not None
    assert quote.currency == "CNY"
    assert quote.volume == 3850175
    assert quote.turnover == Decimal("5075528306.000")
    assert quote.timestamp == datetime(
        2026, 10, 16, 15, 34, 59, tzinfo=ZoneInfo("Asia/Shanghai")
    )


def test_parse_quote_rejects_short_or_empty_body() -> None:
    assert parse_quote("AAPL.US", "") is None
    assert parse_quote("AAPL.US", "苹果,343.46") is None


@pytest.mark.asyncio
async def test_fetch_sends_referer_and_parses_quotes() -> None:
    calls: list[httpx.Request] = []
    provider = SinaProvider(
        transport=make_transport(
            {"gb_aapl": build_us_body(), "rt_hk00700": build_hk_body()}, calls
        )
    )

    quotes, errors = await provider.fetch(["AAPL.US", "700.HK", "BRK.B.US"])

    assert [quote.symbol for quote in quotes] == ["AAPL.US", "700.HK"]
    assert errors[0].symbol == "BRK.B.US"
    assert calls[0].headers["Referer"] == "https://finance.sina.com.cn"
    assert request_codes(calls[0]) == ["gb_aapl", "rt_hk00700"]


@pytest.mark.asyncio
async def test_fetch_reports_missing_symbols() -> None:
    provider = SinaProvider(transport=make_transport({}))

    quotes, errors = await provider.fetch(["AAPL.US"])

    assert quotes == []
    assert [(error.symbol, error.reason) for error in errors] == [
        ("AAPL.US", "新浪行情未返回该标的")
    ]


@pytest.mark.asyncio
async def test_fetch_skips_request_when_no_symbol_is_supported() -> None:
    calls: list[httpx.Request] = []
    provider = SinaProvider(transport=make_transport({}, calls))

    quotes, errors = await provider.fetch(["BRK.B.US", "700.SG"])

    assert quotes == []
    assert [error.symbol for error in errors] == ["BRK.B.US", "700.SG"]
    assert calls == []


@pytest.mark.asyncio
async def test_fetch_wraps_http_errors() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="forbidden")

    provider = SinaProvider(transport=httpx.MockTransport(handler))

    with pytest.raises(ProviderError, match="请求失败"):
        await provider.fetch(["AAPL.US"])
