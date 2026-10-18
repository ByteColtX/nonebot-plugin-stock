"""股票插件的领域异常。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .constants import QUOTE_SOURCE_KEYS, RANK_MARKETS

if TYPE_CHECKING:
    from .providers.base import SymbolError


class StockConfigError(ValueError):
    """Longbridge 凭证未配置。"""

    def __init__(self) -> None:
        super().__init__(
            "未配置 Longbridge 凭证，请在 .env 中设置："
            "LONGBRIDGE_APP_KEY、LONGBRIDGE_APP_SECRET、"
            "LONGBRIDGE_ACCESS_TOKEN"
        )


class StockSourceConfigError(ValueError):
    """行情数据源配置无效。"""

    @classmethod
    def empty(cls) -> "StockSourceConfigError":
        return cls("行情数据源列表不能为空，请检查 STOCK_QUOTE_SOURCES")

    @classmethod
    def unknown(cls, names: list[str]) -> "StockSourceConfigError":
        return cls(
            f"未知的行情数据源：{'、'.join(names)}"
            f"（可选：{'、'.join(QUOTE_SOURCE_KEYS)}）"
        )


class StockSourceError(RuntimeError):
    """所有行情数据源均不可用。"""

    def __init__(
        self,
        attempted: list[str],
        symbol_errors: tuple["SymbolError", ...] = (),
    ) -> None:
        self.attempted = tuple(attempted)
        self.symbol_errors = symbol_errors
        super().__init__(
            f"❌ 行情数据源均不可用（已尝试：{'、'.join(self.attempted)}），请稍后再试"
        )


class RankUsageError(ValueError):
    """榜单命令参数不符合用法。"""


class RankArgumentError(ValueError):
    """榜单命令参数值无效。"""

    @classmethod
    def market_required(cls) -> "RankArgumentError":
        return cls(f"榜单市场必须是：{' | '.join(sorted(RANK_MARKETS))}")

    @classmethod
    def turnover_market_required(cls) -> "RankArgumentError":
        return cls("成交额榜市场必须是：US | HK | CN")

    @classmethod
    def unsupported_market(cls, rank_type: str, market: str) -> "RankArgumentError":
        return cls(f"榜单类型 {rank_type} 不支持市场 {market}")

    @classmethod
    def invalid_count(cls) -> "RankArgumentError":
        return cls("榜单数量必须是 1-50 的整数")
