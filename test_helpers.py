import json
from datetime import datetime
from unittest.mock import patch
import pytest
import unittest.mock
from degiro_connector.trading.models.trading_pb2 import (
    Order
)

from helpers import get_instrument_and_order_params, OrderParams

def test_get_instrument_and_order_params_no_order(monkeypatch):
    def mock_json_load(*args, **kwargs):
        return {
            "instruments": {},
            "buy_amounts": {},
            "account_currency": "USD",
            "conversion_currency": "USD",
        }

    monkeypatch.setattr("json.load", mock_json_load)

    result = get_instrument_and_order_params()

    assert isinstance(result, OrderParams)
    assert result.execute_order is False

def test_get_instrument_and_order_params_same_currency():
    def mock_json_load(*args, **kwargs):
        return {
            "instruments": {"1": "123456"},
            "buy_amounts": {"1": "100"},
            "account_currency": "USD",
            "conversion_currency": "USD",
        }

    with unittest.mock.patch("helpers.current_datetime") as mock_current_datetime:
        mock_current_datetime.return_value = datetime(2023, 4, 1)

        with unittest.mock.patch("json.load", mock_json_load):
            result = get_instrument_and_order_params()
            expected_result = OrderParams("123456", Order.OrderType.LIMIT, 100.0, True)

            assert result == expected_result

@patch("helpers.convert")
def test_get_instrument_and_order_params_different_currency(mock_convert):
    def mock_json_load(*args, **kwargs):
        return {
            "instruments": {"1": "123456"},
            "buy_amounts": {"1": "100"},
            "account_currency": "EUR",
            "conversion_currency": "USD",
        }

    with unittest.mock.patch("helpers.current_datetime") as mock_current_datetime:
        mock_current_datetime.return_value = datetime(2023, 4, 1)

        with unittest.mock.patch("json.load", mock_json_load):
            mock_convert.return_value = json.dumps({"converted": True, "amount": "85.0"})
            result = get_instrument_and_order_params()
            expected_result = OrderParams("123456", Order.OrderType.LIMIT, 85.0, True)

            assert result == expected_result

def test_get_instrument_and_order_params_conversion_failed():
    def mock_json_load(*args, **kwargs):
        return {
            "instruments": {"1": "123456"},
            "buy_amounts": {"1": "100"},
            "account_currency": "EUR",
            "conversion_currency": "USD",
        }

    def mock_convert(*args, **kwargs):
        return json.dumps({"converted": False})

    with unittest.mock.patch("helpers.current_datetime") as mock_current_datetime:
        mock_current_datetime.return_value = datetime(2023, 4, 1)

        with unittest.mock.patch("json.load", mock_json_load):
            with unittest.mock.patch("helpers.convert", mock_convert):
                result = get_instrument_and_order_params()

                assert result is None
