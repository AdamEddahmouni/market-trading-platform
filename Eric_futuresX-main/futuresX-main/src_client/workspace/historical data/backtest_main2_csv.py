import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
import pytz

# === Load CSV data ===
df = pd.read_csv('es_level2_data.csv')

# === Convert UNIX timestamp to datetime & Convert to NY time ===
df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s', utc=True)
# Convert from UTC to America/New_York
df['timestamp'] = df['timestamp'].dt.tz_convert('America/New_York')
df['timestamp'] = df['timestamp'].dt.tz_localize(None)



# === Parse ladder data side (asks or bids) ===
def parse_ladder_side(ladder_str):
    if pd.isna(ladder_str):
        return []
    try:
        return [(float(price), int(size)) for price, size in (item.split(':') for item in ladder_str.split(';'))]
    except Exception as e:
        print(f"Error parsing: {ladder_str} -> {e}")
        return []

df['ask_levels'] = df['asks'].apply(parse_ladder_side)
df['bid_levels'] = df['bids'].apply(parse_ladder_side)

print("finished parsing data")
print(df.head())



# === Trading hours ===
def is_active_hour(timestamp):
    t = timestamp.time()
    return datetime.strptime("09:45", "%H:%M").time() <= t <= datetime.strptime("11:30", "%H:%M").time()

# === Backtest ===
print("starting backtest")
positions = []
trades = []  # will hold one dict per trade
mid_prices = []  # will hold timestamp and future_mid data
pnl = 0
tick_size = 0.25
point_value = 50  # ES futures
N = len(df)
i = 0

