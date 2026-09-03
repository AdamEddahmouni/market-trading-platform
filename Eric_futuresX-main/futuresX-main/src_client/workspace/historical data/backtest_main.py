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
    best_ask_price = asks[0][0]
    mid_price = (best_bid_price + best_ask_price) / 2

    direction = None
    if total_bid > total_ask * 1.5:
        direction = "short"
        entry_price = best_ask_price
        stop_price = entry_price + 3.0
        target_price = entry_price - 6.0
    elif total_ask > total_bid * 1.5:
        direction = "long"
        entry_price = best_bid_price
        stop_price = entry_price - 3.0
        target_price = entry_price + 6.0

    if direction:
        j = i + 1
        while j < N:
            future_bids, future_asks = parse_ladder(df.iloc[j]['ladder'])
            future_mid = (future_bids[0][0] + future_asks[0][0]) / 2

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
                    
                print("forced exit due to session end" + str(future_timestamp) + " " + str(entry_price) + " " + str(stop_price) + " " + str(target_price) + " " + str(trade_pnl))
                print("pnl: " + str(trade_pnl))

                positions.append(trade_pnl)
                pnl += trade_pnl
                break


            if direction == "short":
                if future_mid >= stop_price:
                    trade_pnl = (entry_price - stop_price) * point_value
                    positions.append(trade_pnl)
                    pnl += trade_pnl
                    exit_reason = "stop"
                    break
                elif future_mid <= target_price:
                    trade_pnl = (entry_price - target_price) * point_value
                    positions.append(trade_pnl)
                    pnl += trade_pnl
                    exit_reason = "target"
                    break

            elif direction == "long":
                if future_mid <= stop_price:
                    trade_pnl = (stop_price - entry_price) * point_value
                    positions.append(trade_pnl)
                    pnl += trade_pnl
                    break
                elif future_mid >= target_price:
                    trade_pnl = (target_price - entry_price) * point_value
                    positions.append(trade_pnl)
                    pnl += trade_pnl
                    break

            j += 1
        i = j
    else:
        i += 1

# Results
print(f"Total P&L: ${pnl:.2f}")
print(f"Number of trades: {len(positions)}")
print(f"Avg P&L per trade: {pnl / len(positions):.2f}" if positions else "No trades")

# Plot
if positions:
    cumulative_pnl = pd.Series(positions).cumsum()
    plt.figure(figsize=(10, 5))
    plt.plot(cumulative_pnl, marker='o')
    plt.title("Cumulative P&L per Trade (3pt SL / 6pt TP)\n2 days: 6/5/25-6/6/25")
    plt.xlabel("Trade Number")
    plt.ylabel("Cumulative P&L ($)")
    plt.grid(True)
    plt.show()
else:
    print("No trades to plot.")
