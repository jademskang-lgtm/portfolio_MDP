# RealV2 Investment App

Institutional-grade KOSPI 50 investment management system based on the audited `RealV2` strategy.

## Features
- **Backtest Dashboard**: Daily-updated cumulative returns since 2016.
- **Portfolio Snapshots**: Real-time target weights and holdings.
- **Historical Lookup**: View ideal portfolio composition for any date from 2016.
- **Investment Calculator**: Convert KRW amount to integer share counts with +/- 5% tolerance options.
- **Data Update**: One-click refresh for latest KOSPI prices, KODEX Inverse, and Fisher Z beta predicts.

## Installation & Deployment
1. Ensure Python 3.10+ is installed.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Initialize the database:
   ```bash
   python3 init_db.py
   ```
4. Start the application:
   ```bash
   python3 main.py
   ```
5. Open `http://localhost:8000` in your browser.

## Portability
The entire `app/` folder is self-contained. It can be moved to any location and will maintain functionality as long as the internal `stock_data` and CSV files are present.

---
**Strategy Audit**: Audited net-of-fees performance expectations are documented in the root directory's `walkthrough.md`.
