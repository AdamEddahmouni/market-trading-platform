import pandas as pd
import pytz
import requests
from datetime import datetime, timedelta
from lightweight_charts import Chart

# Replace with your actual credentials
USERNAME = 'EricSB'
# API_KEY = 'REDACTED'
API_ENDPOINT = 'https://api.topstepx.com'

# authentication
# POST request to get token
def authenticate():
    url = f"{API_ENDPOINT}/api/Auth/loginKey"
    headers = {"Content-Type": "application/json"}
    data = {"userName": USERNAME, "apiKey": API_KEY}
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    return response.json()['token']

### --------------- placing your first order tutorial---------------
# POST request to get all accounts
def checkAccounts(token):
    url = f"{API_ENDPOINT}/api/account/search"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    data = {
        "onlyActiveAccounts": True,
    }
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    return response.json()

# POST Contract Search
def searchContract(token, contract):
    url = f"{API_ENDPOINT}/api/contract/search"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    data = {
        "live": False,
        "searchText": contract
    }
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    return response.json()

def searchContractbyID(token, contractId):
    """
        Search for a contract by ID.
            Example:
            contractId = "CON.F.US.ENQ.M25"
    """
    url = f"{API_ENDPOINT}/api/contract/searchbyid"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    data = {
        "contractId": contractId
    }
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    return response.json()


# POST Buy Market Order
def buyMarketOrder(token, accountId, contractId, type, side, size):
    url = f"{API_ENDPOINT}/api/order/place"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    data = {
        "accountId": accountId,
        "contractId": contractId,
        "type": type,
        "side": side,
        "size": size,
        "limitPrice": None,
        "stopPrice": None,
        "trailPrice": None,
        "customTag": None,
        "linkedOrderId": None
    }
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    return response.json()

# POST get bars
def getBars(token, contractId, live, startTime, endTime, unit, unitNumber, limit, includePartialBar):
    """
        Returns a Dict of Bars.
        End Time and number of bars are what matters
    """
    url = f"{API_ENDPOINT}/api/history/retrieveBars"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    data = {
        "contractId": contractId,
        "live": live,
        "startTime": startTime,
        "endTime": endTime,
        "unit": unit,
        "unitNumber": unitNumber,
        "limit": limit,
        "includePartialBar": includePartialBar
    }
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    return response.json()

# Convert New York time to Zulu time for Topstep API historical bars
def ny_to_zulu(ny_str):
    ny_tz = pytz.timezone("America/New_York")
    ny_time = ny_tz.localize(datetime.strptime(ny_str, "%Y-%m-%d %H:%M:%S"))
    return ny_time.astimezone(pytz.utc).isoformat().replace("+00:00", "Z")

def get_historicalbars():
    # get historical bars
    start = ny_to_zulu("2025-05-14 00:00:00")
    end   = ny_to_zulu("2024-05-15 17:00:00")
    # end   = ny_to_zulu("2024-12-31 17:00:00")

    # 5m time frame
    # bars = getBars(token, "CON.F.US.ENQ.M25", False, start, end, 2, 5, 10000, False)
    # 1hr time frame
    bars = getBars(token, "CON.F.US.ENQ.M25", False, start, end, 3, 1, 10000, False)
    # bars = getBars(token, "CON.F.US.ENQ.Z24", False, start, end, 3, 1, 10000, False)

    # daily
    # bars = getBars(token, "CON.F.US.ENQ.M25", False, start, end, 4, 1, 10000, False)

    print(" ------------------------------------------------------------")

    # for i in range(len(bars["bars"])):
    #     print(bars["bars"][i])

    df = pd.DataFrame(bars["bars"])

    df.columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']


    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
    df['timestamp'] = df['timestamp'].dt.tz_convert('America/New_York')
    df['timestamp'] = df['timestamp'].dt.tz_localize(None)


    # Sort timestamp in order
    df = df.sort_values(by='timestamp').reset_index(drop=True)
    df = df.set_index('timestamp')

    chart = Chart()
    chart.set(df)
    chart.show(block=True)

if __name__ == "__main__":
    token = authenticate()
    # print(token)

    print(checkAccounts(token))
    print(searchContract(token, "ENQ"))
    # print(buyMarketOrder(token, "7828375", "CON.F.US.ENQ.M25", 1, 0, 1))
    print("--------------------------------")
    print(searchContractbyID(token, "CON.F.US.ENQ.Z23"))

    # get_historicalbars()
