"""使用 Longbridge OpenAPI 查询股票行情。

配置：

在项目的 ``.env`` 中配置以下 NoneBot 配置项：

.. code-block:: dotenv

    LONGBRIDGE_APP_KEY=你的AppKey
    LONGBRIDGE_APP_SECRET=你的AppSecret
    LONGBRIDGE_ACCESS_TOKEN=你的旧版AccessToken

Longbridge 当前 Python SDK 包名为 ``longbridge``，本插件使用传统 API Key
认证方式的 ``Config.from_apikey``，但密钥由 NoneBot 的 ``driver.config`` 提供。

支持直接输入以下快捷代码查询：``qqq``、``spy``、``aapl``、``tsla``、``msft``、
``nvda``、``amzn``、``googl``、``meta``、``amd`` 和 ``baba``。代码不区分大小写。
例如输入 ``qqq`` 会查询 Longbridge 标准代码 ``QQQ.US``。

可以使用 ``quick`` 子命令管理快捷标的。快捷标的保存在插件数据目录中，重启后仍然
有效；例如 ``/stock quick add COIN.US`` 后，输入 ``coin`` 或 ``COIN.US`` 都可以查询。

另外提供与 Longbridge CLI 一致的行情命令：

.. code-block:: text

    /longbridge quote AAPL.US
    /longbridge quote TSLA.US NVDA.US
    /stock quote TSLA.US
    /stock quick add COIN.US
    /stock quick list
    /stock quick quote
    /stock rank
    /stock rank trade US 10
    /stock rank turnover US 10

当前实现 ``quote``、``quick`` 和 ``rank`` 子命令；标的使用“代码.市场”格式。
``rank`` 使用 Longbridge CLI 的市场热度接口，榜单由服务端综合排序，不能指定
按照成交额或涨跌幅单字段排序。
"""

import asyncio
import json
import re
from datetime import datetime
from decimal import Decimal, DecimalException
from importlib import import_module
from typing import NoReturn
from zoneinfo import ZoneInfo

from longbridge.openapi import (
    AsyncQuoteContext,
    Config,
    HttpClient,
    OpenApiException,
)
from nonebot import get_driver, on_command, require
from nonebot.adapters import Event, Message
from nonebot.adapters.onebot.v11 import (
    Bot,
    GroupMessageEvent,
    MessageEvent,
    MessageSegment,
    PrivateMessageEvent,
)
from nonebot.adapters.onebot.v11.exception import ActionFailed, NetworkError
from nonebot.log import logger
from nonebot.params import CommandArg
from nonebot.plugin import on_message
from nonebot.rule import Rule

require("nonebot_plugin_localstore")
localstore = import_module("nonebot_plugin_localstore")

