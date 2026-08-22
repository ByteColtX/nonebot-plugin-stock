"""行情和榜单的消息格式化。"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, DecimalException
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from .constants import (
    COUNTER_ID_PARTS_MIN,
    LOCAL_TIMEZONE,
    MARKET_INFO,
    RANK_MARKET_NAMES,
    RANK_TYPES,
)

if TYPE_CHECKING:
    from longbridge.openapi import SecurityQuote


def format_decimal(value: object, places: int = 2, *, signed: bool = False) -> str:
    """格式化数值，必要时添加正号和千位分隔符。"""
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


def format_change(last_done: object, prev_close: object) -> tuple[str, str]:
    """计算并格式化涨跌额和涨跌幅。"""
    try:
        change = Decimal(str(last_done)) - Decimal(str(prev_close))
        previous = Decimal(str(prev_close))
        if not previous:
            return format_decimal(change, signed=True), "-"
        percent = change / previous * 100
    except (DecimalException, TypeError, ValueError):
        return "-", "-"
    return format_decimal(change, signed=True), format_decimal(
        percent, signed=True
    ) + "%"


def format_timestamp(value: object) -> str:
    """将行情时间格式化为东八区时间。"""
    if not isinstance(value, datetime):
        return str(value or "-")
    if value.tzinfo is None:
        # Longbridge 的报价时间虽然没有 tzinfo，但已经是东八区时间。
        value = value.replace(tzinfo=LOCAL_TIMEZONE)
    formatted = value.astimezone(LOCAL_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")
    return f"{formatted} (GMT+8)"


def format_status(value: object) -> str:
    """格式化 Longbridge 交易状态枚举。"""
    return str(getattr(value, "__name__", value)).rsplit(".", 1)[-1]


def get_market_info(symbol: object) -> tuple[str, str]:
    """返回标的对应的市场名称和货币。"""
    symbol_text = str(symbol or "").upper()
    market_code = symbol_text.rsplit(".", maxsplit=1)[-1]
    return MARKET_INFO.get(
        market_code,
        (f"未知市场（{market_code or '-'}）", ""),
    )


def format_currency(value: object, currency: str) -> str:
    """格式化带货币单位的数值。"""
    formatted = format_decimal(value)
    return f"{formatted} {currency}" if currency else formatted


def format_quote(quote: SecurityQuote) -> str:
    """格式化一条 Longbridge 实时行情。"""
    market, currency = get_market_info(quote.symbol)
    change, change_percent = format_change(
        quote.last_done,
        quote.prev_close,
    )
    return "\n".join(
        [
            f"标的：{quote.symbol}",
            f"市场：{market}",
            f"最新价：{format_currency(quote.last_done, currency)}",
            f"涨跌额：{format_currency(change, currency)}",
            f"涨跌幅：{change_percent}",
            f"昨收：{format_currency(quote.prev_close, currency)}",
            f"开盘：{format_currency(quote.open, currency)}",
            f"最高：{format_currency(quote.high, currency)}",
            f"最低：{format_currency(quote.low, currency)}",
            f"成交量：{quote.volume:,}",
            f"成交额：{format_currency(quote.turnover, currency)}",
            f"交易状态：{format_status(quote.trade_status)}",
            f"更新时间：{format_timestamp(quote.timestamp)}",
            "数据源：Longbridge OpenAPI",
        ]
    )


def format_quotes(quotes: list[SecurityQuote]) -> str:
    """格式化多条 Longbridge 实时行情。"""
    return "\n\n".join(format_quote(quote) for quote in quotes)


def format_rank_percent(value: object, *, signed: bool = True) -> str:
    """格式化以小数表示的榜单百分比。"""
    if value is None or value == "":
        return "-"
    try:
        percent = Decimal(str(value)) * 100
    except (DecimalException, TypeError, ValueError):
        return str(value)
    return f"{format_decimal(percent, signed=signed)}%"


def rank_symbol(item: dict[str, object], fallback_market: str) -> str:
    """从榜单项中提取标准标的代码。"""
    code = str(item.get("code") or "-")
    market = str(item.get("market") or fallback_market).upper()
    return f"{code}.{market}"


def rank_currency(market: str) -> str:
    """返回榜单市场对应的货币代码。"""
    return {
        "US": "USD",
        "HK": "HKD",
        "CN": "CNY",
        "SG": "SGD",
    }.get(market, "")


def format_rank_amount(value: object, market: str) -> str:
    """格式化榜单金额。"""
    currency = rank_currency(market)
    formatted = format_decimal(value)
    return f"{formatted} {currency}" if currency else formatted


def format_rank_item(item: dict[str, object], rank: int, fallback_market: str) -> str:
    """格式化一个市场热度榜单项。"""
    symbol = rank_symbol(item, fallback_market)
    market = str(item.get("market") or fallback_market).upper()
    return "\n".join(
        [
            f"{rank}. {symbol}  {item.get('name') or '-'}",
            f"最新价：{format_rank_amount(item.get('last_done'), market)}",
            f"涨跌额：{format_rank_amount(item.get('change'), market)}",
            f"涨跌幅：{format_rank_percent(item.get('chg'))}",
            f"成交额：{format_rank_amount(item.get('total_amount'), market)}",
            f"换手率：{format_rank_percent(item.get('turnover_rate'), signed=False)}",
            f"量比：{format_decimal(item.get('volume_rate'))}",
        ]
    )


def screener_indicator(item: dict[str, object], key: str) -> object:
    """从筛选器结果中取指定指标。"""
    indicators = item.get("indicators")
    if not isinstance(indicators, list):
        return None
    for indicator in indicators:
        if isinstance(indicator, dict) and indicator.get("key") == key:
            return indicator.get("value")
    return None


def screener_symbol(item: dict[str, object], fallback_market: str) -> str:
    """从筛选器结果的 counter_id 中提取标准标的代码。"""
    counter_id = str(item.get("counter_id") or "")
    parts = counter_id.split("/")
    if len(parts) >= COUNTER_ID_PARTS_MIN:
        return f"{parts[-1]}.{parts[-2]}"
    return rank_symbol(item, fallback_market)


def format_turnover_item(item: dict[str, object], rank: int, market: str) -> str:
    """格式化一个成交额榜单项。"""
    symbol = screener_symbol(item, market)
    price = format_rank_amount(screener_indicator(item, "filter_prevclose"), market)
    change_percent = format_decimal(
        screener_indicator(item, "filter_prevchg"), signed=True
    )
    turnover = format_rank_amount(screener_indicator(item, "filter_balance"), market)
    return "\n".join(
        [
            f"{rank}. {symbol}  {item.get('name') or '-'}",
            f"最新价：{price}",
            f"涨跌幅：{change_percent}%",
            f"最新成交额：{turnover}",
        ]
    )


def format_rank_updated_at(value: object) -> str:
    """格式化榜单更新时间戳。"""
    if value in (None, ""):
        return "-"
    try:
        timestamp = float(str(value))
        updated_at = datetime.fromtimestamp(timestamp, tz=ZoneInfo("UTC"))
    except (OSError, OverflowError, TypeError, ValueError):
        return str(value)
    return format_timestamp(updated_at)


def format_rank_categories(data: object) -> str:
    """格式化 Longbridge 动态榜单分类。"""
    if not isinstance(data, dict):
        return _format_static_categories()

    first_tags = data.get("first_tags")
    if not isinstance(first_tags, list) or not first_tags:
        return _format_static_categories()

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


def _format_static_categories() -> str:
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
