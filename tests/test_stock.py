from datetime import datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from zoneinfo import ZoneInfo

import pytest
from nonebot.adapters.onebot.v11 import Message

from fake import fake_group_message_event_v11, fake_private_message_event_v11
from nonebot_plugin_stock import plugin as stock
from nonebot_plugin_stock.providers import Quote, QuoteResult, SymbolError


class MatcherFinished(Exception):
    """捕获 matcher.finish，便于直接测试 handler 的最终消息。"""

    def __init__(self, message: object = None) -> None:
        super().__init__(message)
        self.message = message


@pytest.fixture
def finish_matchers(monkeypatch: pytest.MonkeyPatch):
    """把 matcher.finish 替换成可断言的异常。"""

    async def finish(message: object = None, **_kwargs: object) -> None:
        raise MatcherFinished(message)

    monkeypatch.setattr(stock.longbridge_command, "finish", finish)
    monkeypatch.setattr(stock.stock_quote, "finish", finish)


@pytest.fixture
def quick_symbols_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / stock.QUICK_SYMBOLS_FILE
    monkeypatch.setattr(stock.localstore, "get_plugin_data_file", lambda _: path)
    return path


def make_quote(**overrides: object) -> Quote:
    values: dict[str, object] = {
        "symbol": "AAPL.US",
        "source_key": "longbridge",
        "source_label": "Longbridge OpenAPI",
        "currency": "USD",
        "last_done": Decimal("195.25"),
        "prev_close": Decimal("190.00"),
        "open": Decimal("191"),
        "high": Decimal("196.5"),
        "low": Decimal("189.75"),
        "volume": 1234567,
        "turnover": Decimal("987654.3"),
        "trade_status": "Normal",
        "timestamp": datetime(2026, 8, 22, 9, 30, 1, tzinfo=ZoneInfo("Asia/Shanghai")),
    }
    values.update(overrides)
    return Quote(**values)  # type: ignore[arg-type]


def make_result(
    quotes: list[Quote],
    symbol_errors: list[SymbolError] | None = None,
    *,
    provider_key: str = "longbridge",
) -> QuoteResult:
    return QuoteResult(
        quotes=quotes,
        symbol_errors=symbol_errors or [],
        provider_key=provider_key,
        provider_label=stock.QUOTE_SOURCE_LABELS[provider_key],
    )


def test_symbol_normalization_and_validation() -> None:
    assert stock._normalize_symbol(" aapl ") == "AAPL.US"
    assert stock._normalize_symbol(" 700.hk ") == "700.HK"
    assert stock._symbol_alias("BRK.B.US") == "brk.b"

    assert stock._is_valid_symbol("AAPL.US")
    assert stock._is_valid_symbol("BRK-B.US")
    assert stock._is_valid_symbol("600519.SH")
    assert not stock._is_valid_symbol("aapl.US")
    assert stock._is_valid_symbol("AAPL")
    assert not stock._is_valid_symbol("AAPL/US")


def test_load_and_save_added_symbols(quick_symbols_file: Path) -> None:
    assert stock._load_added_symbols() == set()

    quick_symbols_file.write_text(
        '["COIN.US", "invalid symbol", 123, "tsla.us"]',
        encoding="utf-8",
    )
    assert stock._load_added_symbols() == {"COIN.US"}

    stock._save_added_symbols({"TSLA.US", "COIN.US"})
    assert quick_symbols_file.read_text(encoding="utf-8") == (
        '[\n  "COIN.US",\n  "TSLA.US"\n]\n'
    )


@pytest.mark.parametrize("content", ["not json", "{}", "null", "[1]"])
def test_load_added_symbols_ignores_invalid_file(
    quick_symbols_file: Path, content: str
) -> None:
    quick_symbols_file.write_text(content, encoding="utf-8")
    assert stock._load_added_symbols() == set()


def test_quick_symbols_include_popular_and_custom_aliases(
    quick_symbols_file: Path,
) -> None:
    quick_symbols_file.write_text('["COIN.US"]', encoding="utf-8")

    symbols = stock._quick_symbols()

    assert symbols["qqq"] == "QQQ.US"
    assert symbols["qqq.us"] == "QQQ.US"
    assert symbols["coin"] == "COIN.US"
    assert symbols["coin.us"] == "COIN.US"


