import logging
import json
import time
import datetime
import math
import os
from collections import namedtuple
from google_currency import convert
from degiro_connector.trading.api import API as TradingAPI
from degiro_connector.trading.models.trading_pb2 import (
    Order
)
from degiro_connector.quotecast.api import API as QuotecastAPI
from degiro_connector.quotecast.models.quotecast_pb2 import Quotecast
from degiro_connector.trading.models.trading_pb2 import ProductsInfo

OrderParams = namedtuple("OrderParams", ["instrument_id", "step", "order_type", "order_price_target", "execute_order"])
"""
A namedtuple representing the order parameters for a given instrument.

Attributes:
    instrument_id (int): The DeGiro instrument ID.
    step (int): Order step.
    order_type (Order.OrderType): The type of the order (e.g., Order.OrderType.LIMIT).
    order_price_target (float): The target cash amount for the order.
    execute_order (bool): Whether to execute the order or not.
"""

def get_instrument_and_order_params():
    """
    Returns the instrument ID and order parameters for the current week of the month.

    :return: namedtuple OrderParams containing instrument_id, step, order_type,
             order_price_target, and execute_order
    """

    # Determine week of the month
    day_of_the_month = int(current_datetime().strftime("%d"))
    week_of_month = (day_of_the_month - 1) // 7 + 1

    # Get instrument ID and order parameters from config
    with open("config/config.json") as config_file:
        config_dict = json.load(config_file)

    instruments = config_dict.get("instruments")
    buy_amounts = config_dict.get("buy_amounts")
    account_currency = config_dict.get("account_currency")
    conversion_currency = config_dict.get("conversion_currency")

    instrument_id = instruments.get(str(week_of_month), None)
    amount_to_buy = buy_amounts.get(str(week_of_month), None)

    if instrument_id is None or amount_to_buy is None:
        logging.info("No orders executed for week %d of the month", week_of_month)
        return OrderParams(None,None,None,None,False)

    if account_currency == conversion_currency or conversion_currency is None:
        return OrderParams(instrument_id, -1, Order.OrderType.LIMIT, float(amount_to_buy),True)
    else:
        conversion_str = convert(conversion_currency, account_currency, amount_to_buy)
        conversion_dict = json.loads(conversion_str)

        if conversion_dict.get('converted'):
            return OrderParams(instrument_id, -1, Order.OrderType.LIMIT, float(conversion_dict.get('amount')), True)
        else:
            logging.error("Conversion failed for week %d and instrument ID %s", week_of_month, instrument_id)
            return None

def execute_orders(trading_api, instrument_id, step, order_type, order_size, user_token):
    """
    Execute orders for the specified instrument ID and order parameters.

    :param trading_api: TradingAPI instance for connecting to the DeGiro API
    :param instrument_id: DeGiro instrument ID
    :param step: Order step
    :param order_type: Order type (e.g., Order.OrderType.LIMIT)
    :param order_size: Order size (number of shares)
    :param user_token: DeGiro user token for authentication
    :return: True if the order was successfully confirmed, False otherwise
    """

    # Sleep 2 seconds
    time.sleep(2)

    # Setup order
    order = Order(
        action=Order.Action.BUY,
        order_type=order_type,
        price=get_last_price(trading_api, user_token, instrument_id),
        product_id=instrument_id,
        size=order_size,
        time_type=Order.TimeType.GOOD_TILL_CANCELED
    )

    # Log order
    logging.info("Ordering instrument %d, size %d, price %.4f", order.product_id, order.size, order.price)

    # Fetch checking response
    checking_response = trading_api.check_order(order=order)
    if checking_response is None:
        logging.error("Error checking order, probably not enough cash")
        return False

    # Extract confirmation ID
    confirmation_id = checking_response.confirmation_id

    # Send confirmation request
    confirmation_response = trading_api.confirm_order(
        confirmation_id=confirmation_id, order=order
    )
    if confirmation_response is None:
        logging.error("Error confirming order")
        return False

    logging.info("Order of instrument %d, size %d confirmed", instrument_id, order_size)
    return True

def get_last_price(trading_api, user_token, instrument_id):
    """
    Return the last price for the specified instrument ID.

    :param trading_api: TradingAPI instance for connecting to the DeGiro API
    :param user_token: DeGiro user token for authentication
    :param instrument_id: DeGiro instrument ID
    :return: Last price of the specified instrument or None if an error occurred
    """

    # Make request to get product information
    request = ProductsInfo.Request()
    logging.info("Getting product information for instrument ID %i", instrument_id)
    request.products.extend([instrument_id])
    products_info = trading_api.get_products_info(request=request, raw=True)

    # Check if product information was retrieved successfully
    if products_info is None:
        logging.error("Error getting product information for instrument ID %s", instrument_id)
        return None
    if "data" not in products_info:
        logging.error("Error getting product data for instrument ID %s", instrument_id)
        return None
    if str(instrument_id) not in products_info["data"]:
        logging.error("Error getting instrument for instrument ID %s", instrument_id)
        return None

    # Get vwdId for product
    vwd_id = products_info["data"][str(instrument_id)]["vwdId"]

    # Initialize QuotecastAPI and make request for last price
    quotecast_api = QuotecastAPI(user_token=user_token)
    request = Quotecast.Request()
    request.subscriptions[vwd_id].extend([
        'LastDate',
        'LastTime',
        'LastPrice'
    ])

    # Try to fetch ticker data, and handle any exceptions
    try:
        ticker_dict = quotecast_api.fetch_metrics(request=request)
    except Exception as e:
        logging.error("Error fetching ticker data for vwdId %s: %s", vwd_id, e)
        return None

    # Check if ticker data was retrieved successfully
    if ticker_dict is None:
        logging.error("Error getting ticker data for vwdId %s", vwd_id)
        return None
    elif vwd_id not in ticker_dict:
        logging.error("Error getting ticker data for vwdId %s", vwd_id)
        return None
    else:
        last_price = ticker_dict[vwd_id]["LastPrice"]

    # Return last price
    return last_price

def validate_environment_variables(variables):
    """
    Check if environment variables are not empty.

    :param variables: List of environment variable names to validate
    :return: True if all environment variables are set and not empty, False otherwise
    """

    for var in variables:
        if not os.environ.get(var):
            logging.error("Environment variable %s is not set or empty", var)
            return False
    return True

def current_datetime():
    """
    Return the current datetime, for mocking.
    """
    return datetime.datetime.now()

def is_user_token_valid(user_token):
    """
    Check if the provided user_token is valid by making a request to the Quotecast API.

    Args:
        user_token (int): The user token to validate.

    Returns:
        bool: True if the user token is valid, False otherwise.
    """
    try:
        quotecast_api = QuotecastAPI(user_token=user_token)

        # Build sample request
        request = Quotecast.Request()
        request.subscriptions["AAPL.BATS,E"].extend(
            [
                "LastPrice"
            ]
        )
        _ = quotecast_api.fetch_metrics(request=request)
        return True
    except Exception as e:
        logging.error("Error fetching from Quotecast API, probably wrong DEGIRO_USER_TOKEN")
        return False
