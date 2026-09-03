import pandas as pd

# Load the CSV
df = pd.read_csv('tickers/ES/glbx-mdp3-20100606-20250425.ohlcv-1m.csv', parse_dates=['ts_event'])

# Rename Columns
df.columns = ['timestamp', 'col1', 'col2', 'col3', 'open', 'high', 'low', 'close', 'volume', 'symbol']

# Get rid of useless columns
df = df.drop(columns = ["col1", "col2", "col3"])

# FILTER OUT any rows where open, high, low, or close are <= 0
df = df[
    (df['open'] > 0) &
    (df['high'] > 0) &
    (df['low'] > 0) &
    (df['close'] > 0)
]

# REMOVE any rows where symbol contains a "-"
df = df[~df['symbol'].str.contains("-", na=False)]


### --------- 🛠️ CONTRACT MANAGEMENT -----------
# Contract codes per month
month_to_code = {
    3: 'H',   # March
    6: 'M',   # June
    9: 'U',   # September
    12: 'Z'   # December
}

def get_expected_contract(timestamp):
    year = timestamp.year
    month = timestamp.month

    # Determine which "front" contract should be active
    # Based on rolling a week before expiration

    # Rules:
    # March expiry (H): switch in early March
    # June expiry (M): switch in early June
    # September expiry (U): switch in early September
    # December expiry (Z): switch in early December

    if month < 3 or (month == 3 and timestamp.day < 8):
        code = 'H'
    elif month < 6 or (month == 6 and timestamp.day < 8):
        code = 'M'
    elif month < 9 or (month == 9 and timestamp.day < 8):
        code = 'U'
    elif month < 12 or (month == 12 and timestamp.day < 8):
        code = 'Z'
    else:
        # December after roll → move to next year's March
        code = 'H'
        year += 1

    year_digit = str(year)[-1]  # last digit of year

    return f"ES{code}{year_digit}"

# Sort by timestamp and descending volume
df_sorted = df.sort_values(['timestamp', 'volume'], ascending=[True, False])

# Drop duplicate timestamps, keeping the one with highest volume
df_highest_volume = df_sorted.drop_duplicates(subset=['timestamp'])

print(df_highest_volume.head())

# Save File
df_highest_volume.to_csv('ES.csv', index=False)
