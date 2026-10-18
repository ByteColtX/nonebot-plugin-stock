from types import SimpleNamespace

import pytest

from nonebot_plugin_stock.config import Config, quote_source_keys, source_timeout
from nonebot_plugin_stock.errors import StockSourceConfigError


def test_config_defaults_to_free_sources() -> None:
    config = Config()

    assert config.stock_quote_sources == ["tencent", "sina"]
    assert config.stock_source_timeout == 5.0


def test_config_splits_comma_separated_text() -> None:
    config = Config(stock_quote_sources="longbridge, tencent，sina")

    assert config.stock_quote_sources == ["longbridge", "tencent", "sina"]


def test_config_keeps_list_values() -> None:
    config = Config(stock_quote_sources=["sina"])

    assert config.stock_quote_sources == ["sina"]


def test_quote_source_keys_reads_driver_config() -> None:
    assert quote_source_keys(SimpleNamespace()) == ["tencent", "sina"]
    assert quote_source_keys(SimpleNamespace(stock_quote_sources=None)) == [
        "tencent",
        "sina",
    ]
    assert quote_source_keys(SimpleNamespace(stock_quote_sources="Sina, Tencent")) == [
        "sina",
        "tencent",
    ]
    assert quote_source_keys(SimpleNamespace(stock_quote_sources=("tencent", " "))) == [
        "tencent"
    ]


def test_quote_source_keys_rejects_empty_values() -> None:
    with pytest.raises(StockSourceConfigError, match="不能为空"):
        quote_source_keys(SimpleNamespace(stock_quote_sources=""))
    with pytest.raises(StockSourceConfigError, match="不能为空"):
        quote_source_keys(SimpleNamespace(stock_quote_sources=[]))
    with pytest.raises(StockSourceConfigError, match="不能为空"):
        quote_source_keys(SimpleNamespace(stock_quote_sources=42))


def test_source_timeout_defaults_and_clamps() -> None:
    assert source_timeout(SimpleNamespace()) == 5.0
    assert source_timeout(SimpleNamespace(stock_source_timeout="8")) == 8.0
    assert source_timeout(SimpleNamespace(stock_source_timeout="abc")) == 5.0
    assert source_timeout(SimpleNamespace(stock_source_timeout=0)) == 0.5
    assert source_timeout(SimpleNamespace(stock_source_timeout=999)) == 30.0