@pytest.mark.asyncio
async def test_is_quick_stock_requires_message_event(
    quick_symbols_file: Path,
) -> None:
    group_event = fake_group_message_event_v11(message=Message(" AAPL "))
    other_event = SimpleNamespace(get_plaintext=lambda: "AAPL")

    assert await stock._is_quick_stock(group_event)
    assert not await stock._is_quick_stock(other_event)  # type: ignore[arg-type]


def test_build_longbridge_config_strips_values_and_rejects_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        stock,
        "get_driver",
        lambda: SimpleNamespace(
            config=SimpleNamespace(
                longbridge_app_key=" key ",
                longbridge_app_secret="secret",
                longbridge_access_token="token",
            )
        ),
    )
    factory = Mock(return_value="config")
    monkeypatch.setattr(stock.Config, "from_apikey", factory)

    assert stock._build_longbridge_config() == "config"
    factory.assert_called_once_with(
        app_key="key", app_secret="secret", access_token="token"
    )

    monkeypatch.setattr(
        stock,
        "get_driver",
        lambda: SimpleNamespace(
            config=SimpleNamespace(
                longbridge_app_key="key",
                longbridge_app_secret=" ",
                longbridge_access_token="token",
            )
        ),
    )
    with pytest.raises(stock._StockConfigError, match="未配置 Longbridge 凭证"):
        stock._build_longbridge_config()


def test_build_http_client_uses_same_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        stock,
        "get_driver",
        lambda: SimpleNamespace(
            config=SimpleNamespace(
                longbridge_app_key="key",
                longbridge_app_secret="secret",
                longbridge_access_token="token",
            )
        ),
    )
    factory = Mock(return_value="client")
    monkeypatch.setattr(stock.HttpClient, "from_apikey", factory)

    assert stock._build_longbridge_http_client() == "client"
    factory.assert_called_once_with(
        app_key="key", app_secret="secret", access_token="token"
    )


@pytest.mark.asyncio
async def test_quote_context_and_http_client_are_cached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = object()
    client = object()
    stock._quote_context_state.value = None
    stock._http_client_state.value = None
    monkeypatch.setattr(stock, "_build_longbridge_config", lambda: "config")
    monkeypatch.setattr(stock, "_build_longbridge_http_client", lambda: client)
    create = Mock(return_value=context)
    monkeypatch.setattr(stock.AsyncQuoteContext, "create", create)

    assert await stock._get_quote_context() is context
    assert await stock._get_quote_context() is context
    assert await stock._get_http_client() is client
    assert await stock._get_http_client() is client
    create.assert_called_once()

    stock._quote_context_state.value = None
    stock._http_client_state.value = None


@pytest.mark.parametrize(
    ("value", "places", "signed", "expected"),
    [
        (None, 2, False, "-"),
        ("", 2, False, "-"),
        ("1234.5", 2, False, "1,234.50"),
        ("1.2", 2, True, "+1.20"),
        ("-1.2", 1, True, "-1.2"),
        ("unknown", 2, False, "unknown"),
    ],
)
def test_format_decimal(
    value: object, places: int, signed: bool, expected: str
) -> None:
    assert stock._format_decimal(value, places, signed=signed) == expected


def test_format_change_handles_normal_zero_and_invalid_values() -> None:
    assert stock._format_change("105", "100") == ("+5.00", "+5.00%")
    assert stock._format_change("5", "0") == ("+5.00", "-")
    assert stock._format_change("bad", "100") == ("-", "-")


