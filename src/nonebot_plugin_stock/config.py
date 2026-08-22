from nonebot import get_driver, get_plugin_config
from pydantic import BaseModel


class Config(BaseModel):
    """Longbridge 股票插件配置。"""

    longbridge_app_key: str | None = None
    longbridge_app_secret: str | None = None
    longbridge_access_token: str | None = None


plugin_config: Config = get_plugin_config(Config)
global_config = get_driver().config
NICKNAME: str = next(iter(global_config.nickname), "")
