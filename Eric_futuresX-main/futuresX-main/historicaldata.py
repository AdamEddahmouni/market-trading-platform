import pandas as pd
import plotly.graph_objects as go

# Step 1: Load your clean ES file
df = pd.read_csv('tickers/ES/ES.csv', parse_dates=['timestamp'])

# Step 2: Filter only April 25, 2025
# (timestamps may be in UTC, adjust if needed later)
df_filtered = df[
    (df['timestamp'] >= '2024-09-16 00:00:00') &
    (df['timestamp'] < '2024-09-17 00:00:00')
]

# Step 3: Check sample
print(df_filtered.head())

# Step 4: Plot the 1-minute candlestick chart
fig = go.Figure(data=[go.Candlestick(
    x=df_filtered['timestamp'],
    open=df_filtered['open'],
    high=df_filtered['high'],
    low=df_filtered['low'],
    close=df_filtered['close']
)])

fig.update_layout(
    title='ES 1-Min Candlestick Chart (April 25, 2025)',
    xaxis_title='Time',
    yaxis_title='Price',
    xaxis_rangeslider_visible=False
)

fig.show()
