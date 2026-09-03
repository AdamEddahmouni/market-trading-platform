from PyQt6.QtCore import QThread, pyqtSignal
import time
import csv
import json
from ibkrdata import data_manager
from datetime import datetime
import pytz

class DataCollector(QThread):
    data_collected = pyqtSignal(str)  # Emits full ladder snapshot as a dict

    def format_ladder(self,levels):
        """Convert list of (Decimal, Decimal) to 'price:size;price:size;...'."""
        return ";".join(f"{float(price):.2f}:{int(size)}" for price, size in levels)


    def __init__(self, symbol="ES"):
        super().__init__()
        self.symbol = symbol
        self.running = True

    def is_rth(self):
        """Check if current time is within 9:30 AM - 4:00 PM ET."""
        now = datetime.now(pytz.timezone("America/New_York")).time()
        return now >= datetime.strptime("09:30", "%H:%M").time() and \
               now <= datetime.strptime("16:00", "%H:%M").time()

    def run(self):
        
        file_exists = False
        try:
            with open("es_level2_data.csv", "r"):
                file_exists = True
        except FileNotFoundError:
            pass

        with open("es_level2_data.csv", "a", newline="") as f:
            
            writer = csv.writer(f)

            # Write header if file doesn't exist
            if not file_exists:
                writer.writerow(["timestamp", "asks", "bids"])

            while self.running:
                if self.is_rth():
                    bids, asks = data_manager.get_market_depth()
                    asks = sorted(asks, key=lambda x: -x[0])

                    if bids and asks:
                        timestamp = time.time()
                        bid_str = self.format_ladder(bids)
                        ask_str = self.format_ladder(asks)

                        print(f"[DataCollector] {timestamp:.2f} | ASKS: {ask_str} | BIDS: {bid_str}")
                        
                        # Write to CSV (serialize lists as JSON)
                        writer.writerow([timestamp, ask_str, bid_str])

                        f.flush()

                        # Emit to GUI
                        self.data_collected.emit("write")
                    else:
                        self.data_collected.emit("wait")
                    
                else:
                    self.data_collected.emit("wait")

                time.sleep(0.1)  # collect every 100ms


    def stop(self):
        self.running = False