"""股票插件的领域异常。"""

from .constants import RANK_MARKETS


class StockConfigError(ValueError):
    """Longbridge 凭证未配置。"""

    def __init__(self) -> None:
        super().__init__(
            "未配置 Longbridge 凭证，请在 .env 中设置："
            "LONGBRIDGE_APP_KEY、LONGBRIDGE_APP_SECRET、"
            "LONGBRIDGE_ACCESS_TOKEN"
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
