from nonebot.plugin import PluginMetadata

from .config import Config

__plugin_meta__ = PluginMetadata(
    name="Longbridge 股票行情",
    description="使用 Longbridge OpenAPI 查询股票行情",
    usage="/stock quote AAPL.US",
    type="application",
    homepage="https://github.com/ByteColtX/nonebot-plugin-stock",
    config=Config,
    supported_adapters={"~onebot.v11"},
    extra={"author": "ByteColtX <umk@live.com>"},
)

from . import plugin as plugin
