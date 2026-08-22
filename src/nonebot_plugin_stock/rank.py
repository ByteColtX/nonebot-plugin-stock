"""榜单命令的参数解析。"""

from .constants import (
    RANK_ARGUMENTS_WITH_COUNT,
    RANK_ARGUMENTS_WITHOUT_COUNT,
    RANK_DEFAULT_COUNT,
    RANK_MARKETS,
    RANK_MAX_COUNT,
    RANK_TYPE_ALIASES,
    RANK_TYPES,
    TURNOVER_ARGUMENTS_WITH_COUNT,
    TURNOVER_ARGUMENTS_WITHOUT_COUNT,
    TURNOVER_MARKETS,
)
from .errors import RankArgumentError, RankUsageError


def parse_rank_arguments(arguments: list[str]) -> tuple[str, str, int]:
    """解析普通榜单的类型、市场和数量参数。"""
    if len(arguments) not in {
        RANK_ARGUMENTS_WITHOUT_COUNT,
        RANK_ARGUMENTS_WITH_COUNT,
    }:
        raise RankUsageError

    rank_type = RANK_TYPE_ALIASES.get(arguments[0].casefold())
    if rank_type is None:
        raise RankUsageError

    market = arguments[1].upper()
    if market not in RANK_MARKETS:
        raise RankArgumentError.market_required()

    _name, _key_prefix, supported_markets = RANK_TYPES[rank_type]
    if market not in supported_markets:
        raise RankArgumentError.unsupported_market(arguments[0], market)

    count = RANK_DEFAULT_COUNT
    if len(arguments) == RANK_ARGUMENTS_WITH_COUNT:
        if not arguments[2].isdigit():
            raise RankArgumentError.invalid_count()
        count = int(arguments[2])
    if not 1 <= count <= RANK_MAX_COUNT:
        raise RankArgumentError.invalid_count()
    return rank_type, market, count


def parse_turnover_arguments(arguments: list[str]) -> tuple[str, int]:
    """解析成交额榜的市场和数量参数。"""
    if len(arguments) not in {
        TURNOVER_ARGUMENTS_WITHOUT_COUNT,
        TURNOVER_ARGUMENTS_WITH_COUNT,
    }:
        raise RankUsageError

    market = arguments[0].upper()
    if market not in TURNOVER_MARKETS:
        raise RankArgumentError.turnover_market_required()

    count = RANK_DEFAULT_COUNT
    if len(arguments) == TURNOVER_ARGUMENTS_WITH_COUNT:
        if not arguments[1].isdigit():
            raise RankArgumentError.invalid_count()
        count = int(arguments[1])
    if not 1 <= count <= RANK_MAX_COUNT:
        raise RankArgumentError.invalid_count()
    return market, count
