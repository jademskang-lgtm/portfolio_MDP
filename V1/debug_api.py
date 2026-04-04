from fastapi.testclient import TestClient
from main import app
import traceback

client = TestClient(app)

try:
    print("Testing /api/backtest...")
    r = client.get("/api/backtest")
    print("Status:", r.status_code)
    
    print("\nTesting /api/portfolio...")
    r = client.get("/api/portfolio")
    print("Status:", r.status_code)
    if r.status_code != 200:
        print("Error Body:", r.text)
    else:
        print("Body Sample:", str(r.json())[:100])

except Exception as e:
    traceback.print_exc()
