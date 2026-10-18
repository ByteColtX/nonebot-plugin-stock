from unittest.mock import Mock

import pytest

from nonebot_plugin_stock import client as longbridge_client
from nonebot_plugin_stock.errors import StockConfigError, StockSdkMissingError


@pytest.fixture(autouse=True)
def clear_sdk_cache():
    """每个用例前后都清掉 SDK 探测缓存。"""
    longbridge_client.load_sdk.cache_clear()
    yield
    longbridge_client.load_sdk.cache_clear()


def test_load_sdk_returns_module_when_available() -> None:
    sdk = longbridge_client.load_sdk()

    assert sdk is not None
    assert longbridge_client.require_sdk() is sdk
    assert issubclass(longbridge_client.OpenApiException, Exception)


def test_load_sdk_returns_none_when_sdk_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        longbridge_client, "import_module", Mock(side_effect=ImportError)
    )

    assert longbridge_client.load_sdk() is None
    assert longbridge_client.load_sdk() is None
    with pytest.raises(StockSdkMissingError, match="未安装 longbridge SDK"):
        longbridge_client.require_sdk()


def test_openapi_exception_falls_back_to_placeholder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        longbridge_client, "import_module", Mock(side_effect=ImportError)
    )

    assert longbridge_client._openapi_exception() is longbridge_client.MissingSdkError


def test_build_client_rejects_missing_credentials() -> None:
    with pytest.raises(StockConfigError, match="未配置 Longbridge 凭证"):
        longbridge_client.build_client(lambda _name: None, lambda **_: object())
