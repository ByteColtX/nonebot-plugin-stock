"""股票插件使用的常量和帮助信息。"""

import re
from zoneinfo import ZoneInfo

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
QUOTE_SOURCE_LABELS = {
    "longbridge": "Longbridge OpenAPI",
    "tencent": "腾讯行情（免费源，可能延迟）",
    "sina": "新浪行情（免费源，可能延迟）",
}
QUOTE_SOURCE_KEYS = tuple(QUOTE_SOURCE_LABELS)
QUOTE_SOURCE_SHORT_LABELS = {
    "longbridge": "Longbridge 行情",
    "tencent": "腾讯行情",
    "sina": "新浪行情",
}
DEFAULT_QUOTE_SOURCES = ("tencent", "sina")
DEFAULT_SOURCE_TIMEOUT = 5.0
MIN_SOURCE_TIMEOUT = 0.5
MAX_SOURCE_TIMEOUT = 30.0
SOURCE_USAGE_NODE = """Data sources:
  行情：{order}
  榜单：Longbridge OpenAPI（需要 LONGBRIDGE_* 凭证）
  调整：.env 中的 STOCK_QUOTE_SOURCES（逗号分隔，按优先级排列）
"""
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