def test_format_timestamp_status_market_and_currency() -> None:
    naive = datetime(2026, 8, 22, 9, 30, 1)
    utc = datetime(2026, 8, 22, 1, 30, 1, tzinfo=ZoneInfo("UTC"))
    expected = "2026-08-22 09:30:01 (GMT+8)"

    assert stock._format_timestamp(naive) == expected
    assert stock._format_timestamp(utc) == expected
    assert stock._format_timestamp(None) == "-"
    assert stock._format_status(SimpleNamespace(__name__="Normal")) == "Normal"
    assert stock._format_status("Trading") == "Trading"
    assert stock._format_status(None) == "-"
    assert stock._get_market_info("AAPL.US") == ("美股", "USD")
    assert stock._get_market_info("unknown.XX") == ("未知市场（XX）", "")
    assert stock._format_currency("12", "USD") == "12.00 USD"
    assert stock._format_currency("12", "") == "12.00"


def test_format_quote_contains_market_data() -> None:
    formatted = stock._format_quote(make_quote())

    assert formatted == "\n".join(
        [
            "标的：AAPL.US",
            "市场：美股",
            "最新价：195.25 USD",
            "涨跌额：5.25 USD",
            "涨跌幅：+2.76%",
            "昨收：190.00 USD",
            "开盘：191.00 USD",
            "最高：196.50 USD",
            "最低：189.75 USD",
            "成交量：1,234,567",
            "成交额：987,654.30 USD",
            "交易状态：Normal",
            "更新时间：2026-08-22 09:30:01 (GMT+8)",
            "数据源：Longbridge OpenAPI",
        ]
    )
    assert (
        stock._format_quotes([make_quote(), make_quote(symbol="TSLA.US")]).count(
            "标的："
        )
        == 2
    )


def test_format_quote_labels_actual_source_and_missing_fields() -> None:
    quote = make_quote(
        source_key="tencent",
        source_label=stock.QUOTE_SOURCE_LABELS["tencent"],
        currency="",
        trade_status=None,
        volume=None,
        timestamp=None,
    )

    formatted = stock._format_quote(quote)

    assert "数据源：腾讯行情（免费源，可能延迟）" in formatted
    assert "成交量：-" in formatted
    assert "交易状态：-" in formatted
    assert "更新时间：-" in formatted
    assert "最新价：195.25 USD" in formatted


def test_rank_formatters_cover_missing_values_and_market_fallback() -> None:
    item = {
        "code": "AAPL",
        "market": "US",
        "name": "Apple",
        "last_done": "195.25",
        "change": "5.25",
        "chg": "0.0276",
        "total_amount": "1000",
        "turnover_rate": "0.12",
        "volume_rate": "1.5",
    }
    formatted = stock._format_rank_item(item, 1, "HK")

    assert "1. AAPL.US  Apple" in formatted
    assert "最新价：195.25 USD" in formatted
    assert "涨跌幅：+2.76%" in formatted
    assert "换手率：12.00%" in formatted
    assert stock._format_rank_percent(None) == "-"
    assert stock._format_rank_percent("bad") == "bad"
    assert stock._rank_symbol({}, "HK") == "-.HK"
    assert stock._rank_currency("XX") == ""


def test_turnover_formatters_extract_screener_indicators() -> None:
    item = {
        "counter_id": "lb/US/AAPL",
        "name": "Apple",
        "indicators": [
            {"key": "filter_prevclose", "value": "195.25"},
            {"key": "filter_prevchg", "value": "2.76"},
            {"key": "filter_balance", "value": "1000000"},
        ],
    }

    formatted = stock._format_turnover_item(item, 1, "US")

    assert "1. AAPL.US  Apple" in formatted
    assert "最新价：195.25 USD" in formatted
    assert "涨跌幅：+2.76%" in formatted
    assert "最新成交额：1,000,000.00 USD" in formatted
    assert stock._screener_indicator({}, "filter_balance") is None
    assert stock._screener_symbol({}, "US") == "-.US"


def test_rank_categories_supports_dynamic_and_static_data() -> None:
    dynamic = stock._format_rank_categories(
        {
            "first_tags": [
                {
                    "name": "热门",
                    "second_tags": [
                        {"market": "us"},
                        {"market": "SG"},
                        {"name": "missing market"},
                    ],
                },
                {"key": "empty", "second_tags": "invalid"},
            ]
        }
    )
    static = stock._format_rank_categories({"first_tags": []})

    assert "热门：US（美股）、SG（新加坡）" in dynamic
    assert "empty" in dynamic
    assert "类型：hot | rising | trade | discuss | watch" in dynamic
    assert "hot     总热度：US（美股）、HK（港股）" in static


