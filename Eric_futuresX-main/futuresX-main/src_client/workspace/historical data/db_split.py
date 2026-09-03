import sqlite3
import pandas as pd

# Path to your RTH DB
input_db = "market_depth_rth.db"
output_db = "market_depth_rth_before_june9.db"

# Connect to the RTH DB
conn_in = sqlite3.connect(input_db)

# SQL to select only dates before June 9
query = """
SELECT *
FROM depth_snapshots
WHERE substr(timestamp, 1, 10) < '2025-06-09'
"""

# Load filtered data into DataFrame
df_filtered = pd.read_sql_query(query, conn_in)

# Close input DB connection
conn_in.close()

# Save to new DB
conn_out = sqlite3.connect(output_db)
df_filtered.to_sql("depth_snapshots", conn_out, if_exists="replace", index=False)
conn_out.close()

print(f"Filtered data saved to {output_db}")
