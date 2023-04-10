# DEGIRO DCA Trading Bot

This is a simple trading bot for DEGIRO that automates the process of buying assets on a monthly basis. The bot uses the [Degiro Connector](https://github.com/Chavithra/degiro-connector) and [Google currency](https://github.com/om06/google-currency) to fetch data and execute orders.
## Motivation
### Dollar Cost Averaging (DCA)

Dollar Cost Averaging (DCA) is an investment strategy where an investor divides the total amount to be invested across periodic purchases of a target asset in an effort to reduce the impact of volatility on the overall purchase. The key to this strategy is precise execution and low fees, which is the goal of this project.

### Why DEGIRO?

DEGIRO was selected as the broker for this trading bot for several reasons:

- Wide range of commission-free ETFs: DEGIRO offers a comprehensive list of commission-free ETFs, which can be found [here](https://www.degiro.cz/helpdesk/sites/cz/files/imported_files//commission_free_etfs.pdf).
- Automatic conversions to EUR: DEGIRO allows commission-free automatic conversions to EUR of deposits in other currencies. More information can be found [here](https://www.degiro.cz/helpdesk/orders/placing-order/why-can-i-not-purchase-shares-after-depositing-czk).

### Architecture

The bot is implemented as a cloud function using the [Functions Framework](https://github.com/GoogleCloudPlatform/functions-framework-python). It is executed when called by an HTTP request, providing a robust solution for running the bot.

There are two main deployment options for the bot:

1. **Local Deployment**: The bot can be deployed and run locally on your machine. This can be useful for testing or development purposes. The bot execution can be scheduled using tools such as cron.

2. **Cloud Deployment**: For production use, it is recommended to deploy the bot to a cloud environment, such as Google Cloud Platform (GCP). This ensures the bot can run efficiently and reliably, with execution scheduled by Cloud Scheduler.

To use the bot, you need to set up a configuration file with the desired instruments, budget, and schedule, as described in the Usage section. Once the configuration is in place, you can trigger the bot by sending a request to the cloud function. The bot will then execute the necessary purchases based on the current week and the user-defined configuration.

## Usage
The bot buys one user-defined instrument per week, periodically every month. So it can buy 0-4 instruments per month.

The logic behind this strategy is as follows:

1. **Configuration**: The user specifies the desired instrument for every week of the month and the budget for each instrument purchase in the configuration file.

2. **Schedule**: The bot is programmed to execute purchases on a weekly basis. It checks the current date and determines whether and what purchase should be made in the current week. However, the bot doesn't store any state. If called twice in the week, it executes two orders. It's the user's responsibility to call the bot, the intended period is exactly once per week. The week number is calculated as 7 days of the month (8th of a month = week 2).

3. **Purchase**: If it's time to execute a purchase, the bot will:
   a. Retrieve the latest price for the specified instrument using the Quotecast API from the Degiro trading platform.
   b. Calculate the whole number of shares (order size) to buy based on the user-defined budget and the current price of the instrument. The bot doesn't buy fraction shares, it rounds down to a whole number. The budget can be specified in the account currency (EUR), or custom (conversion) currency (for example CZK). In that case, the bot checks the current exchange rate before calculating the order size.
   c. Execute a limit order to buy the calculated number of shares, using the user's Degiro account.

### Example

Assume the user specifies the following configuration for February 2023:

- Week 1 (Feb 1 - Feb 7): Buy AAPL with a budget of 200 EUR
- Week 2 (Feb 8 - Feb 14): Buy MSFT with a budget of 200 EUR
- Week 3 (Feb 15 - Feb 21): Buy GOOGL with a budget of 500 EUR
- Week 4 (Feb 22 - Feb 28): Buy AMZN with a budget of 200 EUR

The bot will then execute the respective purchases each week, following the schedule and budget specified by the user. For example, in week 1, the bot will check the latest price of AAPL, calculate the whole number of shares to buy based on the 1000 EUR budget and execute a limit order to purchase the shares. The user has to call the bot once every week (for example, Mondays).

### Local Deployment

1. Install the required dependencies:

```
pip install -r requirements.txt
```

2. Set the required environment variables:

```bash
export DEGIRO_INT_ACCOUNT="your_int_account"
export DEGIRO_USERNAME="your_degiro_username"
export DEGIRO_PASSWORD="your_degiro_password"
export DEGIRO_USER_TOKEN="your_degiro_user_token"
```

3. Create a `config` directory in the project root and add a `config.json` file with the following structure:

```json

{
  "account_currency": "your_account_currency",
  "conversion_currency": "your_conversion_currency",
  "instruments": {
    "1": instrument_id_for_week_1,
    "2": instrument_id_for_week_2,
    "3": instrument_id_for_week_3,
    "4": instrument_id_for_week_4
  },
  "buy_amounts": {
    "1": buy_amount_for_week_1,
    "2": buy_amount_for_week_2,
    "3": buy_amount_for_week_3,
    "4": buy_amount_for_week_4
  }
}
```
Example configuration for purchase of iShares Core S&P 500 UCITS ETF USD (Acc) in the first week of the month with a budget 1000 EUR:
```json

{
  "account_currency": "eur",
  "conversion_currency": "",
  "instruments": {
    "1": 3234842
  },
  "buy_amounts": {
    "1": 1000
  }
}
```
Instrument (product_id) can be found for example in the URL when clicking on the product in the web app (https://trader.degiro.nl/trader/#/products/3234842/overview).

Example configuration for purchase of iShares Core S&P 500 UCITS ETF USD (Acc) in the first week of the month with a budget 20 000 CZK and purchase of Fidelity Funds - Global Technology Fund Y-ACC-EUR in the third week of the month with a budget 10 000 CZK.
```json

{
  "account_currency": "eur",
  "conversion_currency": "czk",
  "instruments": {
    "1": 3234842,
    "3": 5368166
  },
  "buy_amounts": {
    "1": 20000,
    "3": 10000
  }
}
```

4. Run the trading bot using the Functions Framework:

```bash
functions-framework --source=main.py --target=main --debug
```

5. Call the trading bot function:

```bash
curl -I http://localhost:8080
```

## Developer Documentation

The trading bot consists of the following files:

- `main.py`: Contains the main function for executing orders, which is responsible for connecting to the DeGiro API, getting instrument and order parameters, and executing orders.
- `helpers.py`: Contains helper functions for the trading bot, such as getting instrument and order parameters, executing orders, getting the last price of an instrument, and validating environment variables.
- `test_helpers.py`: Contains unit tests for the helper functions.
- `test_main.py`: Contains unit tests for the main functions.

The main function, `main`, in the `main.py` file starts by validating environment variables and loading the configuration from `config/config.json`. It then sets up the credentials and the trading API, and connects to the DeGiro API. After that, it gets the instrument and order parameters for the current week of the month, and executes the orders if required.

The `helpers.py` file provides helper functions for various tasks, such as getting the instrument and order parameters, executing orders, getting the last price of an instrument, and validating environment variables.

The `tests.py` file contains unit tests for the helper functions in the `helpers.py` file.

To modify or extend the trading bot, you can start by looking into the `main.py` and `helpers.py` files and making changes as needed. Make sure to update the unit tests accordingly.

## Disclaimer
This bot is provided for educational and informational purposes only. The authors and maintainers of this project are not responsible for any financial losses, damages, or any other negative consequences resulting from the use of this bot. Use at your own risk.