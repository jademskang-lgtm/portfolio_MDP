from engine import RealV2Engine
import pandas as pd
import os

engine = RealV2Engine()
results_path = os.path.join(engine.base_dir, "backtest_results.csv")

if os.path.exists(results_path):
    print(f"Reading {results_path}...")
    df = pd.read_csv(results_path)
    try:
        data = df.to_dict(orient='records')
        print(f"Successfully converted {len(data)} records.")
        # Check for dicts in the records
        for i, row in enumerate(data):
            for k, v in row.items():
                if isinstance(v, dict):
                    print(f"Found dict in row {i}, key {k}: {v}")
    except Exception as e:
        print(f"Error in to_dict: {e}")
else:
    print("backtest_results.csv not found.")