@pytest.mark.asyncio
async def test_rank_queries_build_expected_requests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = SimpleNamespace(request_async=AsyncMock(return_value={"ok": True}))
    monkeypatch.setattr(stock, "_get_http_client", AsyncMock(return_value=client))

    await stock._query_rank_categories()
    await stock._query_rank_list("trade", "US", 20)
    await stock._query_turnover_list("HK", 5)

    calls = client.request_async.await_args_list
    assert calls[0].args == ("get", "/v1/quote/market/rank/categories")
    assert calls[1].args == (
        "get",
        "/v1/quote/market/rank/list?key=ib_trade_heat-US"
        "&delay_bmp=false&need_article=false&market=US&size=20",
    )
    assert calls[2].args == ("post", "/v1/quote/ai/screener/search")
    body = calls[2].kwargs["body"]
    assert body["market"] == "HK"
    assert body["size"] == 5
    assert body["sort_by"] == 7
    assert body["sort_order"] == 1
    assert body["returns"][-1] == "filter_balance"


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        (["hot", "US"], ("hot", "US", 10)),
        (["UP", "hk", "20"], ("rising", "HK", 20)),
        (["discussion", "CN", "1"], ("discuss", "CN", 1)),
        (["watchlist", "SG", "50"], ("watch", "SG", 50)),
    ],
)
def test_parse_rank_arguments(arguments: list[str], expected: tuple[str, str, int]):
    assert stock._parse_rank_arguments(arguments) == expected


@pytest.mark.parametrize(
    "arguments",
    [
        [],
        ["hot"],
        ["unknown", "US"],
        ["hot", "US", "0"],
        ["hot", "US", "51"],
        ["hot", "US", "not-number"],
    ],
)
def test_parse_rank_arguments_rejects_invalid_usage(arguments: list[str]) -> None:
    with pytest.raises((stock._RankUsageError, stock._RankArgumentError)):
        stock._parse_rank_arguments(arguments)


def test_parse_rank_arguments_rejects_unsupported_market() -> None:
    with pytest.raises(stock._RankArgumentError, match="不支持市场 SG"):
        stock._parse_rank_arguments(["hot", "SG"])
    with pytest.raises(stock._RankArgumentError, match="榜单市场必须是"):
        stock._parse_rank_arguments(["hot", "JP"])


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        (["US"], ("US", 10)),
        (["hk", "25"], ("HK", 25)),
        (["CN", "1"], ("CN", 1)),
    ],
)
def test_parse_turnover_arguments(
    arguments: list[str], expected: tuple[str, int]
) -> None:
    assert stock._parse_turnover_arguments(arguments) == expected


@pytest.mark.parametrize("arguments", [[], ["US", "1", "2"], ["SG"], ["US", "0"]])
def test_parse_turnover_arguments_rejects_invalid_usage(arguments: list[str]) -> None:
    with pytest.raises((stock._RankUsageError, stock._RankArgumentError)):
        stock._parse_turnover_arguments(arguments)


def test_rank_updated_at_formats_unix_timestamp_and_invalid_values() -> None:
    assert stock._format_rank_updated_at(None) == "-"
    assert stock._format_rank_updated_at("bad") == "bad"
    assert stock._format_rank_updated_at(0) == "1970-01-01 08:00:00 (GMT+8)"


@pytest.mark.asyncio
async def test_update_quick_symbols_add_remove_and_validate(
    quick_symbols_file: Path,
) -> None:
    changed, unchanged = await stock._update_quick_symbols([" coin "], remove=False)
    assert changed == ["COIN.US"]
    assert unchanged == []
    assert stock._load_added_symbols() == {"COIN.US"}

    changed, unchanged = await stock._update_quick_symbols(
        ["coin.us", "TSLA"], remove=False
    )
    assert changed == ["TSLA.US"]
    assert unchanged == ["COIN.US"]

    changed, unchanged = await stock._update_quick_symbols(
        ["COIN.US", "missing"], remove=True
    )
    assert changed == ["COIN.US"]
    assert unchanged == ["MISSING.US"]
    assert stock._load_added_symbols() == {"TSLA.US"}

    with pytest.raises(ValueError, match=r"BAD SYMBOL\.US"):
        await stock._update_quick_symbols(["bad symbol"], remove=False)