POPULAR_STOCKS = {
    "qqq": "QQQ.US",
    "spy": "SPY.US",
    "aapl": "AAPL.US",
    "tsla": "TSLA.US",
    "msft": "MSFT.US",
    "nvda": "NVDA.US",
    "amzn": "AMZN.US",
    "googl": "GOOGL.US",
    "meta": "META.US",
    "amd": "AMD.US",
    "baba": "BABA.US",
}
LOCAL_TIMEZONE = ZoneInfo("Asia/Shanghai")
HELP_ARGUMENTS = frozenset({"-h", "--help"})
RANK_DEFAULT_COUNT = 10
RANK_MAX_COUNT = 50
RANK_ARGUMENTS_WITHOUT_COUNT = 2
RANK_ARGUMENTS_WITH_COUNT = 3
TURNOVER_ARGUMENTS_WITHOUT_COUNT = 1
TURNOVER_ARGUMENTS_WITH_COUNT = 2
TURNOVER_MARKETS = frozenset({"US", "HK", "CN"})
COUNTER_ID_PARTS_MIN = 3
RANK_MARKETS = frozenset({"US", "HK", "CN", "SG"})
RANK_TYPES = {
    "hot": ("总热度", "ib_hot_all", frozenset({"US", "HK"})),
    "rising": ("热度上升", "ib_hot_up", frozenset({"US", "HK"})),
    "trade": ("热门交易", "ib_trade_heat", frozenset({"US", "HK"})),
    "discuss": ("热议", "ib_discuss_heat", RANK_MARKETS),
    "watch": ("关注度", "ib_watchlist_heat", RANK_MARKETS),
}
RANK_TYPE_ALIASES = {
    "hot": "hot",
    "热度": "hot",
    "total": "hot",
    "rising": "rising",
    "up": "rising",
    "上升": "rising",
    "trade": "trade",
    "trading": "trade",
    "交易": "trade",
    "discuss": "discuss",
    "discussion": "discuss",
    "talk": "discuss",
    "热议": "discuss",
    "watch": "watch",
    "watchlist": "watch",
    "关注": "watch",
}
TURNOVER_ALIASES = frozenset({"turnover", "amount", "成交额"})
RANK_MARKET_NAMES = {
    "US": "美股",
    "HK": "港股",
    "CN": "沪深",
    "SG": "新加坡",
}
QUICK_SYMBOLS_FILE = "quick_symbols.json"
SYMBOL_PATTERN = re.compile(r"^[A-Z0-9]+(?:[.-][A-Z0-9]+)*$")
MARKET_INFO = {
    "US": ("美股", "USD"),
    "HK": ("港股", "HKD"),
    "SH": ("沪市 A 股", "CNY"),
    "SZ": ("深市 A 股", "CNY"),
    "BJ": ("北交所", "CNY"),
    "CN": ("中国内地市场", "CNY"),
    "SG": ("新加坡股", "SGD"),
}
MIN_SUBCOMMAND_ARGUMENTS = 2
LONGBRIDGE_USAGE_NODES = (
    """Longbridge Market Data CLI

Usage:
  /longbridge <COMMAND> [OPTIONS]
  /stock <COMMAND> [OPTIONS]
""",
    """Commands:
  quote <SYMBOL>...  查询一个或多个标的的实时行情
  quick <COMMAND>    管理快捷标的
  rank [TYPE MARKET COUNT] 查询 Longbridge 市场榜单
""",
    """Quick commands:
  add <SYMBOL>...    添加快捷标的
  del <SYMBOL>...    删除快捷标的
  remove <SYMBOL>... 删除快捷标的（del 的别名）
  list               列出已添加的快捷标的
  quote              查询全部快捷标的（合并转发）
""",
    """Rank commands:
  rank               查看当前可用的榜单类型和市场
  rank hot US        查询美股总热度榜
  rank rising HK     查询港股热度上升榜
  rank trade US 20   查询美股热门交易榜前 20 条
  rank turnover US 10 查询美股成交额榜前 10 条
  rank discuss CN    查询沪深热议榜
  rank watch SG 10   查询新加坡关注度榜前 10 条

Types: hot | rising | trade | discuss | watch
Markets: US | HK | CN | SG
Count: 1-50，默认 10；实际结果由服务端榜单决定
Turnover markets: US | HK | CN
""",
    """Symbol format:
  <CODE>.<MARKET>
  TSLA.US    美股
  700.HK     港股
  600519.SH  沪市 A 股
  000568.SZ  深市 A 股
""",
    """Examples:
  /longbridge quote TSLA.US
  /longbridge quote TSLA.US NVDA.US
  /stock quote AAPL.US
  /stock quick add COIN.US
  /stock quick del COIN.US
  /stock quick list
  /stock rank
  /stock rank trade US 10
  /stock rank turnover US 10
""",
    """Options:
  -h, --help  显示此帮助信息""",
)
LONGBRIDGE_USAGE = "\n\n".join(LONGBRIDGE_USAGE_NODES)


class _StockConfigError(ValueError):
    """Longbridge 凭证未配置。"""

    def __init__(self) -> None:
        super().__init__(
            "未配置 Longbridge 凭证，请在 .env 中设置："
            "LONGBRIDGE_APP_KEY、LONGBRIDGE_APP_SECRET、"
            "LONGBRIDGE_ACCESS_TOKEN"
        )


class _RankUsageError(ValueError):
    """榜单命令参数不符合用法。"""


class _RankArgumentError(ValueError):
    """榜单命令参数值无效。"""

    @classmethod
    def market_required(cls) -> "_RankArgumentError":
        return cls(f"榜单市场必须是：{' | '.join(sorted(RANK_MARKETS))}")

    @classmethod
    def turnover_market_required(cls) -> "_RankArgumentError":
        return cls("成交额榜市场必须是：US | HK | CN")

    @classmethod
    def unsupported_market(
        cls, rank_type: str, market: str
    ) -> "_RankArgumentError":
        return cls(f"榜单类型 {rank_type} 不支持市场 {market}")

    @classmethod
    def invalid_count(cls) -> "_RankArgumentError":
        return cls("榜单数量必须是 1-50 的整数")


class _QuoteContextState:
    """保存当前事件循环使用的行情上下文。"""

    value: AsyncQuoteContext | None = None


class _HttpClientState:
    """保存调用 Longbridge 内部 HTTP 行情接口的客户端。"""

    value: HttpClient | None = None


