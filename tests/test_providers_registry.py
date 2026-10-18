from dataclasses import dataclass

import pytest

from nonebot_plugin_stock.constants import QUOTE_SOURCE_LABELS
from nonebot_plugin_stock.errors import StockSourceConfigError, StockSourceError
from nonebot_plugin_stock.providers import base
from nonebot_plugin_stock.providers.registry import build_providers, fetch_quotes


@dataclass
class FakeProvider:
    key: str
    label: str
    result: tuple[list[base.Quote], list[base.SymbolError]] | None = None
    error: Exception | None = None
    delay: float = 0.0

    async def fetch(
        self, symbols: list[str]
    ) -> tuple[list[base.Quote], list[base.SymbolError]]:
        if self.delay:
            import asyncio

            await asyncio.sleep(self.delay)
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


def make_quote(symbol: str = "AAPL.US", source_key: str = "tencent") -> base.Quote:
    return base.Quote(
        symbol=symbol,
        source_key=source_key,
        source_label=QUOTE_SOURCE_LABELS[source_key],
    )


def test_build_providers_rejects_empty_and_unknown_keys() -> None:
    async def get_context() -> None:
        return None

    with pytest.raises(StockSourceConfigError, match="不能为空"):
        build_providers([], timeout=1.0, get_longbridge_context=get_context)

    with pytest.raises(StockSourceConfigError, match="未知的行情数据源：foo"):
        build_providers(["foo"], timeout=1.0, get_longbridge_context=get_context)


@pytest.mark.asyncio
async def test_fetch_quotes_uses_first_working_provider() -> None:
    primary = FakeProvider(
        "tencent", QUOTE_SOURCE_LABELS["tencent"], error=base.ProviderError("boom")
    )
    fallback = FakeProvider(
        "sina",
        QUOTE_SOURCE_LABELS["sina"],
        result=([make_quote(source_key="sina")], []),
    )

    result = await fetch_quotes([primary, fallback], ["AAPL.US"], timeout=1.0)

    assert result.provider_key == "sina"
    assert [quote.symbol for quote in result.quotes] == ["AAPL.US"]


@pytest.mark.asyncio
async def test_fetch_quotes_skips_unconfigured_and_empty_providers() -> None:
    unconfigured = FakeProvider(
        "longbridge",
        QUOTE_SOURCE_LABELS["longbridge"],
        error=base.ProviderUnavailableError("未配置"),
    )
    empty = FakeProvider("tencent", QUOTE_SOURCE_LABELS["tencent"], result=([], []))
    working = FakeProvider(
        "sina",
        QUOTE_SOURCE_LABELS["sina"],
        result=([make_quote(source_key="sina")], []),
    )

    result = await fetch_quotes(
        [unconfigured, empty, working], ["AAPL.US"], timeout=1.0
    )

    assert result.provider_key == "sina"


@pytest.mark.asyncio
async def test_fetch_quotes_times_out_and_continues() -> None:
    slow = FakeProvider(
        "tencent",
        QUOTE_SOURCE_LABELS["tencent"],
        result=([make_quote()], []),
        delay=0.2,
    )
    working = FakeProvider(
        "sina",
        QUOTE_SOURCE_LABELS["sina"],
        result=([make_quote(source_key="sina")], []),
    )

    result = await fetch_quotes([slow, working], ["AAPL.US"], timeout=0.01)

    assert result.provider_key == "sina"


@pytest.mark.asyncio
async def test_fetch_quotes_survives_unexpected_provider_errors() -> None:
    broken = FakeProvider(
        "tencent", QUOTE_SOURCE_LABELS["tencent"], error=KeyError("bad payload")
    )
    working = FakeProvider(
        "sina",
        QUOTE_SOURCE_LABELS["sina"],
        result=([make_quote(source_key="sina")], []),
    )

    result = await fetch_quotes([broken, working], ["AAPL.US"], timeout=1.0)

    assert result.provider_key == "sina"


@pytest.mark.asyncio
async def test_fetch_quotes_reports_every_attempted_source() -> None:
    tencent = FakeProvider(
        "tencent",
        QUOTE_SOURCE_LABELS["tencent"],
        result=([], [base.SymbolError("AAPL.US", "腾讯行情未返回该标的")]),
    )
    sina = FakeProvider(
        "sina",
        QUOTE_SOURCE_LABELS["sina"],
        error=base.ProviderError("请求失败"),
    )

    with pytest.raises(StockSourceError) as raised:
        await fetch_quotes([tencent, sina], ["AAPL.US"], timeout=1.0)

    assert raised.value.attempted == (
        QUOTE_SOURCE_LABELS["tencent"],
        QUOTE_SOURCE_LABELS["sina"],
    )
    assert raised.value.symbol_errors[0].reason == "腾讯行情未返回该标的"
    assert "已尝试：腾讯行情（免费源，可能延迟）、新浪行情（免费源，可能延迟）" in str(
        raised.value
    )


@pytest.mark.asyncio
async def test_fetch_quotes_keeps_partial_symbol_errors() -> None:
    provider = FakeProvider(
        "tencent",
        QUOTE_SOURCE_LABELS["tencent"],
        result=(
            [make_quote()],
            [base.SymbolError("700.SG", "腾讯行情不支持该市场或标的格式")],
        ),
    )

    result = await fetch_quotes([provider], ["AAPL.US", "700.SG"], timeout=1.0)

    assert [error.symbol for error in result.symbol_errors] == ["700.SG"]
