from lightweight_charts import Chart

import pandas as pd

# LOAD DATA
# Load your cleaned ES data
df = pd.read_csv('tickers/SPY/SPY-1m-databento.csv', parse_dates=['ts_event'])

df['ts_event'] = pd.to_datetime(df['ts_event'], utc=True)
df['ts_event'] = df['ts_event'].dt.tz_convert('America/New_York')  # Convert to New York time
df['ts_event'] = df['ts_event'].dt.tz_localize(None) # flatten into lightweight charts format

#Filter April 25, 2025
df_filtered = df[
    # (df['timestamp'] >= '2024-09-16 00:00:00') &
    # (df['timestamp'] < '2024-09-17 00:00:00')
    (df['ts_event'] >= '2025-03-06 00:00:00') &
    (df['ts_event'] < '2025-03-11 00:00:00')
]
# df_filtered = df.loc['2025-04-25' : '2025-04-26']

print(df_filtered)

print(df_filtered.dtypes)

df_filtered = df_filtered.set_index('ts_event')

# RTH hours: df = df.between_time('09:30', '16:00')

def on_timeframe_selection(chart):
    print(f'Getting data with a {chart.topbar["my_switcher"].value} timeframe.')

if __name__ == '__main__':
    # Set up chart
    chart = Chart()

    chart.set(df_filtered)

    chart.topbar.switcher(
        name='my_switcher',
        options=('1min', '5min', '15min', '1h', 'D', 'W'),
        default='1min',
        func=on_timeframe_selection)

    chart.show(block=True)