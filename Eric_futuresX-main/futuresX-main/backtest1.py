import pandas as pd
import matplotlib.pyplot as plt

# --- Load cleaned data ---
df = pd.read_csv('tickers/ES/ES.csv', parse_dates=['timestamp'])

# Parse timestamps properly
df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
df['timestamp'] = df['timestamp'].dt.tz_convert('America/New_York')
df['timestamp'] = df['timestamp'].dt.tz_localize(None)

# Set index
df = df.set_index('timestamp')

# --- Filter to 2025 only ---
df = df[(df.index >= '2025-01-01') & (df.index < '2026-01-01')]

# --- Parameters ---
opening_range_minutes = 5
r_multiple = 1

# Results list
trades = []

# --- Group by Day ---
for day, group in df.groupby(df.index.date):
    day_df = group.between_time('09:30', '16:00')
    
    if day_df.empty:
        continue
    
    # Get Opening Range
    opening_range = day_df.between_time('09:30', f'09:{30+opening_range_minutes-1}:59')
    
    if opening_range.empty:
        continue
    
    or_high = opening_range['high'].max()
    or_low = opening_range['low'].min()
    or_range = or_high - or_low

    # Search for breakout
    breakout = None
    entry_price = None
    target_price = None
    stop_price = None
    entry_time = None

    day_5m = day_df.resample('5min').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }).dropna()
    
    for time, row in day_5m.iterrows():
        if time.time() >= pd.to_datetime('11:00:00').time():
            # It's past 11:00 AM, don't take any trades
            break

        # Look for CLOSE breakout
        if row['close'] > or_high:
            breakout = 'long'
            entry_price = row['close']
            target_price = entry_price + r_multiple * or_range
            stop_price = or_low
            entry_time = time
            break



    # Manage the trade
    if breakout == 'long':
        risk = or_high - or_low
        for time, row in day_df.loc[entry_time:].iterrows():
            if row['high'] >= target_price:
                # trades.append({'day': day, 'result': 'win', 'entry': entry_price, 'exit': target_price})
                reward = target_price - entry_price  # Reward achieved
                trades.append({
                    'day': day,
                    'result': 'win',
                    'entry': entry_price,
                    'exit': target_price,
                    'risk': risk,
                    'reward': reward
                })
                break
            elif row['low'] <= stop_price:
                # trades.append({'day': day, 'result': 'loss', 'entry': entry_price, 'exit': stop_price})
                reward = stop_price - entry_price  # Negative reward
                trades.append({
                    'day': day,
                    'result': 'loss',
                    'entry': entry_price,
                    'exit': stop_price,
                    'risk': risk,
                    'reward': reward
                })
                break
        else:
            # If neither hit, exit at EOD
            exit_price = day_df['close'].iloc[-1]
            # trades.append({'day': day, 'result': 'close', 'entry': entry_price, 'exit': exit_price})
            reward = exit_price - entry_price
            trades.append({
                'day': day,
                'result': 'close',
                'entry': entry_price,
                'exit': exit_price,
                'risk': risk,
                'reward': reward
            })
    

# --- Analyze Results ---
trades_df = pd.DataFrame(trades)
trades_df['pnl'] = (trades_df['exit'] - trades_df['entry']) * 50
trades_df['rr'] = trades_df.apply(lambda row: 
    (row['exit'] - row['entry']) / row['risk'] if row['result'] == 'win' else 
    (row['entry'] - row['exit']) / row['risk'], axis=1
)
print(trades_df)
print("Win Rate:", (trades_df['result'] == 'win').mean())
print("Average PnL per Trade:", trades_df['pnl'].mean())
print("Total PnL:", trades_df['pnl'].sum())
print("Average Risk/Reward:", trades_df['rr'].mean())

# --- Plot Equity Curve ---
trades_df['cumulative_pnl'] = trades_df['pnl'].cumsum()
plt.plot(trades_df['cumulative_pnl'])
plt.title('Simple 5-Minute ORB Equity Curve (2024-2025)')
plt.xlabel('Trades')
plt.ylabel('Cumulative PnL')
plt.show()
