"""快捷标的的规范化、持久化和匹配。"""

import asyncio
import json
from importlib import import_module

from nonebot import require
from nonebot.adapters import Event
from nonebot.adapters.onebot.v11 import MessageEvent
from nonebot.log import logger

from .constants import (
    POPULAR_STOCKS,
    QUICK_SYMBOLS_FILE,
    SYMBOL_PATTERN,
)

require("nonebot_plugin_localstore")
localstore = import_module("nonebot_plugin_localstore")
quick_symbols_lock = asyncio.Lock()


def normalize_symbol(symbol: str) -> str:
    """将用户输入转换为 Longbridge 标的格式。"""
    normalized = symbol.strip().upper()
    if "." not in normalized:
        return f"{normalized}.US"
    return normalized


def symbol_alias(symbol: str) -> str:
    """返回标的可直接输入的代码别名。"""
    return symbol.rsplit(".", maxsplit=1)[0].casefold()


def is_valid_symbol(symbol: str) -> bool:
    """判断标的是否符合 Longbridge 代码格式。"""
    return bool(SYMBOL_PATTERN.fullmatch(symbol))


def load_added_symbols() -> set[str]:
    """从插件数据目录读取用户添加的快捷标的。"""
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
        if isinstance(symbol, str) and is_valid_symbol(symbol)
    }


def save_added_symbols(symbols: set[str]) -> None:
    """将用户添加的快捷标的原子写入插件数据目录。"""
    path = localstore.get_plugin_data_file(QUICK_SYMBOLS_FILE)
    temporary_path = path.with_suffix(".tmp")
    temporary_path.write_text(
        json.dumps(sorted(symbols), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(path)


def get_quick_symbols() -> dict[str, str]:
    """返回快捷别名到 Longbridge 标的的映射。"""
    symbols = {alias.casefold(): symbol for alias, symbol in POPULAR_STOCKS.items()}
    for symbol in tuple(symbols.values()):
        symbols.setdefault(symbol.casefold(), symbol)

    for symbol in load_added_symbols():
        symbols[symbol.casefold()] = symbol
        symbols.setdefault(symbol_alias(symbol), symbol)
    return symbols


async def is_quick_stock(event: Event) -> bool:
    """判断事件是否为快捷标的查询。"""
    if not isinstance(event, MessageEvent):
        return False
    return event.get_plaintext().strip().casefold() in get_quick_symbols()


async def update_quick_symbols(
    raw_symbols: list[str], *, remove: bool
) -> tuple[list[str], list[str]]:
    """添加或删除快捷标的，并返回已变化和未变化的标的。"""
    normalized_symbols = [normalize_symbol(symbol) for symbol in raw_symbols]
    invalid_symbols = [
        symbol for symbol in normalized_symbols if not is_valid_symbol(symbol)
    ]
    if invalid_symbols:
        raise ValueError(", ".join(invalid_symbols))

    async with quick_symbols_lock:
        symbols = load_added_symbols()
        if remove:
            changed = [symbol for symbol in normalized_symbols if symbol in symbols]
            missing = [symbol for symbol in normalized_symbols if symbol not in symbols]
            symbols.difference_update(changed)
        else:
            changed = [symbol for symbol in normalized_symbols if symbol not in symbols]
            missing = [symbol for symbol in normalized_symbols if symbol in symbols]
            symbols.update(changed)
        if changed:
            save_added_symbols(symbols)
    return changed, missing


def format_quick_list(symbols: set[str]) -> str:
    """格式化快捷标的列表。"""
    if not symbols:
        return "当前没有已添加的快捷标的"

    lines = [f"已添加快捷标的（{len(symbols)}）："]
    lines.extend(
        f"{symbol}（可直接发送 {symbol_alias(symbol)}）" for symbol in sorted(symbols)
    )
    return "\n".join(lines)