longbridge_command = on_command(
    "longbridge",
    aliases={"stock"},
    force_whitespace=True,
)
_quote_context_state = _QuoteContextState()
_http_client_state = _HttpClientState()
_quote_context_lock = asyncio.Lock()
_http_client_lock = asyncio.Lock()
_quick_symbols_lock = asyncio.Lock()


def _normalize_symbol(symbol: str) -> str:
    normalized = symbol.strip().upper()
    if "." not in normalized:
        return f"{normalized}.US"
    return normalized


def _symbol_alias(symbol: str) -> str:
    return symbol.rsplit(".", maxsplit=1)[0].casefold()


def _is_valid_symbol(symbol: str) -> bool:
    return bool(SYMBOL_PATTERN.fullmatch(symbol))


def _load_added_symbols() -> set[str]:
    path = localstore.get_plugin_data_file(QUICK_SYMBOLS_FILE)
    if not path.exists():
        return set()

    try:
        content = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        logger.warning(f"读取 Longbridge 快捷标的失败：{error}")
        return set()

    if not isinstance(content, list):
        logger.warning("Longbridge 快捷标的数据格式无效，已忽略")
        return set()

    return {
        symbol
        for symbol in content
        if isinstance(symbol, str) and _is_valid_symbol(symbol)
    }


