import sqlite3
import pandas as pd
import ast
import matplotlib.pyplot as plt
from datetime import datetime

# Load SQL data
conn = sqlite3.connect("market_depth_rth_before_june9.db")
df = pd.read_sql_query("SELECT * FROM depth_snapshots", conn)
conn.close()

# Timestamp conversion (if available)
df['timestamp'] = pd.to_datetime(df['timestamp'])

def parse_ladder(ladder_str):
    ladder = ast.literal_eval(ladder_str)
    mid = len(ladder) // 2
    asks = ladder[:mid]
    bids = ladder[mid:]
    return bids, asks

def is_active_hour(timestamp):
    t = timestamp.time()
    return datetime.strptime("9:45", "%H:%M").time() <= t <= datetime.strptime("11:30", "%H:%M").time()

positions = []
trades   = []    # will hold one dict per trade
mid_prices = []  # will hold timestamp and future_mid data

pnl = 0
N = len(df)
tick_size = 0.25
point_value = 50  # For ES futures

i = 0
while i < N - 1:
    row = df.iloc[i]
    timestamp = row['timestamp']
    
    if not is_active_hour(timestamp):
        i += 1
        continue

    bids, asks = parse_ladder(row['ladder'])


    total_bid = sum(level[1] for level in bids[:5])
    total_ask = sum(level[1] for level in asks[:5])

    best_bid_price = bids[0][0]
    best_ask_price = asks[-1][0]
    mid_price = (best_bid_price + best_ask_price) / 2

    # Note: Original was total_ask > total_bid * 1.5: for short, total_bid > total_ask * 1.5: for long

    direction = None
    if total_bid > total_ask * 1.5:
        direction = "short"
        entry_price = best_ask_price
        stop_price = entry_price + 4
        target_price = entry_price - 4
    elif total_ask > total_bid * 1.5:
        direction = "long"
        entry_price = best_bid_price
        stop_price = entry_price - 4
        target_price = entry_price + 4

    if direction:
        j = i + 1
        while j < N:
            future_bids, future_asks = parse_ladder(df.iloc[j]['ladder'])
            future_mid = (future_bids[0][0] + future_asks[-1][0]) / 2

            # Log timestamp and future_mid
            mid_prices.append({
                'timestamp': df.iloc[j]['timestamp'],
                'future_mid': future_mid,
                'stop_price': stop_price if direction else None,
                'target_price': target_price if direction else None,
                'direction': direction,
                'stop_condition_met': future_mid <= stop_price if direction == "long" else (future_mid >= stop_price if direction == "short" else None)
            })

            # Exit if session ends
            future_row = df.iloc[j]
            future_timestamp = future_row['timestamp']
            if not is_active_hour(future_timestamp):
                # Forced exit due to session end
                exit_price = (future_bids[0][0] + future_asks[0][0]) / 2
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
                # print("timestamp: " + str(future_timestamp) + " future mid: " + str(future_mid))
                # print(f"  LONG trade check - future_mid: {future_mid:.2f}, stop_price: {stop_price:.2f}, condition: {future_mid <= stop_price}")
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

# Results
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

# Save timestamp and future_mid data to CSV
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

# Plot
if positions:
    cumulative_pnl = pd.Series(positions).cumsum()
    plt.figure(figsize=(10, 5))
    plt.plot(cumulative_pnl, marker='o')
    plt.title("Cumulative P&L per Trade (4pt SL / 4pt TP)\n2 days: 6/5/25-6/6/25")
    plt.xlabel("Trade Number")
    plt.ylabel("Cumulative P&L ($)")
    plt.grid(True)
    plt.show()
else:
    print("No trades to plot.")
