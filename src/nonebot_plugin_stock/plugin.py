"""Longbridge 股票行情插件的 NoneBot 入口和命令处理。"""

from __future__ import annotations

import asyncio
from typing import Any, NoReturn

from nonebot import get_driver, on_command
from nonebot.adapters import Event, Message
from nonebot.adapters.onebot.v11 import (
    Bot,
    GroupMessageEvent,
    MessageSegment,
    PrivateMessageEvent,
)
from nonebot.adapters.onebot.v11.exception import ActionFailed, NetworkError
from nonebot.log import logger
from nonebot.params import CommandArg
from nonebot.plugin import on_message
from nonebot.rule import Rule

from . import client as longbridge_client
from . import formatters, providers
from . import rank as rank_commands
from . import symbols as symbol_store
from .client import OpenApiException
from .config import quote_source_keys, source_timeout
from .constants import (
    HELP_ARGUMENTS,
    LONGBRIDGE_USAGE_NODES,
    MIN_SUBCOMMAND_ARGUMENTS,
    QUOTE_SOURCE_LABELS,
    QUOTE_SOURCE_SHORT_LABELS,
    RANK_TYPES,
    SOURCE_USAGE_NODE,
    TURNOVER_ALIASES,
)
from .errors import (
    RankArgumentError,
    RankUsageError,
    StockConfigError,
    StockSourceConfigError,
    StockSourceError,
)

# handler 复用的领域异常别名，避免在命令处理代码中暴露实现模块。
_StockConfigError = StockConfigError
_RankUsageError = RankUsageError
_RankArgumentError = RankArgumentError

longbridge_command = on_command(
    "longbridge",
    aliases={"stock"},
    force_whitespace=True,
)

_quote_context_state = longbridge_client.QuoteContextState()
_http_client_state = longbridge_client.HttpClientState()
_oauth_state = longbridge_client.OAuthState()
_quote_context_lock = asyncio.Lock()
_http_client_lock = asyncio.Lock()
_oauth_lock = asyncio.Lock()
_oauth_task: asyncio.Task[None] | None = None


def _normalize_symbol(symbol: str) -> str:
    return symbol_store.normalize_symbol(symbol)


def _symbol_alias(symbol: str) -> str:
    return symbol_store.symbol_alias(symbol)


def _is_valid_symbol(symbol: str) -> bool:
    return symbol_store.is_valid_symbol(symbol)


def _sync_symbol_store() -> None:
    # 入口层持有 localstore 引用，数据模块只负责实际读写。
    symbol_store.localstore = localstore


localstore = symbol_store.localstore
QUICK_SYMBOLS_FILE = symbol_store.QUICK_SYMBOLS_FILE


def _load_added_symbols() -> set[str]:
    _sync_symbol_store()
    return symbol_store.load_added_symbols()


def _save_added_symbols(symbols: set[str]) -> None:
    _sync_symbol_store()
    symbol_store.save_added_symbols(symbols)


def _quick_symbols() -> dict[str, str]:
    _sync_symbol_store()
    return symbol_store.get_quick_symbols()


async def _is_quick_stock(event: Event) -> bool:
    _sync_symbol_store()
    return await symbol_store.is_quick_stock(event)


stock_quote = on_message(rule=Rule(_is_quick_stock))


def _get_config_value(name: str) -> str | None:
    return longbridge_client.get_config_value(name, get_driver().config)


def _is_oauth_auth() -> bool:
    return (
        longbridge_client.auth_method(_get_config_value)
        == longbridge_client.AUTH_METHOD_OAUTH
    )


def _report_oauth_url(url: str) -> None:
    """把 OAuth 授权链接和操作提示写入日志。"""
    logger.warning(f"Longbridge OAuth 授权链接：{url}")
    logger.warning("请在能访问本机回调端口的浏览器中打开该链接完成授权")


async def _authorize_oauth() -> Any:
    """启动 OAuth 2.0 浏览器授权流程并返回授权句柄。"""
    sdk = longbridge_client.require_sdk()
    client_id = longbridge_client.oauth_client_id(_get_config_value)
    if client_id is None:
        raise StockConfigError.oauth_client_id_missing()
    builder = sdk.OAuthBuilder(
        client_id,
        longbridge_client.oauth_callback_port(_get_config_value),
    )
    return await builder.build_async(_report_oauth_url)


