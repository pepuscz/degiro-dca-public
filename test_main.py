from main import main
from flask import Request
from unittest.mock import MagicMock
from degiro_connector.trading.api import API

def test_main_no_config(monkeypatch):
    def mock_open(*args, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr("builtins.open", mock_open)

    request = Request.from_values()
    response = main(request)

    assert response.status_code == 500
    assert response.data.decode("utf-8") == "Error loading config.json"

def test_invalid_credentials(monkeypatch):
    def mock_login(*args, **kwargs):
        raise Exception("400 Client Error: Bad Request for url: https://trader.degiro.nl/login/secure/login")

    # Temporarily set invalid environment variables for the test
    monkeypatch.setenv("DEGIRO_USERNAME", "invalid_username")
    monkeypatch.setenv("DEGIRO_PASSWORD", "invalid_password")
    
    # Create a MagicMock object with a mocked login method
    mocked_api = MagicMock(spec=API)
    mocked_api.login = MagicMock(side_effect=mock_login)
    
    # Replace the real API object with the MagicMock object
    monkeypatch.setattr("degiro_connector.trading.api.API", lambda *args, **kwargs: mocked_api)

    request = Request.from_values()
    response = main(request)

    assert response.status_code == 401
    assert response.data.decode("utf-8") == "Error: Invalid credentials."