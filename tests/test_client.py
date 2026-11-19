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


def test_auth_method_defaults_to_apikey() -> None:
    assert longbridge_client.auth_method(lambda _name: None) == "apikey"
    assert longbridge_client.auth_method(lambda _name: "API_KEY") == "apikey"
    assert longbridge_client.auth_method(lambda _name: "oauth") == "oauth"
    assert longbridge_client.auth_method(lambda _name: "OAuth2") == "oauth"


def test_auth_method_rejects_unknown_values() -> None:
    with pytest.raises(StockConfigError, match="未知的 Longbridge 认证方式"):
        longbridge_client.auth_method(lambda _name: "token")


def test_auth_method_auto_prefers_oauth_when_client_id_configured() -> None:
    def get_value(name: str) -> str | None:
        return {"longbridge_oauth_client_id": "client-id"}.get(name)

    assert longbridge_client.auth_method(get_value) == "oauth"


def test_auth_method_explicit_value_overrides_auto_detection() -> None:
    def get_value(name: str) -> str | None:
        return {
            "longbridge_oauth_client_id": "client-id",
            "longbridge_auth_method": "apikey",
        }.get(name)

    assert longbridge_client.auth_method(get_value) == "apikey"


def test_oauth_config_reads_client_id_and_clamps_port() -> None:
    def get_value(name: str) -> str | None:
        return {"longbridge_oauth_client_id": "client-id"}.get(name)

    assert longbridge_client.oauth_client_id(get_value) == "client-id"
    assert longbridge_client.oauth_callback_port(get_value) == 60355

    def port(raw: str | None):
        return lambda _name: raw

    assert longbridge_client.oauth_callback_port(port("60400")) == 60400
    assert longbridge_client.oauth_callback_port(port("abc")) == 60355
    assert longbridge_client.oauth_callback_port(port("0")) == 1
    assert longbridge_client.oauth_callback_port(port("99999")) == 65535