async def _get_oauth() -> Any:
    return await longbridge_client.get_oauth(
        _oauth_state,
        _oauth_lock,
        _authorize_oauth,
    )


async def _warm_oauth_authorization() -> None:
    """在后台完成 OAuth 授权，避免首个行情请求被超时打断。"""
    try:
        await _get_oauth()
        logger.info("Longbridge OAuth 授权已就绪")
    except StockConfigError as error:
        logger.warning(f"Longbridge OAuth 授权未完成：{error}")
    except Exception as error:
        logger.warning(f"Longbridge OAuth 授权失败：{error}", exc_info=True)


@get_driver().on_startup
async def _start_oauth_authorization() -> None:
    global _oauth_task
    try:
        oauth_enabled = _is_oauth_auth()
    except StockConfigError as error:
        logger.warning(f"Longbridge 认证配置无效：{error}")
        return
    if not oauth_enabled:
        return
    if _oauth_task is None or _oauth_task.done():
        _oauth_task = asyncio.create_task(_warm_oauth_authorization())


@get_driver().on_shutdown
async def _stop_oauth_authorization() -> None:
    if _oauth_task is not None and not _oauth_task.done():
        _oauth_task.cancel()


async def _build_longbridge_config() -> Any:
    # 先确认 SDK 存在，否则用户会去配一份根本用不上的凭证。
    sdk = longbridge_client.require_sdk()
    if _is_oauth_auth():
        return sdk.Config.from_oauth(await _get_oauth())
    return longbridge_client.build_client(_get_config_value, sdk.Config.from_apikey)


async def _build_longbridge_http_client() -> Any:
    sdk = longbridge_client.require_sdk()
    if _is_oauth_auth():
        return sdk.HttpClient.from_oauth(await _get_oauth())
    return longbridge_client.build_client(_get_config_value, sdk.HttpClient.from_apikey)


async def _get_quote_context() -> Any:
    def create(config: Any, loop: asyncio.AbstractEventLoop) -> Any:
        sdk = longbridge_client.require_sdk()
        return sdk.AsyncQuoteContext.create(config, loop_=loop)

    return await longbridge_client.get_quote_context(
        _quote_context_state,
        _quote_context_lock,
        _build_longbridge_config,
        create,
    )


async def _get_http_client() -> Any:
    return await longbridge_client.get_http_client(
        _http_client_state,
        _http_client_lock,
        _build_longbridge_http_client,
    )


_format_decimal = formatters.format_decimal
_format_change = formatters.format_change
_format_timestamp = formatters.format_timestamp
_format_status = formatters.format_status
_get_market_info = formatters.get_market_info
_format_currency = formatters.format_currency
_format_quote = formatters.format_quote
_format_quotes = formatters.format_quotes
_format_rank_percent = formatters.format_rank_percent
_rank_symbol = formatters.rank_symbol
_rank_currency = formatters.rank_currency
_format_rank_amount = formatters.format_rank_amount
_format_rank_item = formatters.format_rank_item
_screener_indicator = formatters.screener_indicator
_screener_symbol = formatters.screener_symbol
_format_turnover_item = formatters.format_turnover_item
_format_rank_updated_at = formatters.format_rank_updated_at
_format_rank_categories = formatters.format_rank_categories
_rank_static_categories = formatters._format_static_categories


async def _query_rank_categories() -> object:
    client = await _get_http_client()
    return await client.request_async("get", "/v1/quote/market/rank/categories")


async def _query_rank_list(rank_type: str, market: str, count: int) -> object:
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
    return await client.request_async("post", "/v1/quote/ai/screener/search", body=body)


async def _handle_rank_categories(event: Event, bot: Bot) -> NoReturn:
    try:
        data = await _query_rank_categories()
    except StockConfigError as error:
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


_parse_turnover_arguments = rank_commands.parse_turnover_arguments
_parse_rank_arguments = rank_commands.parse_rank_arguments


async def _handle_turnover_command(
    arguments: list[str], event: Event, bot: Bot
) -> NoReturn:
    try:
        market, count = _parse_turnover_arguments(arguments)
    except RankUsageError:
        await _finish_usage(event, bot)
    except RankArgumentError as error:
        await longbridge_command.finish(f"❌ {error}")

    try:
        data = await _query_turnover_list(market, count)
    except StockConfigError as error:
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

    market_name = formatters.RANK_MARKET_NAMES[market]
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


