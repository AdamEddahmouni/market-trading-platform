import time
import sys
import os
from decimal import Decimal

# Add parent directory to path to import ibkrdata
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ibkrdata import data_manager

CONTRACT_NAME = "ES"  # replace with your current ES contract code
TRADE_SIZE = 1

def should_trade():
    bids, asks = data_manager.get_market_depth()

    if not bids or not asks:
        print("No bids or asks")
        return None, None, None, None  # No signal

    total_bid = sum(level[1] for level in bids[:5])
    total_ask = sum(level[1] for level in asks[:5])

    print(total_bid, total_ask)

    best_bid = bids[0][0]
    best_ask = asks[0][0]

    if total_bid > total_ask * Decimal("1.5"):
        # Short signal
        print("Short signal")
        return "short", best_ask, best_ask + 4.0, best_ask - 4.0
    elif total_ask > total_bid * Decimal("1.5"):
        print("Long signal")
        # Long signal
        return "long", best_bid, best_bid - 4.0, best_bid + 4.0

    return None, None, None, None

def run_live_strategy():
    print("Starting live strategy loop...")


    try:
        while True:
            # print(data_manager.get_positions())

            # 

            signal, entry_price, sl, tp = should_trade()


            if signal:
                print(f"[SIGNAL] {signal.upper()} @ {entry_price} | TP: {tp} | SL: {sl}")
                current_pos = data_manager.get_positions()

                if current_pos == 0.0:
                    if signal == "short":
                        data_manager.sell_bracket_order_market(CONTRACT_NAME, TRADE_SIZE, tp, sl)
                    elif signal == "long":
                        data_manager.buy_bracket_order_market(CONTRACT_NAME, TRADE_SIZE, tp, sl)
                    print("[ORDER] Bracket order placed.")

                # wait a second after placing to avoid duplicates
                time.sleep(1)
            else:
                time.sleep(0.1)
                
    except KeyboardInterrupt:
        print("Strategy stopped.")
        data_manager.cancel_all_orders()
        data_manager.disconnect()

# Run it
run_live_strategy()
