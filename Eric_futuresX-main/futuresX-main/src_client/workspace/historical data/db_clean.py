import sqlite3
import pandas as pd
import os

# Connect to your original database
conn = sqlite3.connect("market_depth.db")

# SQL query: filter for RTH (09:30:00 to 16:00:00 NY time)
query = """
SELECT *
FROM depth_snapshots
WHERE 
    substr(timestamp, 12, 8) >= '09:30:00'
    AND substr(timestamp, 12, 8) <= '16:00:00'
"""

# Load filtered data into DataFrame
df_rth = pd.read_sql_query(query, conn)

# Display sample
print(df_rth.head())

# Close original connection
conn.close()

# ✅ Save the RTH data into a new SQLite database
output_db_path = "market_depth_rth.db"
conn_rth = sqlite3.connect(output_db_path)

# Write DataFrame to a new table in the new DB
df_rth.to_sql("depth_snapshots", conn_rth, if_exists="replace", index=False)

# Close new DB connection
conn_rth.close()

print(f"RTH data exported to {output_db_path}")
