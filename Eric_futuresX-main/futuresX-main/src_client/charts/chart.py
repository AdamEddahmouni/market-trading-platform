from lightweight_charts import Chart

import pandas as pd

# LOAD DATA
# Load your cleaned ES data
df = pd.read_csv('tickers/ES/ES.csv', parse_dates=['timestamp'])

df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
df['timestamp'] = df['timestamp'].dt.tz_convert('America/New_York')  # Convert to New York time
df['timestamp'] = df['timestamp'].dt.tz_localize(None) # flatten into lightweight charts format

#Filter April 25, 2025
df_filtered = df[
    # (df['timestamp'] >= '2024-09-16 00:00:00') &
    # (df['timestamp'] < '2024-09-17 00:00:00')
    (df['timestamp'] >= '2025-03-06 00:00:00') &
    (df['timestamp'] < '2025-03-11 00:00:00')
]
# df_filtered = df.loc['2025-04-25' : '2025-04-26']

print(df_filtered)

df_filtered = df_filtered.set_index('timestamp')

# RTH hours: df = df.between_time('09:30', '16:00')

def on_timeframe_selection(chart):
    print(f'Getting data with a {chart.topbar["my_switcher"].value} timeframe.')

if __name__ == '__main__':
    # Set up chart
    chart = Chart()

    chart.set(df_filtered)

    # chart.topbar.switcher(
    #     name='my_switcher',
    #     options=('1min', '5min', '15min', '1h', 'D', 'W'),
    #     default='1min',
    #     func=on_timeframe_selection)

    chart.show(block=True)