async def _handle_rank_command(
    arguments: list[str], event: Event, bot: Bot
) -> NoReturn:
    if not arguments or arguments[0].casefold() in {"list", "categories"}:
        if len(arguments) > 1:
            await _finish_usage(event, bot)
        await _handle_rank_categories(event, bot)

    try:
        rank_type, market, count = _parse_rank_arguments(arguments)
    except RankUsageError:
        await _finish_usage(event, bot)
    except RankArgumentError as error:
        await longbridge_command.finish(f"❌ {error}")

    try:
        data = await _query_rank_list(rank_type, market, count)
    except StockConfigError as error:
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
    market_name = formatters.RANK_MARKET_NAMES[market]
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


async def _query_quotes(symbols: list[str]) -> providers.QuoteResult:
    config = get_driver().config
    timeout = source_timeout(config)
    chain = providers.build_providers(
        quote_source_keys(config),
        timeout=timeout,
        get_longbridge_context=_get_quote_context,
    )
    return await providers.fetch_quotes(chain, symbols, timeout=timeout)


def _symbol_error_lines(errors: list[providers.SymbolError]) -> str:
    return "\n".join(f"❌ {item.symbol}：{item.reason}" for item in errors)


def _source_failure_message(error: StockSourceError) -> str:
    lines = [str(error)]
    lines.extend(f"· {item.symbol}：{item.reason}" for item in error.symbol_errors)
    return "\n".join(lines)


def _source_usage_node() -> str:
    try:
        keys = quote_source_keys(get_driver().config)
        order = " → ".join(QUOTE_SOURCE_LABELS.get(key, key) for key in keys)
    except StockSourceConfigError:
        order = "配置无效，请检查 STOCK_QUOTE_SOURCES"
    return SOURCE_USAGE_NODE.format(order=order)


def _usage_nodes() -> tuple[str, ...]:
    return (*LONGBRIDGE_USAGE_NODES, _source_usage_node())


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
    nodes = _usage_nodes()
    await _finish_forward(
        event,
        bot,
        nodes,
        "\n\n".join(nodes),
        "Longbridge CLI",
    )


async def _handle_quotes(
    symbols: list[str],
    event: Event,
    bot: Bot,
    *,
    force_forward: bool = False,
) -> None:
    try:
        result = await _query_quotes(symbols)
    except StockConfigError as error:
        await longbridge_command.finish(str(error))
    except StockSourceConfigError as error:
        await longbridge_command.finish(f"❌ {error}")
    except StockSourceError as error:
        await longbridge_command.finish(_source_failure_message(error))

    quotes = result.quotes
    missing = _symbol_error_lines(result.symbol_errors)
    message = _format_quotes(quotes)
    if missing:
        message = f"{message}\n\n{missing}" if message else missing
    if force_forward or len(symbols) > 1:
        contents = tuple(_format_quote(quote) for quote in quotes)
        if missing:
            contents = (*contents, missing)
        await _finish_forward(
            event,
            bot,
            contents,
            message,
            QUOTE_SOURCE_SHORT_LABELS.get(result.provider_key, "行情"),
        )
    await longbridge_command.finish(message)


async def _update_quick_symbols(
    raw_symbols: list[str], *, remove: bool
) -> tuple[list[str], list[str]]:
    _sync_symbol_store()
    return await symbol_store.update_quick_symbols(raw_symbols, remove=remove)


_format_quick_list = symbol_store.format_quick_list


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
            f"✅ 已添加快捷标的：{', '.join(changed)}" if changed else "快捷标的已存在"
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


@stock_quote.handle()
async def handle_stock_quote(event: Event) -> None:
    keyword = event.get_plaintext().strip().casefold()
    symbol = _quick_symbols().get(keyword)
    if symbol is None:
        await stock_quote.finish(
            "暂不支持该快捷标的，请使用 /stock quote <代码.市场> 查询"
        )

    try:
        result = await _query_quotes([symbol])
    except StockConfigError as error:
        await stock_quote.finish(str(error))
    except StockSourceConfigError as error:
        await stock_quote.finish(f"❌ {error}")
    except StockSourceError as error:
        await stock_quote.finish(_source_failure_message(error))

    if not result.quotes:
        await stock_quote.finish(f"❌ 未获取到 {symbol} 的行情")
    await stock_quote.finish(_format_quote(result.quotes[0]))


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