def test_format_quick_list() -> None:
    assert stock._format_quick_list(set()) == "当前没有已添加的快捷标的"
    formatted = stock._format_quick_list({"TSLA.US", "COIN.US"})
    assert formatted.splitlines() == [
        "已添加快捷标的（2）：",
        "COIN.US（可直接发送 coin）",
        "TSLA.US（可直接发送 tsla）",
    ]


@pytest.mark.asyncio
async def test_finish_forward_sends_group_and_private_messages(
    finish_matchers,
) -> None:
    group = fake_group_message_event_v11(group_id=42)
    group_bot = SimpleNamespace(self_id="7", call_api=AsyncMock())
    with pytest.raises(MatcherFinished) as group_finished:
        await stock._finish_forward(
            group, group_bot, ("header", "item"), "fallback", "Test"
        )
    assert group_finished.value.message is None
    assert group_bot.call_api.await_args.args[0] == "send_group_forward_msg"
    assert group_bot.call_api.await_args.kwargs["group_id"] == 42
    assert len(group_bot.call_api.await_args.kwargs["messages"]) == 2

    private = fake_private_message_event_v11(user_id=24)
    private_bot = SimpleNamespace(self_id="7", call_api=AsyncMock())
    with pytest.raises(MatcherFinished):
        await stock._finish_forward(
            private, private_bot, ("content",), "fallback", "Test"
        )
    assert private_bot.call_api.await_args.args[0] == "send_private_forward_msg"
    assert private_bot.call_api.await_args.kwargs["user_id"] == 24


@pytest.mark.asyncio
async def test_finish_forward_falls_back_for_unsupported_event(
    finish_matchers,
) -> None:
    bot = SimpleNamespace(self_id="7", call_api=AsyncMock())
    with pytest.raises(MatcherFinished) as finished:
        await stock._finish_forward(
            SimpleNamespace(), bot, ("content",), "fallback", "Test"
        )
    assert finished.value.message == "fallback"
    bot.call_api.assert_not_awaited()


@pytest.mark.asyncio
async def test_finish_forward_falls_back_when_api_fails(finish_matchers) -> None:
    bot = SimpleNamespace(
        self_id="7", call_api=AsyncMock(side_effect=TypeError("bad node"))
    )
    with pytest.raises(MatcherFinished) as finished:
        await stock._finish_forward(
            fake_group_message_event_v11(), bot, ("content",), "fallback", "Test"
        )
    assert finished.value.message == "fallback"


@pytest.mark.asyncio
async def test_handle_quotes_returns_single_message(
    monkeypatch: pytest.MonkeyPatch, finish_matchers
) -> None:
    quote = make_quote()
    query = AsyncMock(return_value=make_result([quote]))
    monkeypatch.setattr(stock, "_query_quotes", query)

    with pytest.raises(MatcherFinished) as finished:
        await stock._handle_quotes(
            ["AAPL.US"], fake_group_message_event_v11(), SimpleNamespace()
        )

    query.assert_awaited_once_with(["AAPL.US"])
    assert "标的：AAPL.US" in finished.value.message


@pytest.mark.asyncio
async def test_handle_quotes_uses_forward_for_multiple_quotes(
    monkeypatch: pytest.MonkeyPatch, finish_matchers
) -> None:
    quotes = [make_quote(), make_quote(symbol="TSLA.US")]
    forward = AsyncMock()
    monkeypatch.setattr(
        stock, "_query_quotes", AsyncMock(return_value=make_result(quotes))
    )
    monkeypatch.setattr(stock, "_finish_forward", forward)

    with pytest.raises(MatcherFinished):
        await stock._handle_quotes(
            ["AAPL.US", "TSLA.US"],
            fake_group_message_event_v11(),
            SimpleNamespace(),
        )

    forward.assert_awaited_once()
    assert forward.await_args.args[2] == (
        stock._format_quote(quotes[0]),
        stock._format_quote(quotes[1]),
    )
    assert forward.await_args.args[4] == "Longbridge 行情"


