from ibapi.client import *
from ibapi.wrapper import *
import datetime
from zoneinfo import ZoneInfo
import time
from src_client.workspace.backend.utils import *
import threading
from lightweight_charts import Chart
import pandas as pd
import streamlit as st

# streamlit run .\chart2.py

port = 7497

ohlc = []
all_df = pd.DataFrame()

class IBApp(EClient, EWrapper):
    def __init__(self):
        EClient.__init__(self, self)

    def nextValidId(self, orderId: OrderId):
        self.orderId = orderId
    
    def nextId(self):
        self.orderId += 1
        return self.orderId
    
    def error(self, reqId, errorCode, errorString, advancedOrderReject=""):
        print(f"reqId: {reqId}, errorCode: {errorCode}, errorString: {errorString}, orderReject: {advancedOrderReject}")
    
    def historicalData(self, reqId, bar):
         # Parse IB's timestamp string as US Central Time
        bar_time = datetime.strptime(bar.date, "%Y%m%d  %H:%M:%S US/Central")


        ohlc.append({
            "time": bar_time,
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close
        })
        print(reqId, bar)
    
    def historicalDataEnd(self, reqId, start, end):
        # print(f"Historical Data Ended for {reqId}. Started at {start}, ending at {end}")
        self.cancelHistoricalData(reqId)

        print(ohlc)

        df = pd.DataFrame(ohlc)
        df["time"] = pd.to_datetime(df["time"], unit="s") 

        # localize then convert to eastern
        df["time"] = df["time"].dt.tz_localize("US/Central")
        df["time"] = df["time"].dt.tz_convert("America/New_York").dt.tz_localize(None)
        
        df.rename(columns={"time": "timestamp"}, inplace=True)

        df.set_index("timestamp", inplace=True)

        print(df.head()) 


        start_chart(df)


def start_ib():
    app = IBApp()
    app.connect("127.0.0.1", port, 0)
    threading.Thread(target=app.run).start()
    time.sleep(1)

    contract = get_latest_futures_contract("ES")

    # Is in central time, cannot request in Eastern, closes at 15:55 for central
    app.reqHistoricalData(app.nextId(), contract, "", "1 W", "1 min", "TRADES", 0, 1, False, [])

def on_timeframe_selection(chart):
    print(f'LOG: Getting data with a {chart.topbar["timeframe"].value} timeframe.')

    print(all_df)
    timeframe = chart.topbar["timeframe"].value

    # Get the original DataFrame from the chart

    resample_rules = {
        '1min': '1min',
        '5min': '5min',
        '15min': '15min',
        '1h': '1h',
        '4h': '4h',
        'D': '1D',
        'W': '1W'
    }

    resampled_df = all_df.resample(resample_rules[timeframe]).agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last'
    })

    resampled_df.head()
    # Update the chart with the resampled data
    chart.set(resampled_df)
def start_chart(df):
    global all_df

    chart = Chart()
    chart.set(df)
    all_df = df.copy()

    chart.topbar.switcher(
        name='timeframe',
        options=('1min', '5min', '15min', '1h', 'D', 'W'),
        default='1min',
        func=on_timeframe_selection)

    chart.show(block=True)
if __name__ == "__main__":
    start_ib()
