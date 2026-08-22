import os
import sys
import types
from pathlib import Path

import nonebot
import pytest
from nonebot.adapters.onebot.v11 import Adapter as OnebotV11Adapter
from pytest_asyncio import is_async_test

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


try:
    import longbridge.openapi  # noqa: F401
except Exception:
    # longbridge 0.2.74 没有适用于 Apple Silicon 的 wheel，测试不应因此依赖
    # 本机架构。插件只需要这些类型作为 SDK 边界，实际请求均由测试 mock。
    class _OpenApiException(Exception):
        pass

    class _AsyncQuoteContext:
        @classmethod
        def create(cls, *_args, **_kwargs):
            return cls()

        async def quote(self, _symbols):
            return []

    class _Config:
        @classmethod
        def from_apikey(cls, **kwargs):
            return kwargs

    class _HttpClient:
        @classmethod
        def from_apikey(cls, **kwargs):
            return kwargs

        async def request_async(self, *_args, **_kwargs):
            return {}

    longbridge_module = types.ModuleType("longbridge")
    openapi_module = types.ModuleType("longbridge.openapi")
    openapi_module.AsyncQuoteContext = _AsyncQuoteContext
    openapi_module.Config = _Config
    openapi_module.HttpClient = _HttpClient
    openapi_module.OpenApiException = _OpenApiException
    longbridge_module.openapi = openapi_module
    sys.modules["longbridge"] = longbridge_module
    sys.modules["longbridge.openapi"] = openapi_module

if Path(".env.dev").exists():
    os.environ["ENVIRONMENT"] = "dev"
else:
    os.environ["ENVIRONMENT"] = "test"

nonebot.init()


def pytest_collection_modifyitems(items: list[pytest.Item]):
    pytest_asyncio_tests = (item for item in items if is_async_test(item))
    session_scope_marker = pytest.mark.asyncio(loop_scope="session")
    for async_test in pytest_asyncio_tests:
        async_test.add_marker(session_scope_marker, append=False)


@pytest.fixture(scope="session", autouse=True)
def initialize_nonebot():
    """为直接调用 matcher handler 的测试注册 OneBot 适配器。"""
    driver = nonebot.get_driver()
    driver.register_adapter(OnebotV11Adapter)