@pytest.mark.asyncio
async def test_handle_quotes_appends_unsupported_symbols(
    monkeypatch: pytest.MonkeyPatch, finish_matchers
) -> None:
    result = make_result(
        [make_quote()],
        [SymbolError("700.SG", "腾讯行情不支持该市场或标的格式")],
        provider_key="tencent",
    )
    monkeypatch.setattr(stock, "_query_quotes", AsyncMock(return_value=result))
    bot = SimpleNamespace(self_id="1", call_api=AsyncMock())

    with pytest.raises(MatcherFinished):
        await stock._handle_quotes(
            ["AAPL.US", "700.SG"], fake_group_message_event_v11(), bot
        )

    contents = [
        node.data["content"] for node in bot.call_api.await_args.kwargs["messages"]
    ]
    assert contents[-1] == "❌ 700.SG：腾讯行情不支持该市场或标的格式"
    assert contents[0] == stock._format_quote(result.quotes[0])


@pytest.mark.asyncio
async def test_handle_quotes_reports_all_sources_failed(
    monkeypatch: pytest.MonkeyPatch, finish_matchers
) -> None:
    error = stock.StockSourceError(
        ["腾讯行情（免费源，可能延迟）", "新浪行情（免费源，可能延迟）"],
        (SymbolError("AAPL.US", "腾讯行情未返回该标的"),),
    )
    monkeypatch.setattr(stock, "_query_quotes", AsyncMock(side_effect=error))

    with pytest.raises(MatcherFinished) as finished:
        await stock._handle_quotes(
            ["AAPL.US"], fake_group_message_event_v11(), SimpleNamespace()
        )

    assert "行情数据源均不可用（已尝试：腾讯行情（免费源，可能延迟）" in (
        finished.value.message
    )
    assert "· AAPL.US：腾讯行情未返回该标的" in finished.value.message


@pytest.mark.asyncio
async def test_handle_quotes_reports_invalid_source_config(
    monkeypatch: pytest.MonkeyPatch, finish_matchers
) -> None:
    monkeypatch.setattr(
        stock,
        "_query_quotes",
        AsyncMock(side_effect=stock.StockSourceConfigError.unknown(["foo"])),
    )

    with pytest.raises(MatcherFinished) as finished:
        await stock._handle_quotes(
            ["AAPL.US"], fake_group_message_event_v11(), SimpleNamespace()
        )

    assert finished.value.message == (
        "❌ 未知的行情数据源：foo（可选：longbridge、tencent、sina）"
    )


@pytest.mark.asyncio
async def test_handle_stock_quote_uses_shortcut_and_formats_result(
    monkeypatch: pytest.MonkeyPatch, finish_matchers, quick_symbols_file: Path
) -> None:
    monkeypatch.setattr(
        stock, "_query_quotes", AsyncMock(return_value=make_result([make_quote()]))
    )
    event = fake_group_message_event_v11(message=Message(" AAPL "))

    with pytest.raises(MatcherFinished) as finished:
        await stock.handle_stock_quote(event)

    assert "标的：AAPL.US" in finished.value.message


@pytest.mark.asyncio
async def test_handle_stock_quote_reports_unknown_shortcut(
    finish_matchers, quick_symbols_file: Path
) -> None:
    event = fake_group_message_event_v11(message=Message("unknown"))

    with pytest.raises(MatcherFinished) as finished:
        await stock.handle_stock_quote(event)

    assert finished.value.message == (
        "暂不支持该快捷标的，请使用 /stock quote <代码.市场> 查询"
    )


