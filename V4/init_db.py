from engine import RealV2Engine
import os
import pandas as pd
from datetime import datetime

def init():
    print("Initializing App Data (RealV2)...")
    engine = RealV2Engine()
    
    # Check if results exist, if not, we can either copy from the main folder or run
    src_results = "../results/cumulative_returns/mvp_backtest_cumulative_returns_real_v2.csv"
    dst_results = "backtest_results.csv"
    
    if os.path.exists(src_results):
        print("Copying existing results...")
        df = pd.read_csv(src_results)
        df.to_csv(dst_results, index=False)
    else:
        print("No existing results found. Running partial update...")
        # For a truly portable app, we'd run the backtest here if data allows
        pass

if __name__ == "__main__":
    init()
