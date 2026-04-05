from fastapi import FastAPI, Request, BackgroundTasks, File, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.templating import Jinja2Templates
from engine import RealV2Engine
import pandas as pd
import os
import io
from datetime import datetime
import traceback
import logging
import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
engine = RealV2Engine()

_NAME_CACHE = {}
def get_korean_name(code: str) -> str:
    if code in _NAME_CACHE:
        return _NAME_CACHE[code]
    try:
        res = requests.get(f"https://finance.naver.com/item/main.naver?code={code}", timeout=3)
        soup = BeautifulSoup(res.text, "html.parser")
        tag = soup.select_one("div.wrap_company h2 a")
        name = tag.text if tag else f"Stock {code}"
        _NAME_CACHE[code] = name
        return name
    except:
        return f"Stock {code}"

# Mount static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/", response_class=HTMLResponse)
async def read_root():
    index_path = os.path.join(static_dir, "index.html")
    return FileResponse(index_path)

@app.get("/api/backtest")
async def get_backtest():
    try:
        results_path = os.path.join(engine.base_dir, "backtest_results.csv")
        if os.path.exists(results_path):
            df = pd.read_csv(results_path)
            return JSONResponse(content=df.to_dict(orient='records'))
        return JSONResponse(content={"error": "No results found. Please update data first."}, status_code=404)
    except Exception as e:
        logger.error(traceback.format_exc())
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.get("/api/portfolio")
async def get_portfolio(date: str = None):
    try:
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        weights = engine.get_portfolio_snapshot(date)
        
        # Augment with names and latest prices for the UI
        detailed_holdings = {}
        for code, weight in weights.items():
            fpath = os.path.join(engine.stock_data_dir, f"{code}.csv")
            price = 0
            if os.path.exists(fpath):
                df = pd.read_csv(fpath, index_col=0, parse_dates=True)
                price = float(df['Close'].iloc[-1])
            detailed_holdings[code] = {
                "weight": weight,
                "price": price,
                "name": get_korean_name(code)
            }
            
        return JSONResponse(content={"date": date, "weights": weights, "details": detailed_holdings})
    except Exception as e:
        logger.error(traceback.format_exc())
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.get("/api/calculator")
async def calculate(amount: float, mode: str = 'both', date: str = None):
    try:
        calc_date = datetime.now()
        if date:
            calc_date = datetime.fromisoformat(date)
            
        weights = engine.get_portfolio_snapshot(calc_date)
        prices = {}
        names = {}
        for code in weights.keys():
            fpath = os.path.join(engine.stock_data_dir, f"{code}.csv")
            if os.path.exists(fpath):
                df = pd.read_csv(fpath, index_col=0, parse_dates=True)
                # Filter prices by the same target date to be consistent
                price_hist = df['Close'].loc[:calc_date]
                if not price_hist.empty:
                    prices[code] = float(price_hist.iloc[-1])
                else:
                    prices[code] = 0
            names[code] = get_korean_name(code)
                
        result = engine.calculate_shares(amount, weights, prices, mode)
        result["names"] = names
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(traceback.format_exc())
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.get("/api/universe/status")
async def universe_status():
    try:
        return JSONResponse(content=engine.get_universe_status())
    except Exception as e:
        logger.error(traceback.format_exc())
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.post("/api/universe/upload")
async def upload_universe(file: UploadFile = File(...)):
    try:
        content = await file.read()
        df = pd.read_excel(io.BytesIO(content))
        engine.update_universe_from_excel(df)
        return JSONResponse(content={"message": "Universe updated successfully."})
    except Exception as e:
        logger.error(traceback.format_exc())
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.post("/api/update")
async def update_data(background_tasks: BackgroundTasks):
    background_tasks.add_task(engine.update_data)
    return JSONResponse(content={"message": "Update started in background."})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
