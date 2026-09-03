import os
import sqlite3
import json
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from src_client.workspace.backend.ibkrdata import data_manager

"""
Collects market depth data from IBKR and saves it to a SQLite database
"""

# Settings
DB_PATH = "market_depth2use.db"
SYMBOL = "ES"
INTERVAL = 0.1  # Log every 0.1 seconds (100ms)

# Create DB table if it doesn't exist
def create_table():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS depth_snapshots (
            timestamp TEXT,
            symbol TEXT,
            ladder TEXT  -- JSON string
        )
    """)
    conn.commit()
    conn.close()

# Continously log one market depth snapshot to the DB
def log_snapshot():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Pull market depth from data manager
        bids, asks = data_manager.get_market_depth()

        # Combine into one ladder: asks first (reversed for top-down), then bids
        ladder = asks[::-1] + bids
        print(ladder)

        # Convert ladder to JSON string and switch Decimal to float
        ladder_json = json.dumps([[float(price), float(size)] for price, size in ladder])

        # Fix to NY timezone
        timestamp = datetime.now(ZoneInfo("America/New_York")).isoformat()

        # Insert snapshot into DB
        cursor.execute("""
            INSERT INTO depth_snapshots (timestamp, symbol, ladder)
            VALUES (?, ?, ?)
        """, (timestamp, SYMBOL, ladder_json))

        conn.commit()
        conn.close()

        print(f"[{timestamp}] Snapshot saved with {len(ladder)} levels.")

    except Exception as e:
        print(f"[ERROR] {e}")

# Background logger loop (runs every INTERVAL seconds)
def run_logger():
    while True:
        log_snapshot()
        time.sleep(INTERVAL)

# Start background thread for logging
def start_thread():
    thread = threading.Thread(target=run_logger, daemon=True)
    thread.start()

# Main script logic
if __name__ == "__main__":
    create_table()
    start_thread()

    try:
        # Keep main thread alive so background thread can run
        while True:
            time.sleep(1)
    except KeyboardInterrupt: # Type in CTRL+C to stop
        print("\n[INFO] Shutting down and disconnecting IBKR...")
        data_manager.disconnect()
        print("[INFO] Disconnected from data manager")
