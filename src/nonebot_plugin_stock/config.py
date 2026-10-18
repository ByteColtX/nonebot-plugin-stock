"""股票插件配置读取。"""

from __future__ import annotations

import json
import re

from pydantic import BaseModel, field_validator

from .constants import (
    DEFAULT_QUOTE_SOURCES,
    DEFAULT_SOURCE_TIMEOUT,
    MAX_SOURCE_TIMEOUT,
    MIN_SOURCE_TIMEOUT,
)
from .errors import StockSourceConfigError

SOURCE_SEPARATORS = re.compile(r"[,，\s]+")


class Config(BaseModel):
    """股票插件配置。"""

    longbridge_app_key: str | None = None
    longbridge_app_secret: str | None = None
    longbridge_access_token: str | None = None
    stock_quote_sources: list[str] = list(DEFAULT_QUOTE_SOURCES)
    stock_source_timeout: float = DEFAULT_SOURCE_TIMEOUT

    @field_validator("stock_quote_sources", mode="before")
    @classmethod
    def _split_sources(cls, value: object) -> object:
        """把逗号分隔的配置文本拆成列表。"""
        if value is None:
            return list(DEFAULT_QUOTE_SOURCES)
        if isinstance(value, str):
            return split_source_text(value)
        return value


def split_source_text(value: str) -> list[str]:
    """把数据源配置文本拆成列表。

    同时接受逗号/空白分隔（`tencent,sina`）和 JSON 数组
    （`["tencent","sina"]`）两种写法。
    """
    text = value.strip()
    if text.startswith("[") and text.endswith("]"):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    return [
        item.strip().strip("\"'")
        for item in SOURCE_SEPARATORS.split(text)
        if item.strip().strip("\"'")
    ]


def quote_source_keys(config: object) -> list[str]:
    """读取行情数据源优先级列表。

    Args:
        config: NoneBot 配置对象。

    Returns:
        小写的数据源键列表，第一个为主源；未配置时使用默认顺序。

    Raises:
        StockSourceConfigError: 配置存在但解析不出任何数据源。
    """
    raw = getattr(config, "stock_quote_sources", None)
    if raw is None:
        return list(DEFAULT_QUOTE_SOURCES)
    if isinstance(raw, str):
        keys = split_source_text(raw)
    elif isinstance(raw, (list, tuple)):
        keys = [str(item).strip() for item in raw if str(item).strip()]
    else:
        keys = []
    if not keys:
        raise StockSourceConfigError.empty()
    return [key.casefold() for key in keys]


def source_timeout(config: object) -> float:
    """读取单个数据源的超时秒数，并限制在合理区间内。

    Args:
        config: NoneBot 配置对象。

    Returns:
        超时秒数；配置无效时回退到默认值。
    """
    raw = getattr(config, "stock_source_timeout", None)
    if raw is None:
        return DEFAULT_SOURCE_TIMEOUT
    try:
        timeout = float(str(raw).strip())
    except (TypeError, ValueError):
        return DEFAULT_SOURCE_TIMEOUT
    return min(max(timeout, MIN_SOURCE_TIMEOUT), MAX_SOURCE_TIMEOUT)