while i < N - 1:
    row = df.iloc[i]
    timestamp = row['timestamp']

    if not is_active_hour(timestamp):
        i += 1
        continue

    bids = row['bid_levels']
    asks = row['ask_levels']

    if len(bids) < 5 or len(asks) < 5:
        i += 1
        continue

    total_bid = sum(size for _, size in bids[:5])
    total_ask = sum(size for _, size in asks[:5])

    best_bid = bids[0][0]
    best_ask = asks[-1][0]
    mid_price = (best_bid + best_ask) / 2



    direction = None
    if total_bid > total_ask * 1.5:
        direction = "short"
        entry_price = best_ask
        stop_price = entry_price + 4.0
        target_price = entry_price - 4
    elif total_ask > total_bid * 1.5:
        direction = "long"
        entry_price = best_bid
        stop_price = entry_price - 4.0
        target_price = entry_price + 4

    if direction:
        j = i + 1
        while j < N:
            next_row = df.iloc[j]
            future_timestamp = next_row['timestamp']
            
            # Log timestamp and future_mid data
            bids_f = next_row['bid_levels']
            asks_f = next_row['ask_levels']
            if bids_f and asks_f:
                future_mid = (bids_f[0][0] + asks_f[-1][0]) / 2
                mid_prices.append({
                    'timestamp': future_timestamp,
                    'future_mid': future_mid,
                    'stop_price': stop_price if direction else None,
                    'target_price': target_price if direction else None,
                    'direction': direction,
                    'stop_condition_met': future_mid <= stop_price if direction == "long" else (future_mid >= stop_price if direction == "short" else None)
                })
            
            if not is_active_hour(future_timestamp):
                if bids_f and asks_f:
                    exit_price = (bids_f[0][0] + asks_f[0][0]) / 2
                    if direction == "short":
                        trade_pnl = (entry_price - exit_price) * point_value
                    else:
                        trade_pnl = (exit_price - entry_price) * point_value
                    
                    # Log the trade
                    trade_info = {
                        'entry_time': timestamp,
                        'exit_time': future_timestamp,
                        'direction': direction,
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'stop_price': stop_price,
                        'target_price': target_price,
                        'exit_reason': 'session_end',
                        'pnl': trade_pnl,
                        'total_bid': total_bid,
                        'total_ask': total_ask
                    }
                    trades.append(trade_info)
                    
                    print(f"Trade #{len(trades)}: {direction.upper()} | Entry: {timestamp.strftime('%m/%d %H:%M:%S')} @ {entry_price:.2f} | Exit: {future_timestamp.strftime('%m/%d %H:%M:%S')} @ {exit_price:.2f} | P&L: ${trade_pnl:.2f} | Reason: Session End")
                    print(f"  Stop: {stop_price:.2f} | Target: {target_price:.2f} | Bid/Ask Ratio: {total_bid}/{total_ask}")
                    print("-" * 80)
                    
                    positions.append(trade_pnl)
                    pnl += trade_pnl
                break

            if not bids_f or not asks_f:
                j += 1
                continue

            future_mid = (bids_f[0][0] + asks_f[0][0]) / 2

            if direction == "short":
                if future_mid >= stop_price:
                    trade_pnl = (entry_price - stop_price) * point_value
                    
                    # Log the trade
                    trade_info = {
                        'entry_time': timestamp,
                        'exit_time': future_timestamp,
                        'direction': direction,
                        'entry_price': entry_price,
                        'exit_price': stop_price,
                        'stop_price': stop_price,
                        'target_price': target_price,
                        'exit_reason': 'stop',
                        'pnl': trade_pnl,
                        'total_bid': total_bid,
                        'total_ask': total_ask
                    }
                    trades.append(trade_info)
                    
                    print(f"Trade #{len(trades)}: {direction.upper()} | Entry: {timestamp.strftime('%m/%d %H:%M:%S')} @ {entry_price:.2f} | Exit: {future_timestamp.strftime('%m/%d %H:%M:%S')} @ {stop_price:.2f} | P&L: ${trade_pnl:.2f} | Reason: Stop Loss")
                    print(f"  Stop: {stop_price:.2f} | Target: {target_price:.2f} | Bid/Ask Ratio: {total_bid}/{total_ask}")
                    print("-" * 80)
                    
                    positions.append(trade_pnl)
                    pnl += trade_pnl
                    break
                elif future_mid <= target_price:
                    trade_pnl = (entry_price - target_price) * point_value
                    
                    # Log the trade
                    trade_info = {
                        'entry_time': timestamp,
                        'exit_time': future_timestamp,
                        'direction': direction,
                        'entry_price': entry_price,
                        'exit_price': target_price,
                        'stop_price': stop_price,
                        'target_price': target_price,
                        'exit_reason': 'target',
                        'pnl': trade_pnl,
                        'total_bid': total_bid,
                        'total_ask': total_ask
                    }
                    trades.append(trade_info)
                    
                    print(f"Trade #{len(trades)}: {direction.upper()} | Entry: {timestamp.strftime('%m/%d %H:%M:%S')} @ {entry_price:.2f} | Exit: {future_timestamp.strftime('%m/%d %H:%M:%S')} @ {target_price:.2f} | P&L: ${trade_pnl:.2f} | Reason: Target Hit")
                    print(f"  Stop: {stop_price:.2f} | Target: {target_price:.2f} | Bid/Ask Ratio: {total_bid}/{total_ask}")
                    print("-" * 80)
                    
                    positions.append(trade_pnl)
                    pnl += trade_pnl
                    break
            elif direction == "long":
                if future_mid <= stop_price:
                    trade_pnl = (stop_price - entry_price) * point_value
                    
                    # Log the trade
                    trade_info = {
                        'entry_time': timestamp,
                        'exit_time': future_timestamp,
                        'direction': direction,
                        'entry_price': entry_price,
                        'exit_price': stop_price,
                        'stop_price': stop_price,
                        'target_price': target_price,
                        'exit_reason': 'stop',
                        'pnl': trade_pnl,
                        'total_bid': total_bid,
                        'total_ask': total_ask
                    }
                    trades.append(trade_info)
                    
                    print(f"Trade #{len(trades)}: {direction.upper()} | Entry: {timestamp.strftime('%m/%d %H:%M:%S')} @ {entry_price:.2f} | Exit: {future_timestamp.strftime('%m/%d %H:%M:%S')} @ {stop_price:.2f} | P&L: ${trade_pnl:.2f} | Reason: Stop Loss")
                    print(f"  Stop: {stop_price:.2f} | Target: {target_price:.2f} | Bid/Ask Ratio: {total_bid}/{total_ask}")
                    print("-" * 80)
                    
                    positions.append(trade_pnl)
                    pnl += trade_pnl
                    break
                elif future_mid >= target_price:
                    trade_pnl = (target_price - entry_price) * point_value
                    
                    # Log the trade
                    trade_info = {
                        'entry_time': timestamp,
                        'exit_time': future_timestamp,
                        'direction': direction,
                        'entry_price': entry_price,
                        'exit_price': target_price,
                        'stop_price': stop_price,
                        'target_price': target_price,
                        'exit_reason': 'target',
                        'pnl': trade_pnl,
                        'total_bid': total_bid,
                        'total_ask': total_ask
                    }
                    trades.append(trade_info)
                    
                    print(f"Trade #{len(trades)}: {direction.upper()} | Entry: {timestamp.strftime('%m/%d %H:%M:%S')} @ {entry_price:.2f} | Exit: {future_timestamp.strftime('%m/%d %H:%M:%S')} @ {target_price:.2f} | P&L: ${trade_pnl:.2f} | Reason: Target Hit")
                    print(f"  Stop: {stop_price:.2f} | Target: {target_price:.2f} | Bid/Ask Ratio: {total_bid}/{total_ask}")
                    print("-" * 80)
                    
                    positions.append(trade_pnl)
                    pnl += trade_pnl
                    break
            j += 1
        i = j
    else:
        i += 1