@pytest.mark.asyncio
async def test_handle_quick_command_manages_symbols(
    monkeypatch: pytest.MonkeyPatch,
    finish_matchers,
    quick_symbols_file: Path,
) -> None:
    event = fake_group_message_event_v11()
    bot = SimpleNamespace()

    with pytest.raises(MatcherFinished) as added:
        await stock._handle_quick_command("add", ["coin"], event, bot)
    assert added.value.message == "✅ 已添加快捷标的：COIN.US"

    with pytest.raises(MatcherFinished) as listed:
        await stock._handle_quick_command("list", [], event, bot)
    assert "COIN.US（可直接发送 coin）" in listed.value.message

    with pytest.raises(MatcherFinished) as duplicate:
        await stock._handle_quick_command("add", ["coin"], event, bot)
    assert duplicate.value.message == "快捷标的已存在\n未变化：COIN.US"

    with pytest.raises(MatcherFinished) as removed:
        await stock._handle_quick_command("remove", ["coin"], event, bot)
    assert removed.value.message == "✅ 已删除快捷标的：COIN.US"
    assert stock._load_added_symbols() == set()

    usage = AsyncMock(side_effect=MatcherFinished())
    monkeypatch.setattr(stock, "_finish_usage", usage)
    with pytest.raises(MatcherFinished):
        await stock._handle_quick_command("invalid", ["COIN.US"], event, bot)
    usage.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_rank_command_formats_rank_and_limits_items(
    monkeypatch: pytest.MonkeyPatch, finish_matchers
) -> None:
    data = {
        "updated_at": 0,
        "lists": [
            {
                "code": "AAPL",
                "market": "US",
                "name": "Apple",
                "last_done": "195",
                "change": "5",
                "chg": "0.02",
                "total_amount": "1000",
                "turnover_rate": "0.1",
                "volume_rate": "2",
            },
            {"code": "TSLA", "market": "US", "name": "Tesla"},
        ],
    }
    forward = AsyncMock(side_effect=MatcherFinished())
    monkeypatch.setattr(stock, "_query_rank_list", AsyncMock(return_value=data))
    monkeypatch.setattr(stock, "_finish_forward", forward)

    with pytest.raises(MatcherFinished):
        await stock._handle_rank_command(
            ["trade", "us", "1"],
            fake_group_message_event_v11(),
            SimpleNamespace(),
        )

    contents = forward.await_args.args[2]
    assert contents[0].startswith("美股热门交易榜 Top 1")
    assert len(contents) == 2
    assert "AAPL.US" in contents[1]


@pytest.mark.asyncio
async def test_handle_turnover_command_formats_screener_results(
    monkeypatch: pytest.MonkeyPatch, finish_matchers
) -> None:
    data = {
        "items": [
            {
                "counter_id": "lb/US/AAPL",
                "name": "Apple",
                "indicators": [
                    {"key": "filter_prevclose", "value": "195"},
                    {"key": "filter_prevchg", "value": "2"},
                    {"key": "filter_balance", "value": "1000"},
                ],
            }
        ]
    }
    forward = AsyncMock(side_effect=MatcherFinished())
    monkeypatch.setattr(stock, "_query_turnover_list", AsyncMock(return_value=data))
    monkeypatch.setattr(stock, "_finish_forward", forward)

    with pytest.raises(MatcherFinished):
        await stock._handle_turnover_command(
            ["us", "10"], fake_group_message_event_v11(), SimpleNamespace()
        )

    contents = forward.await_args.args[2]
    assert contents[0].startswith("美股成交额榜 Top 1")
    assert "最新成交额：1,000.00 USD" in contents[1]


@pytest.mark.asyncio
async def test_handle_longbridge_quote_help_uses_usage_message(
    finish_matchers,
) -> None:
    with pytest.raises(MatcherFinished) as finished:
        await stock.handle_longbridge_quote(
            SimpleNamespace(),
            SimpleNamespace(self_id="1", call_api=AsyncMock()),
            Message("--help"),
        )

    assert finished.value.message == "\n\n".join(stock._usage_nodes())
    assert "数据源" not in stock.LONGBRIDGE_USAGE_NODES[-1]
    assert "腾讯行情" in finished.value.message
    assert "STOCK_QUOTE_SOURCES" in finished.value.message
