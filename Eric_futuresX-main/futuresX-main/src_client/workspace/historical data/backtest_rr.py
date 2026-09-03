import sqlite3
import pandas as pd
import ast
import matplotlib.pyplot as plt

# Load data
conn = sqlite3.connect("market_depth_rth_before_june9.db")
df = pd.read_sql_query("SELECT * FROM depth_snapshots", conn)
conn.close()

def parse_ladder(ladder_str):
    ladder = ast.literal_eval(ladder_str)
    mid = len(ladder) // 2
    asks = ladder[:mid]
    bids = ladder[mid:]
    return bids, asks

positions = []
pnl = 0
N = len(df)

i = 0
while i < N - 1:
    row = df.iloc[i]
    bids, asks = parse_ladder(row['ladder'])

    total_bid = sum(level[1] for level in bids[:5])  # top 5 levels
    total_ask = sum(level[1] for level in asks[:5])

    top_ask_price = asks[0][0]

    if total_bid > total_ask:
        # Short position triggered
        entry_price = top_ask_price
        stop_price = entry_price + 8.0
        target_price = entry_price - 4.0

        # Search forward until stop or target hit
        j = i + 1
        while j < N:
            future_bids, future_asks = parse_ladder(df.iloc[j]['ladder'])
            future_mid = (future_bids[0][0] + future_asks[0][0]) / 2

            if future_mid >= stop_price:
                # Stop hit
                trade_pnl = (entry_price - stop_price) * 50
                pnl += trade_pnl
                positions.append(trade_pnl)
                break

            if future_mid <= target_price:
                # TP hit
                trade_pnl = (entry_price - target_price) * 50
                pnl += trade_pnl
                positions.append(trade_pnl)
                break

            j += 1

        i = j  # Move to next after trade closes
    else:
        i += 1  # No trade, move to next tick

# Results
print(f"Total P&L: {pnl:.2f}")
print(f"Number of trades: {len(positions)}")
print(f"Avg P&L per trade: {pnl / len(positions):.4f}" if positions else "No trades")

# Plot
if positions:
    cumulative_pnl = pd.Series(positions).cumsum()
    plt.figure(figsize=(10, 5))
    plt.plot(cumulative_pnl, marker='o')
    plt.title("Cumulative P&L per Trade (4pt SL / 8pt TP Longs)")
    plt.xlabel("Trade Number")
    plt.ylabel("Cumulative P&L ($)")
    plt.grid(True)
    plt.show()
else:
    print("No trades to plot.")
