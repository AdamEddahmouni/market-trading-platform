import sqlite3
from matplotlib import pyplot as plt
import pandas as pd
import ast

# Load data
conn = sqlite3.connect("market_depth_rth_before_june9.db")
df = pd.read_sql_query("SELECT * FROM depth_snapshots", conn)
conn.close()

def parse_top(ladder_str):
    ladder = ast.literal_eval(ladder_str)
    top_ask = ladder[0]
    top_bid = ladder[-1]
    return top_bid, top_ask

positions = []
pnl = 0
N = 5  # Number of ticks to hold

for i in range(len(df) - N):
    row = df.iloc[i]
    top_bid, top_ask = parse_top(row['ladder'])

    bid_size = top_bid[1]
    bid_price = top_bid[0]
    ask_size = top_ask[1]
    ask_price = top_ask[0]

    # Check imbalance
    if bid_size > 2 * ask_size:
        # Simulate market buy at ask price
        entry_price = ask_price

        future_row = df.iloc[i + N]
        future_bid, future_ask = parse_top(future_row['ladder'])
        # Assume we exit at mid price for simplicity
        future_mid = (future_bid[0] + future_ask[0]) / 2

        profit = (future_mid - entry_price) * 50
        pnl += profit
        positions.append(profit)

    elif ask_size > 2 * bid_size:
        # Simulate market sell at bid price
        entry_price = bid_price

        future_row = df.iloc[i + N]
        future_bid, future_ask = parse_top(future_row['ladder'])
        # Assume we exit at mid price for simplicity
        future_mid = (future_bid[0] + future_ask[0]) / 2

        profit = (entry_price - future_mid) * 50
        pnl += profit
        positions.append(profit)

print(f"Total P&L: {pnl:.2f}")
print(f"Number of trades: {len(positions)}")
print(f"Avg P&L per trade: {pnl / len(positions):.4f}" if positions else "No trades")

# Plot
if positions:
    cumulative_pnl = pd.Series(positions).cumsum()
    plt.figure(figsize=(10, 5))
    plt.plot(cumulative_pnl, marker='o')
    plt.title("Cumulative P&L per Trade (Smarter Strategy)")
    plt.xlabel("Trade Number")
    plt.ylabel("Cumulative P&L ($)")
    plt.grid(True)
    plt.show()
else:
    print("No trades to plot.")