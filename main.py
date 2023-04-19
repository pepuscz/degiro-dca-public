import logging
import os
import flask
import math
import time
import json
import functions_framework
from google_currency import convert
from degiro_connector.trading.models.trading_pb2 import ProductsInfo
from degiro_connector.trading.api import API as TradingAPI
from degiro_connector.trading.models.trading_pb2 import (
    Order,
    Credentials
)
from degiro_connector.quotecast.api import API as QuotecastAPI
from degiro_connector.quotecast.models.quotecast_pb2 import Quotecast
from helpers import (
    get_instrument_and_order_params,
    execute_orders,
    get_last_price,
    validate_environment_variables,
    is_user_token_valid
)

@functions_framework.http
def main(request):
    """
    Handle the main function for executing orders.

    :param request: Flask request object containing the incoming HTTP request
    :return: Flask response object containing the response message and status code
    """
    
    # Setup logging level
    logging.basicConfig(level=logging.DEBUG)
    quotecast_logger = logging.getLogger('degiro_connector.quotecast')
    quotecast_logger.setLevel(logging.WARNING)

    # Validate environment variables
    env_vars = ["DEGIRO_USERNAME", "DEGIRO_PASSWORD"]
    if not validate_environment_variables(env_vars):
        return flask.Response("Error: Missing or empty environment variables", status=500)

     # Setup config dict
    try:
        with open("config/config.json") as config_file:
            config_dict = json.load(config_file)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error("Error loading config.json: %s", e)
        return flask.Response("Error loading config.json", status=500)

    required_keys = ["account_currency", "conversion_currency"]
    if not all(key in config_dict for key in required_keys):
        logging.error("Error: config.json is missing required keys")
        return flask.Response("Error: config.json is missing required keys", status=500)

    # Setup credentials
    credentials = Credentials(
        username=os.environ.get("DEGIRO_USERNAME"),
        password=os.environ.get("DEGIRO_PASSWORD")
    )

    # Setup trading API
    trading_api = TradingAPI(credentials=credentials)

    # Establish connection
    try:
        trading_api.connect()
    except Exception as e:
        logging.error("Connection failed: %s", e)
        if "400 Client Error" in str(e):
            logging.error("Error: Invalid credentials. Please check DEGIRO_USERNAME and DEGIRO_PASSWORD environment variables.")
            return flask.Response("Error: Invalid credentials.", status=401)
        else:
            logging.error("Connection failed")
            return flask.Response("Connection failed", status=500)
        
    # Get user_token and int_account
    client_details_table = trading_api.get_client_details()
    user_token = client_details_table["data"]["id"]
    logging.debug("User token: %s", user_token)
    int_account = client_details_table["data"]["intAccount"]
    logging.debug("Int account: %s", int_account)

    # Set int_account in credentials
    credentials.int_account = int_account

    # Get instrument ID and order parameters
    order_params = get_instrument_and_order_params()

    if order_params is not None and order_params.execute_order is True:
        instrument_id = order_params.instrument_id
        step = order_params.step
        order_type = order_params.order_type
        order_price_target = order_params.order_price_target
    elif order_params.execute_order is False:
        return flask.Response("No orders executed", status=200)
    else:
        return flask.Response("Conversion failed", status=500)

    # Get last price
    last_price = get_last_price(trading_api, user_token, instrument_id)
    if last_price is not None:
        logging.info("Last price of %s is %.4f", instrument_id, last_price)
        order_size = math.floor(order_price_target / last_price)
        logging.info("Order size of %s is %s", instrument_id, order_size)
    else:
        return flask.Response("Error getting last price", status=500)

    # Execute orders
    if execute_orders(trading_api, instrument_id, step, order_type, order_size, user_token):
        return flask.Response("Order confirmed", status=200)
    else:
        return flask.Response("Error confirming order", status=500)