import requests
import pandas as pd
from datetime import datetime, timedelta
import pytz
import os

# === Configuration ===
USERNAME = "EricSB"  # Replace with your TopstepX username
API_KEY = "bfOuiIEvSK3BnaNvaxUr+KeE1B+qz3jENiiNqKigFJI="    # Replace with your API key
CONTRACT_ID = "CON.F.US.EP.M25"
API_ENDPOINT = "https://api.topstepx.com"
TIMEZONE = pytz.timezone("US/Eastern")
INTERVAL = '1m'
RANGE_MINUTES = 15
RR_RATIO = 2

# === Authentication ===
def authenticate():
    url = f"{API_ENDPOINT}/api/Auth/loginKey"
    headers = {"Content-Type": "application/json"}
    data = {"userName": USERNAME, "apiKey": API_KEY}
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    return response.json()['token']

# === Data Fetching ===
def fetch_data(token, start_date, end_date):
    url = f"{API_ENDPOINT}/api/MarketData/historical"
    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "contractId": CONTRACT_ID,
        "startDate": start_date.strftime('%Y-%m-%d'),
        "endDate": end_date.strftime('%Y-%m-%d'),
        "interval": INTERVAL
    }
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    df = pd.DataFrame(response.json())
    df['time'] = pd.to_datetime(df['time']).dt.tz_localize('UTC').dt.tz_convert(TIMEZONE)
    df.set_index('time', inplace=True)
    return df

# === Strategy Logic ===
def run_orb_strategy(df):
    trades = []
    grouped = df.groupby(df.index.date)
    for date, day_data in grouped:
        day_data = day_data.between_time("09:30", "16:00")
        if len(day_data) < RANGE_MINUTES:
            continue

        open_range = day_data.between_time("09:30", "09:45")
        high = open_range['high'].max()
        low = open_range['low'].min()
        range_size = high - low
        target = RR_RATIO * range_size

        post_range_data = day_data[open_range.index[-1]:]
        for idx, row in post_range_data.iterrows():
            if row['high'] > high:
                # Long
                entry = high
                stop = entry - range_size
                take = entry + target
                exit_price, exit_time = simulate_exit(post_range_data.loc[idx:], entry, stop, take, 'long')
                trades.append([idx, 'long', entry, exit_time, exit_price, round(exit_price - entry, 2)])
                break
            elif row['low'] < low:
                # Short
                entry = low
                stop = entry + range_size
                take = entry - target
                exit_price, exit_time = simulate_exit(post_range_data.loc[idx:], entry, stop, take, 'short')
                trades.append([idx, 'short', entry, exit_time, exit_price, round(entry - exit_price, 2)])
                break
    return trades

def simulate_exit(df, entry, stop, take, side):
    for time, row in df.iterrows():
        price = row['high'] if side == 'long' else row['low']
        if (side == 'long' and price >= take) or (side == 'short' and price <= take):
            return take, time
        if (side == 'long' and row['low'] <= stop) or (side == 'short' and row['high'] >= stop):
            return stop, time
    return df.iloc[-1]['close'], df.index[-1]

# === Main ===
def main():
    token = authenticate()
    end = datetime.now()
    start = end - timedelta(days=7)
    df = fetch_data(token, start, end)
    trades = run_orb_strategy(df)

    results = pd.DataFrame(trades, columns=["entry_time", "side", "entry_price", "exit_time", "exit_price", "pnl"])
    results.to_csv("orb_backtest_results.csv", index=False)
    print("Backtest complete. Results saved to 'orb_backtest_results.csv'.")

if __name__ == "__main__":
    main()