def _save_added_symbols(symbols: set[str]) -> None:
    path = localstore.get_plugin_data_file(QUICK_SYMBOLS_FILE)
    temporary_path = path.with_suffix(".tmp")
    temporary_path.write_text(
        json.dumps(sorted(symbols), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(path)


def _quick_symbols() -> dict[str, str]:
    symbols = {
        alias.casefold(): symbol for alias, symbol in POPULAR_STOCKS.items()
    }
    for _alias, symbol in tuple(symbols.items()):
        symbols.setdefault(symbol.casefold(), symbol)

    for symbol in _load_added_symbols():
        symbols[symbol.casefold()] = symbol
        symbols.setdefault(_symbol_alias(symbol), symbol)
    return symbols


async def _is_quick_stock(event: Event) -> bool:
    if not isinstance(event, MessageEvent):
        return False
    return event.get_plaintext().strip().casefold() in _quick_symbols()


stock_quote = on_message(rule=Rule(_is_quick_stock))


def _get_config_value(name: str) -> str | None:
    value = getattr(get_driver().config, name, None)
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _build_longbridge_config() -> Config:
    config_values = {
        "app_key": _get_config_value("longbridge_app_key"),
        "app_secret": _get_config_value("longbridge_app_secret"),
        "access_token": _get_config_value("longbridge_access_token"),
    }
    missing = [name for name, value in config_values.items() if not value]
    if missing:
        raise _StockConfigError

    return Config.from_apikey(**config_values)


def _build_longbridge_http_client() -> HttpClient:
    config_values = {
        "app_key": _get_config_value("longbridge_app_key"),
        "app_secret": _get_config_value("longbridge_app_secret"),
        "access_token": _get_config_value("longbridge_access_token"),
    }
    missing = [name for name, value in config_values.items() if not value]
    if missing:
        raise _StockConfigError

    return HttpClient.from_apikey(**config_values)


async def _get_quote_context() -> AsyncQuoteContext:
    if _quote_context_state.value is not None:
        return _quote_context_state.value

    async with _quote_context_lock:
        if _quote_context_state.value is None:
            config = _build_longbridge_config()
            _quote_context_state.value = AsyncQuoteContext.create(
                config, loop_=asyncio.get_running_loop()
            )
    return _quote_context_state.value


async def _get_http_client() -> HttpClient:
    if _http_client_state.value is not None:
        return _http_client_state.value

    async with _http_client_lock:
        if _http_client_state.value is None:
            _http_client_state.value = _build_longbridge_http_client()
    return _http_client_state.value


def _format_decimal(value: object, places: int = 2, *, signed: bool = False) -> str:
    if value is None or value == "":
        return "-"

    try:
        number = Decimal(str(value))
    except (DecimalException, TypeError, ValueError):
        return str(value)

    result = f"{number:,.{places}f}"
    if signed and number > 0:
        return f"+{result}"
    return result


def _format_change(last_done: object, prev_close: object) -> tuple[str, str]:
    try:
        change = Decimal(str(last_done)) - Decimal(str(prev_close))
        previous = Decimal(str(prev_close))
        if not previous:
            return _format_decimal(change, signed=True), "-"
        percent = change / previous * 100
    except (DecimalException, TypeError, ValueError):
        return "-", "-"
    return _format_decimal(change, signed=True), _format_decimal(
        percent, signed=True
    ) + "%"


def _format_timestamp(value: object) -> str:
    if not isinstance(value, datetime):
        return str(value or "-")
    if value.tzinfo is None:
        # Longbridge 的报价时间虽然没有 tzinfo，但已经是东八区时间。
        value = value.replace(tzinfo=LOCAL_TIMEZONE)
    formatted = value.astimezone(LOCAL_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")
    return f"{formatted} (GMT+8)"


def _format_status(value: object) -> str:
    return str(getattr(value, "__name__", value)).rsplit(".", 1)[-1]


def _get_market_info(symbol: object) -> tuple[str, str]:
    symbol_text = str(symbol or "").upper()
    market_code = symbol_text.rsplit(".", maxsplit=1)[-1]
    return MARKET_INFO.get(
        market_code,
        (f"未知市场（{market_code or '-'}）", ""),
    )


def _format_currency(value: object, currency: str) -> str:
    formatted = _format_decimal(value)
    return f"{formatted} {currency}" if currency else formatted


def _format_quote(quote: object) -> str:
    market, currency = _get_market_info(quote.symbol)
    change, change_percent = _format_change(
        quote.last_done,
        quote.prev_close,
    )
    return "\n".join(
        [
            f"标的：{quote.symbol}",
            f"市场：{market}",
            f"最新价：{_format_currency(quote.last_done, currency)}",
            f"涨跌额：{_format_currency(change, currency)}",
            f"涨跌幅：{change_percent}",
            f"昨收：{_format_currency(quote.prev_close, currency)}",
            f"开盘：{_format_currency(quote.open, currency)}",
            f"最高：{_format_currency(quote.high, currency)}",
            f"最低：{_format_currency(quote.low, currency)}",
            f"成交量：{quote.volume:,}",
            f"成交额：{_format_currency(quote.turnover, currency)}",
            f"交易状态：{_format_status(quote.trade_status)}",
            f"更新时间：{_format_timestamp(quote.timestamp)}",
            "数据源：Longbridge OpenAPI",
        ]
    )


def _format_quotes(quotes: list[object]) -> str:
    return "\n\n".join(_format_quote(quote) for quote in quotes)


def _format_rank_percent(value: object, *, signed: bool = True) -> str:
    if value is None or value == "":
        return "-"
    try:
        percent = Decimal(str(value)) * 100
    except (DecimalException, TypeError, ValueError):
        return str(value)
    return f"{_format_decimal(percent, signed=signed)}%"


def _rank_symbol(item: dict[str, object], fallback_market: str) -> str:
    code = str(item.get("code") or "-")
    market = str(item.get("market") or fallback_market).upper()
    return f"{code}.{market}"


def _rank_currency(market: str) -> str:
    return {
        "US": "USD",
        "HK": "HKD",
        "CN": "CNY",
        "SG": "SGD",
    }.get(market, "")


def _format_rank_amount(value: object, market: str) -> str:
    currency = _rank_currency(market)
    formatted = _format_decimal(value)
    return f"{formatted} {currency}" if currency else formatted


def _format_rank_item(
    item: dict[str, object], rank: int, fallback_market: str
) -> str:
    symbol = _rank_symbol(item, fallback_market)
    market = str(item.get("market") or fallback_market).upper()
    return "\n".join(
        [
            f"{rank}. {symbol}  {item.get('name') or '-'}",
            f"最新价：{_format_rank_amount(item.get('last_done'), market)}",
            f"涨跌额：{_format_rank_amount(item.get('change'), market)}",
            f"涨跌幅：{_format_rank_percent(item.get('chg'))}",
            f"成交额：{_format_rank_amount(item.get('total_amount'), market)}",
            f"换手率：{_format_rank_percent(item.get('turnover_rate'), signed=False)}",
            f"量比：{_format_decimal(item.get('volume_rate'))}",
        ]
    )


def _screener_indicator(item: dict[str, object], key: str) -> object:
    indicators = item.get("indicators")
    if not isinstance(indicators, list):
        return None
    for indicator in indicators:
        if isinstance(indicator, dict) and indicator.get("key") == key:
            return indicator.get("value")
    return None


def _screener_symbol(item: dict[str, object], fallback_market: str) -> str:
    counter_id = str(item.get("counter_id") or "")
    parts = counter_id.split("/")
    if len(parts) >= COUNTER_ID_PARTS_MIN:
        return f"{parts[-1]}.{parts[-2]}"
    return _rank_symbol(item, fallback_market)


def _format_turnover_item(
    item: dict[str, object], rank: int, market: str
) -> str:
    symbol = _screener_symbol(item, market)
    price = _format_rank_amount(
        _screener_indicator(item, "filter_prevclose"), market
    )
    change_percent = _format_decimal(
        _screener_indicator(item, "filter_prevchg"), signed=True
    )
    turnover = _format_rank_amount(
        _screener_indicator(item, "filter_balance"), market
    )
    return "\n".join(
        [
            f"{rank}. {symbol}  {item.get('name') or '-'}",
            f"最新价：{price}",
            f"涨跌幅：{change_percent}%",
            f"最新成交额：{turnover}",
        ]
    )


def _format_rank_updated_at(value: object) -> str:
    if value in (None, ""):
        return "-"
    try:
        timestamp = float(str(value))
        updated_at = datetime.fromtimestamp(timestamp, tz=ZoneInfo("UTC"))
    except (OSError, OverflowError, TypeError, ValueError):
        return str(value)
    return _format_timestamp(updated_at)


def _rank_static_categories() -> str:
    lines = ["Longbridge 可用市场榜单", ""]
    for rank_type, (name, _key, markets) in RANK_TYPES.items():
        market_names = "、".join(
            f"{market}（{RANK_MARKET_NAMES[market]}）"
            for market in ("US", "HK", "CN", "SG")
            if market in markets
        )
        lines.append(f"{rank_type:<8}{name}：{market_names}")
    lines.extend(
        [
            "",
            "用法：/stock rank <TYPE> <MARKET> [COUNT]",
            "成交额榜：/stock rank turnover <US | HK | CN> [COUNT]",
            "数量范围：1-50，默认 10",
        ]
    )
    return "\n".join(lines)


def _format_rank_categories(data: object) -> str:
    if not isinstance(data, dict):
        return _rank_static_categories()

    first_tags = data.get("first_tags")
    if not isinstance(first_tags, list) or not first_tags:
        return _rank_static_categories()

    lines = ["Longbridge 可用市场榜单", ""]
    for tag in first_tags:
        if not isinstance(tag, dict):
            continue
        group_name = str(tag.get("name") or tag.get("key") or "-")
        second_tags = tag.get("second_tags")
        if not isinstance(second_tags, list):
            lines.append(group_name)
            continue
        markets = []
        for item in second_tags:
            if not isinstance(item, dict) or not item.get("market"):
                continue
            market = str(item["market"]).upper()
            market_name = RANK_MARKET_NAMES.get(market, market)
            markets.append(f"{market}（{market_name}）")
        if markets:
            lines.append(f"{group_name}：{'、'.join(markets)}")

    lines.extend(
        [
            "",
            "用法：/stock rank <TYPE> <MARKET> [COUNT]",
            "类型：hot | rising | trade | discuss | watch",
            "成交额榜：/stock rank turnover <US | HK | CN> [COUNT]",
            "数量范围：1-50，默认 10",
        ]
    )
    return "\n".join(lines)


async def _query_rank_categories() -> object:
    client = await _get_http_client()
    return await client.request_async(
        "get", "/v1/quote/market/rank/categories"
    )


async def _query_rank_list(
    rank_type: str, market: str, count: int
) -> object:
    _name, key_prefix, _markets = RANK_TYPES[rank_type]
    path = (
        "/v1/quote/market/rank/list?"
        f"key={key_prefix}-{market}"
        f"&delay_bmp=false&need_article=false&market={market}&size={count}"
    )
    client = await _get_http_client()
    return await client.request_async("get", path)


async def _query_turnover_list(market: str, count: int) -> object:
    returns = [
        "filter_prevclose",
        "filter_prevchg",
        "filter_marketcap",
        "filter_salesgrowthyoy",
        "filter_pettm",
        "filter_pbmrq",
        "filter_industry",
        "filter_balance",
    ]
    body = {
        "market": market,
        "page": 0,
        "size": count,
        "filters": [],
        "returns": returns,
        "sort_by": returns.index("filter_balance"),
        "sort_order": 1,
        "industries": [],
    }
    client = await _get_http_client()
    return await client.request_async(
        "post", "/v1/quote/ai/screener/search", body=body
    )


async def _handle_rank_categories(event: Event, bot: Bot) -> NoReturn:
    try:
        data = await _query_rank_categories()
    except _StockConfigError as error:
        await longbridge_command.finish(str(error))
    except OpenApiException as error:
        logger.warning(f"Longbridge 榜单分类请求失败：{error}")
        await longbridge_command.finish(
            "❌ 榜单分类请求失败，请检查 Longbridge 配置或稍后再试"
        )
    except (OSError, RuntimeError, TimeoutError) as error:
        logger.warning(f"Longbridge 榜单分类连接失败：{error}")
        await longbridge_command.finish("❌ 榜单分类请求失败，请稍后再试")

    content = _format_rank_categories(data)
    await _finish_forward(
        event,
        bot,
        tuple(content.split("\n\n")),
        content,
        "Longbridge Rank",
    )


def _parse_turnover_arguments(arguments: list[str]) -> tuple[str, int]:
    if len(arguments) not in {
        TURNOVER_ARGUMENTS_WITHOUT_COUNT,
        TURNOVER_ARGUMENTS_WITH_COUNT,
    }:
        raise _RankUsageError

    market = arguments[0].upper()
    if market not in TURNOVER_MARKETS:
        raise _RankArgumentError.turnover_market_required()

    count = RANK_DEFAULT_COUNT
    if len(arguments) == TURNOVER_ARGUMENTS_WITH_COUNT:
        if not arguments[1].isdigit():
            raise _RankArgumentError.invalid_count()
        count = int(arguments[1])
    if not 1 <= count <= RANK_MAX_COUNT:
        raise _RankArgumentError.invalid_count()
    return market, count


async def _handle_turnover_command(
    arguments: list[str], event: Event, bot: Bot
) -> NoReturn:
    try:
        market, count = _parse_turnover_arguments(arguments)
    except _RankUsageError:
        await _finish_usage(event, bot)
    except _RankArgumentError as error:
        await longbridge_command.finish(f"❌ {error}")

    try:
        data = await _query_turnover_list(market, count)
    except _StockConfigError as error:
        await longbridge_command.finish(str(error))
    except OpenApiException as error:
        logger.warning(f"Longbridge 成交额榜请求失败：{error}")
        await longbridge_command.finish(
            "❌ 成交额榜请求失败，请检查 Longbridge 配置或稍后再试"
        )
    except (OSError, RuntimeError, TimeoutError) as error:
        logger.warning(f"Longbridge 成交额榜连接失败：{error}")
        await longbridge_command.finish("❌ 成交额榜请求失败，请稍后再试")

    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        await longbridge_command.finish("❌ Longbridge 未返回有效成交额榜数据")
    items = [item for item in data["items"] if isinstance(item, dict)][:count]
    if not items:
        await longbridge_command.finish("❌ 当前没有可用的成交额榜数据")

    market_name = RANK_MARKET_NAMES[market]
    header = "\n".join(
        [
            f"{market_name}成交额榜 Top {len(items)}",
            "排序指标：最新成交额（降序）",
            "数据源：Longbridge OpenAPI Screener",
        ]
    )
    contents = (
        header,
        *(
            _format_turnover_item(item, index, market)
            for index, item in enumerate(items, start=1)
        ),
    )
    fallback = "\n\n".join(contents)
    await _finish_forward(event, bot, contents, fallback, "Longbridge Turnover")


def _parse_rank_arguments(arguments: list[str]) -> tuple[str, str, int]:
    if len(arguments) not in {
        RANK_ARGUMENTS_WITHOUT_COUNT,
        RANK_ARGUMENTS_WITH_COUNT,
    }:
        raise _RankUsageError

    rank_type = RANK_TYPE_ALIASES.get(arguments[0].casefold())
    if rank_type is None:
        raise _RankUsageError

    market = arguments[1].upper()
    if market not in RANK_MARKETS:
        raise _RankArgumentError.market_required()

    _name, _key_prefix, supported_markets = RANK_TYPES[rank_type]
    if market not in supported_markets:
        raise _RankArgumentError.unsupported_market(arguments[0], market)

    count = RANK_DEFAULT_COUNT
    if len(arguments) == RANK_ARGUMENTS_WITH_COUNT:
        if not arguments[2].isdigit():
            raise _RankArgumentError.invalid_count()
        count = int(arguments[2])
    if not 1 <= count <= RANK_MAX_COUNT:
        raise _RankArgumentError.invalid_count()
    return rank_type, market, count


async def _handle_rank_command(
    arguments: list[str], event: Event, bot: Bot
) -> NoReturn:
    if not arguments or arguments[0].casefold() in {"list", "categories"}:
        if len(arguments) > 1:
            await _finish_usage(event, bot)
        await _handle_rank_categories(event, bot)

    try:
        rank_type, market, count = _parse_rank_arguments(arguments)
    except _RankUsageError:
        await _finish_usage(event, bot)
    except _RankArgumentError as error:
        await longbridge_command.finish(f"❌ {error}")

    try:
        data = await _query_rank_list(rank_type, market, count)
    except _StockConfigError as error:
        await longbridge_command.finish(str(error))
    except OpenApiException as error:
        logger.warning(f"Longbridge 榜单请求失败：{error}")
        await longbridge_command.finish(
            "❌ 榜单请求失败，请检查 Longbridge 配置或稍后再试"
        )
    except (OSError, RuntimeError, TimeoutError) as error:
        logger.warning(f"Longbridge 榜单连接失败：{error}")
        await longbridge_command.finish("❌ 榜单请求失败，请稍后再试")

    if not isinstance(data, dict) or not isinstance(data.get("lists"), list):
        await longbridge_command.finish("❌ Longbridge 未返回有效榜单数据")
    items = [item for item in data["lists"] if isinstance(item, dict)][:count]
    if not items:
        await longbridge_command.finish("❌ 当前没有可用的榜单数据")

    name = RANK_TYPES[rank_type][0]
    market_name = RANK_MARKET_NAMES[market]
    updated_at = _format_rank_updated_at(data.get("updated_at"))
    header = "\n".join(
        [
            f"{market_name}{name}榜 Top {len(items)}",
            f"更新时间：{updated_at}",
            "数据源：Longbridge OpenAPI（服务端综合榜单）",
        ]
    )
    contents = (
        header,
        *(
            _format_rank_item(item, index, market)
            for index, item in enumerate(items, start=1)
        ),
    )
    fallback = "\n\n".join(contents)
    await _finish_forward(event, bot, contents, fallback, "Longbridge Rank")


async def _query_quotes(symbols: list[str]) -> list[object]:
    context = await _get_quote_context()
    return await context.quote(symbols)


@stock_quote.handle()
async def handle_stock_quote(event: Event) -> None:
    keyword = event.get_plaintext().strip().casefold()
    symbol = _quick_symbols().get(keyword)
    if symbol is None:
        await stock_quote.finish(
            "暂不支持该快捷标的，请使用 /stock quote <代码.市场> 查询"
        )

    try:
        quotes = await _query_quotes([symbol])
    except _StockConfigError as error:
        await stock_quote.finish(str(error))
    except OpenApiException as error:
        logger.warning(f"Longbridge 行情请求失败：{error}")
        await stock_quote.finish(
            "❌ 股票行情请求失败，请检查 Longbridge 配置或稍后再试"
        )
    except (OSError, RuntimeError, TimeoutError) as error:
        logger.warning(f"Longbridge 行情连接失败：{error}")
        await stock_quote.finish("❌ 股票行情请求失败，请稍后再试")

    if not quotes:
        await stock_quote.finish(f"❌ 未获取到 {symbol} 的行情")
    await stock_quote.finish(_format_quote(quotes[0]))


async def _handle_quotes(
    symbols: list[str],
    event: Event,
    bot: Bot,
    *,
    force_forward: bool = False,
) -> None:
    try:
        quotes = await _query_quotes(symbols)
    except _StockConfigError as error:
        await longbridge_command.finish(str(error))
    except OpenApiException as error:
        logger.warning(f"Longbridge 行情请求失败：{error}")
        await longbridge_command.finish(
            "❌ 股票行情请求失败，请检查 Longbridge 配置或稍后再试"
        )
    except (OSError, RuntimeError, TimeoutError) as error:
        logger.warning(f"Longbridge 行情连接失败：{error}")
        await longbridge_command.finish("❌ 股票行情请求失败，请稍后再试")

    if not quotes:
        await longbridge_command.finish("❌ 未获取到行情")
    if force_forward or len(symbols) > 1:
        await _finish_forward(
            event,
            bot,
            tuple(_format_quote(quote) for quote in quotes),
            _format_quotes(quotes),
            "Longbridge 行情",
        )
    await longbridge_command.finish(_format_quotes(quotes))


async def _update_quick_symbols(
    raw_symbols: list[str], *, remove: bool
) -> tuple[list[str], list[str]]:
    normalized_symbols = [_normalize_symbol(symbol) for symbol in raw_symbols]
    invalid_symbols = [
        symbol
        for symbol in normalized_symbols
        if not _is_valid_symbol(symbol)
    ]
    if invalid_symbols:
        raise ValueError(", ".join(invalid_symbols))

    async with _quick_symbols_lock:
        symbols = _load_added_symbols()
        if remove:
            changed = [symbol for symbol in normalized_symbols if symbol in symbols]
            missing = [symbol for symbol in normalized_symbols if symbol not in symbols]
            symbols.difference_update(changed)
        else:
            changed = [symbol for symbol in normalized_symbols if symbol not in symbols]
            missing = [symbol for symbol in normalized_symbols if symbol in symbols]
            symbols.update(changed)
        if changed:
            _save_added_symbols(symbols)
    return changed, missing


def _format_quick_list(symbols: set[str]) -> str:
    if not symbols:
        return "当前没有已添加的快捷标的"

    lines = [f"已添加快捷标的（{len(symbols)}）："]
    lines.extend(
        f"{symbol}（可直接发送 {_symbol_alias(symbol)}）"
        for symbol in sorted(symbols)
    )
    return "\n".join(lines)


async def _finish_forward(
    event: Event,
    bot: Bot,
    contents: tuple[str, ...],
    fallback: str,
    nickname: str,
) -> NoReturn:
    try:
        nodes = [
            MessageSegment.node_custom(
                user_id=int(bot.self_id),
                nickname=nickname,
                content=content,
            )
            for content in contents
        ]
        if isinstance(event, GroupMessageEvent):
            await bot.call_api(
                "send_group_forward_msg",
                group_id=event.group_id,
                messages=nodes,
            )
        elif isinstance(event, PrivateMessageEvent):
            await bot.call_api(
                "send_private_forward_msg",
                user_id=event.user_id,
                messages=nodes,
            )
        else:
            await longbridge_command.finish(fallback)
    except (ActionFailed, NetworkError, TypeError, ValueError) as error:
        logger.warning(f"发送 Longbridge 合并转发失败：{error}")
        await longbridge_command.finish(fallback)
    await longbridge_command.finish()


async def _finish_usage(event: Event, bot: Bot) -> NoReturn:
    await _finish_forward(
        event,
        bot,
        LONGBRIDGE_USAGE_NODES,
        LONGBRIDGE_USAGE,
        "Longbridge CLI",
    )


async def _handle_quick_command(
    operation: str,
    symbols: list[str],
    event: Event,
    bot: Bot,
) -> None:
    if operation == "list" and not symbols:
        await longbridge_command.finish(_format_quick_list(_load_added_symbols()))
    if operation == "quote":
        if symbols:
            await _finish_usage(event, bot)
        quick_symbols = sorted(_load_added_symbols())
        if not quick_symbols:
            await longbridge_command.finish("当前没有已添加的快捷标的")
        await _handle_quotes(
            quick_symbols,
            event,
            bot,
            force_forward=True,
        )
    if operation not in {"add", "del", "remove"} or not symbols:
        await _finish_usage(event, bot)

    try:
        changed, unchanged = await _update_quick_symbols(
            symbols,
            remove=operation in {"del", "remove"},
        )
    except (OSError, RuntimeError) as error:
        logger.warning(f"保存 Longbridge 快捷标的失败：{error}")
        await longbridge_command.finish("❌ 快捷标的保存失败，请稍后再试")
    except ValueError as error:
        await longbridge_command.finish(
            f"❌ 标的格式无效：{error}。请使用如 COIN.US 或 COIN 的格式"
        )

    if operation == "add":
        message = (
            f"✅ 已添加快捷标的：{', '.join(changed)}"
            if changed
            else "快捷标的已存在"
        )
    else:
        message = (
            f"✅ 已删除快捷标的：{', '.join(changed)}"
            if changed
            else "没有找到要删除的快捷标的"
        )
    if unchanged:
        message += f"\n未变化：{', '.join(unchanged)}"
    await longbridge_command.finish(message)


@longbridge_command.handle()
async def handle_longbridge_quote(
    event: Event,
    bot: Bot,
    args: Message = CommandArg(),
) -> None:
    arguments = args.extract_plain_text().split()
    if not arguments or arguments[0].casefold() in HELP_ARGUMENTS:
        await _finish_usage(event, bot)

    subcommand = arguments[0].casefold()
    if any(argument.casefold() in HELP_ARGUMENTS for argument in arguments[1:]):
        await _finish_usage(event, bot)

    if subcommand == "rank":
        if len(arguments) > 1 and arguments[1].casefold() in TURNOVER_ALIASES:
            await _handle_turnover_command(arguments[2:], event, bot)
        await _handle_rank_command(arguments[1:], event, bot)

    if subcommand == "quick":
        if len(arguments) < MIN_SUBCOMMAND_ARGUMENTS:
            await _finish_usage(event, bot)

        await _handle_quick_command(
            arguments[1].casefold(),
            arguments[2:],
            event,
            bot,
        )

    if subcommand != "quote" or len(arguments) < MIN_SUBCOMMAND_ARGUMENTS:
        await _finish_usage(event, bot)

    symbols = [symbol.upper() for symbol in arguments[1:]]
    await _handle_quotes(symbols, event, bot)
