from engine import RealV2Engine
from datetime import datetime
import pandas as pd

try:
    print("Testing Engine Initialization...")
    engine = RealV2Engine()
    print("Testing get_portfolio_snapshot...")
    weights = engine.get_portfolio_snapshot(datetime.now())
    print("Weights:", weights)
except Exception as e:
    import traceback
    traceback.print_exc()
