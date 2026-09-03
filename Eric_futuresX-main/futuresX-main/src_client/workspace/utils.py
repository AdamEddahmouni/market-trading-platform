from datetime import date, timedelta
from ibapi.client import *
from ibapi.wrapper import *

def get_third_friday(year: int, month: int) -> date:
    """
    Returns the date of the third Friday for a given month and year.
    """
    # Start from the 15th and go forward to find Friday
    d = date(year, month, 15)
    while d.weekday() != 4:  # 4 = Friday
        d += timedelta(days=1)
    return d

def get_latest_index_futures_expiry(symbol: str) -> str:
    """
    Returns the latest ES/NQ contract code in YYYYMM format as a string.
    Ex: Today is 5/14/2025, returns "202506" which is the June 2025 contract
    """
    today = date.today()
    year = today.year
    month = today.month

    # Identify nearest contract month
    if month <= 3:
        expiry_month = 3
    elif month <= 6:
        expiry_month = 6
    elif month <= 9:
        expiry_month = 9
    else:
        expiry_month = 12

    expiry_year = year
    # Get third Friday of the identified expiry month
    third_friday = get_third_friday(expiry_year, expiry_month)

    # If today is on or after the third Friday, roll to next contract
    if today >= third_friday:
        if expiry_month == 3:
            expiry_month = 6
        elif expiry_month == 6:
            expiry_month = 9
        elif expiry_month == 9:
            expiry_month = 12
        else:  # expiry_month == 12
            expiry_month = 3
            expiry_year += 1

    return f"{expiry_year}{expiry_month:02d}"

def get_latest_futures_contract(symbol: str) -> Contract:
    """
    Returns the latest futures contract as a Contract object
    """

    contract = Contract()
    contract.symbol = symbol
    contract.secType = "FUT"
    contract.currency = "USD"
    contract.exchange = "CME" 
    contract.lastTradeDateOrContractMonth = get_latest_index_futures_expiry(symbol)
    contract.includeExpired = False

    # print("[INFO] [utils.py] Latest futures expiry: ", contract.lastTradeDateOrContractMonth)
    # print("[INFO] [utils.py] Latest futures contract: ", contract)
    return contract

# print(get_latest_index_futures_expiry("ES"))
# print(get_latest_futures_contract("ES"))