# === Results ===
print(f"\n{'='*80}")
print(f"BACKTEST SUMMARY")
print(f"{'='*80}")
print(f"Total P&L: ${pnl:.2f}")
print(f"Number of trades: {len(positions)}")
print(f"Avg P&L per trade: {pnl / len(positions):.2f}" if positions else "No trades")

# Additional statistics
if trades:
    winning_trades = [t for t in trades if t['pnl'] > 0]
    losing_trades = [t for t in trades if t['pnl'] < 0]
    
    print(f"Winning trades: {len(winning_trades)}")
    print(f"Losing trades: {len(losing_trades)}")
    print(f"Win rate: {len(winning_trades)/len(trades)*100:.1f}%")
    
    if winning_trades:
        avg_win = sum(t['pnl'] for t in winning_trades) / len(winning_trades)
        print(f"Average win: ${avg_win:.2f}")
    
    if losing_trades:
        avg_loss = sum(t['pnl'] for t in losing_trades) / len(losing_trades)
        print(f"Average loss: ${avg_loss:.2f}")
    
    # Exit reason breakdown
    exit_reasons = {}
    for trade in trades:
        reason = trade['exit_reason']
        exit_reasons[reason] = exit_reasons.get(reason, 0) + 1
    
    print(f"\nExit Reasons:")
    for reason, count in exit_reasons.items():
        print(f"  {reason}: {count} trades")

# Save trades to CSV
# if trades:
#     # Convert trades list to DataFrame
#     trades_df = pd.DataFrame(trades)
    
#     # Format timestamps for better CSV readability
#     trades_df['entry_time'] = trades_df['entry_time'].dt.strftime('%Y-%m-%d %H:%M:%S')
#     trades_df['exit_time'] = trades_df['exit_time'].dt.strftime('%Y-%m-%d %H:%M:%S')
    
#     # Generate filename with timestamp
#     timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
#     csv_filename = f"backtest_trades_{timestamp_str}.csv"
    
#     # Save to CSV
#     trades_df.to_csv(csv_filename, index=False)
#     print(f"\nTrades saved to: {csv_filename}")
#     print(f"CSV contains {len(trades_df)} trades with {len(trades_df.columns)} columns")
    
#     # Display first few trades as preview
#     print(f"\nFirst 3 trades preview:")
#     print(trades_df.head(3).to_string(index=False))

# # Save timestamp and future_mid data to CSV
# if mid_prices:
#     # Convert to DataFrame
#     mid_df = pd.DataFrame(mid_prices)
    
#     # Generate filename with timestamp
#     timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
#     csv_filename = f"timestamp_mid_prices_{timestamp_str}.csv"
    
#     # Save to CSV
#     mid_df.to_csv(csv_filename, index=False)
#     print(f"\nTimestamp and future_mid data saved to: {csv_filename}")
#     print(f"CSV contains {len(mid_df)} data points")
    
#     # Display first few rows as preview
#     print(f"\nFirst 5 rows preview:")
#     print(mid_df.head().to_string(index=False))

# === Plot ===
if positions:
    cumulative_pnl = pd.Series(positions).cumsum()
    plt.figure(figsize=(10, 5))
    plt.plot(cumulative_pnl, marker='o')
    plt.title("Cumulative P&L per Trade (4pt SL / 4pt TP). 9:45 AM - 11:30 AM\n4 days: July 2025 7,25,28, and 29")
    plt.xlabel("Trade Number")
    plt.ylabel("Cumulative P&L ($)")
    plt.grid(True)
    plt.show()
else:
    print("No trades to plot.")
