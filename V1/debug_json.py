from engine import RealV2Engine
from datetime import datetime
import json

engine = RealV2Engine()
weights = engine.get_portfolio_snapshot(datetime.now())
print("Weights dict:", weights)

try:
    print("Testing JSON serialization...")
    json_str = json.dumps(weights)
    print("JSON success:", json_str[:50], "...")
except Exception as e:
    print("JSON Error:", e)

# Test the TemplateResponse style context
try:
    print("Testing context dict hashing (if FastAPI does it)...")
    context = {"request": "dummy", "weights": weights}
    # Some frameworks hash keys or values
    hash(json.dumps(context)) 
    print("Hashing success.")
except Exception as e:
    print("Hashing Error:", e)
