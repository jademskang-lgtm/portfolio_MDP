import pandas as pd
from engine import RealV2Engine
import sys

csv_path = "kospi50_list 복사본.csv"

# 1. Read existing and memorize the last row
df = pd.read_csv(csv_path, dtype=str, index_col=0)
original_last_date = df.index.max()
original_last_row = df.loc[original_last_date].tolist()

print(f"Original Last Date: {original_last_date}")
print(f"Original Row Preview: {original_last_row[:5]} ... {original_last_row[-5:]}")

# 2. Drop the last row
df_dropped = df.drop(index=original_last_date)
df_dropped.to_csv(csv_path)
print(f"Dropped {original_last_date} from CSV.")

# 3. Initialize engine and trigger update
# Since 'update_data' might check for "Jan/Jul" based on TODAY,
# wait! The auto-update only fetches if we are CURRENTLY in Jan/Jul.
# Today is April 4th, 2026!
# engine.py logic:
# if now.month in [1, 7]:
#    needs_update = True
# So it WON'T update if we just call it today. We need to mock datetime.now() via mocking.
