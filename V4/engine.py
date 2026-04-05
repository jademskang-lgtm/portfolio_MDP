import os
import pandas as pd
import numpy as np
import FinanceDataReader as fdr
from scipy.optimize import minimize
from statsmodels.tsa.stattools import coint
from datetime import datetime, timedelta
import warnings
import traceback
import logging

warnings.filterwarnings('ignore')
logger = logging.getLogger(__name__)

class RealV2Engine:
    def __init__(self, base_dir=None):
        if base_dir is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        self.base_dir = base_dir
        self.stock_data_dir = os.path.join(base_dir, "stock_data 복사본")
        self.kospi50_list_path = os.path.join(base_dir, "kospi50_list 복사본.csv")
        self.etf_path = os.path.join(base_dir, "코덱스 인버스.csv")
        self.beta_file_path = os.path.join(base_dir, "prediction_avg_results 복사본.xlsx")
        
        self.fee_rate = 0.00015
        self.weight_floor = 0.01
        self.etf_data = self.load_local_etf()

    def get_universe_status(self):
        """Checks if the KOSPI 50 list for the current period is missing."""
        try:
            df = pd.read_csv(self.kospi50_list_path, index_col=0)
            df.index = pd.to_datetime(df.index)
            
            now = datetime.now()
            # Determine strategic rebalance date (Jan 2nd or Jul 1st)
            target_year = now.year
            if now.month <= 6:
                target_date = datetime(target_year, 1, 2)
            else:
                target_date = datetime(target_year, 7, 1)
            
            # Find if this exact date exists
            existing = df[df.index == target_date]
            
            if existing.empty:
                return {"status": "missing_row", "date": target_date.strftime('%Y-%m-%d')}
            
            # Check if all stock columns are NaN or empty for this row
            latest_row = existing.iloc[-1]
            if latest_row.dropna().empty:
                return {"status": "missing_data", "date": target_date.strftime('%Y-%m-%d')}
                
            return {"status": "ok", "date": target_date.strftime('%Y-%m-%d')}
        except Exception as e:
            logger.error(f"Error checking universe status: {e}")
            return {"status": "error", "message": str(e)}

    def update_universe_from_excel(self, excel_df):
        """Extracts top 50 stock codes from '종목코드' column and updates the CSV."""
        try:
            if '종목코드' not in excel_df.columns:
                raise ValueError("Excel file must have a '종목코드' column.")
            
            # Clean and take top 50 codes
            codes = excel_df['종목코드'].astype(str).str.strip().str.zfill(6)
            top_50 = codes.head(50).tolist()
            
            if len(top_50) < 50:
                logger.warning(f"Only {len(top_50)} codes found in Excel.")
            
            # Load current CSV
            df = pd.read_csv(self.kospi50_list_path, index_col=0)
            df.index = pd.to_datetime(df.index)
            
            now = datetime.now()
            target_year = now.year
            if now.month <= 6:
                target_date = datetime(target_year, 1, 2)
            else:
                target_date = datetime(target_year, 7, 1)
            
            target_date_str = target_date.strftime('%Y-%m-%d')
            
            # Update the specific date row
            new_data = {f'stock{i+1}': top_50[i] if i < len(top_50) else None for i in range(50)}
            df.loc[target_date] = pd.Series(new_data)
            
            # Sort and save
            df = df.sort_index()
            df.to_csv(self.kospi50_list_path, encoding='utf-8-sig')
            return True
        except Exception as e:
            logger.error(f"Error updating universe from excel: {e}")
            raise e

    def load_local_etf(self):
        if not os.path.exists(self.etf_path):
            return pd.DataFrame()
        df = pd.read_csv(self.etf_path)
        df['date'] = pd.to_datetime(df['날짜'].str.replace(' ', '').str.strip())
        df['Close'] = df['종가'].astype(str).str.replace(',', '').astype(float)
        return df.set_index('date')[['Close']].sort_index()

    def update_data(self):
        """Update stock data and ETF data up to today."""
        # 1. Update ETF (KODEX Inverse: 114800)
        today = datetime.now().strftime('%Y-%m-%d')
        etf_live = fdr.DataReader('114800', '2016-01-01')
        etf_live.index = pd.to_datetime(etf_live.index)
        # Combine local and live
        local_etf = self.load_local_etf()
        combined_etf = pd.concat([local_etf[~local_etf.index.isin(etf_live.index)], etf_live[['Close']]])
        combined_etf = combined_etf.sort_index()
        
        # Save back to CSV
        output_etf = combined_etf.copy()
        output_etf.index.name = 'date'
        output_etf.index = output_etf.index.strftime('%Y- %m- %d')
        output_etf['종가'] = output_etf['Close'].apply(lambda x: f"{int(x):,}")
        output_etf = output_etf.reset_index().rename(columns={'date': '날짜'})
        output_etf[['날짜', '종가']].to_csv(self.etf_path, index=False, encoding='utf-8-sig')
        
        self.etf_data = combined_etf
        
        # 2. Update Stock Data for KOSPI 50
        kospi50 = pd.read_csv(self.kospi50_list_path, dtype=str, index_col=0)
        kospi50.index = pd.to_datetime(kospi50.index)
        latest_list_date = kospi50.index.max()
        current_universe = kospi50.loc[latest_list_date].dropna().unique().tolist()
        
        for code in current_universe:
            code = str(code).strip()
            if not code: continue
            if code.isdigit():
                code = code.zfill(6)
            
            fpath = os.path.join(self.stock_data_dir, f"{code}.csv")
            try:
                # Try standard fetch first
                live_df = fdr.DataReader(code, '2016-01-01')
                if live_df.empty:
                    # Try specifying KRX for special codes like 0126Z0
                    live_df = fdr.DataReader(code, '2016-01-01', exchange='KRX')
                
                if not live_df.empty:
                    live_df.to_csv(fpath)
            except Exception:
                # Silently skip special codes or transient network errors for clean UI
                pass
        
        # 3. Monthly Beta Calculation (if 1st of month)
        # 3. Monthly Beta Recalculation Trigger
        try:
            now = datetime.now()
            if os.path.exists(self.beta_file_path):
                existing_beta = pd.read_excel(self.beta_file_path, sheet_name='P200_F60')
                existing_beta['Date'] = pd.to_datetime(existing_beta['Date'], errors='coerce')
                existing_beta = existing_beta.dropna(subset=['Date'])
                
                # Check for and append missing month rows
                max_date = existing_beta['Date'].max()
                current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                if max_date < current_month_start:
                    print(f"Adding missing month rows after {max_date.strftime('%Y-%m-%d')}...")
                    new_dates = pd.date_range(start=max_date + pd.DateOffset(months=1), end=current_month_start, freq='MS')
                    new_rows = pd.DataFrame({'Date': new_dates, 'Actual': [np.nan]*len(new_dates)})
                    existing_beta = pd.concat([existing_beta, new_rows], ignore_index=True)
                    # Force Pred re-calc for new rows
                    existing_beta['Pred (10-Month Avg)'] = existing_beta['Actual'].rolling(10, min_periods=1).mean()
                    existing_beta['Pred (10-Month Avg)'] = existing_beta['Pred (10-Month Avg)'].ffill()

                # Find all dates where 'Actual' is NaN and we have enough history
                missing_dates = existing_beta.loc[existing_beta['Actual'].isna(), 'Date'].sort_values()
                
                updated_any = False
                for current_check in missing_dates:
                    if current_check >= now: continue # Skip future
                    
                    print(f"Attempting beta calculation for {current_check.strftime('%Y-%m-%d')}...")
                    res_beta = self.calculate_beta_monthly(current_check)
                    if res_beta is not None:
                        print(f"Calculated Actual Beta for {current_check.strftime('%Y-%m-%d')}: {res_beta:.6f}")
                        existing_beta.loc[existing_beta['Date'] == current_check, 'Actual'] = res_beta
                        updated_any = True
                    else:
                        print(f"Not enough data to calculate beta for {current_check.strftime('%Y-%m-%d')} yet.")
                        break 

                # Always recalculate 10-month average with strict Business Day Knowledge tracking
                # A month's actual beta is only known AFTER the 60th trading day following its target_date.
                # Pred[i] should only include Actuals where 60th training day < Date[i].
                
                # Use the local ETF data index as the source of truth for trading days
                benchmark_days = self.etf_data.index.sort_values()
                
                def get_knowledge_date(d):
                    after = benchmark_days[benchmark_days > d]
                    if len(after) >= 60:
                        return after[59] # 60th day after market close
                    return pd.Timestamp.max

                # Apply point-in-time logic to the entire Pred column to prevent look-ahead bias
                preds = []
                for idx, row in existing_beta.iterrows():
                    target_rebalance_date = row['Date']
                    
                    # Candidates: all previous rows
                    candidates = existing_beta[existing_beta['Date'] < target_rebalance_date].copy()
                    if len(candidates) == 0:
                        preds.append(np.nan)
                        continue
                        
                    # Filter candidates by their individual knowledge dates
                    # Knowledge must be strictly BEFORE the rebalance date morning
                    candidates['Knowledge_Date'] = candidates['Date'].apply(get_knowledge_date)
                    available = candidates[candidates['Knowledge_Date'] < target_rebalance_date]
                    
                    if len(available) > 0:
                        # Mean of last 10 available 'Actual' values
                        val = available['Actual'].dropna().tail(10).mean()
                        preds.append(val)
                    else:
                        preds.append(np.nan)
                
                existing_beta['Pred (10-Month Avg)'] = preds
                existing_beta['Pred (10-Month Avg)'] = existing_beta['Pred (10-Month Avg)'].ffill()
                
                with pd.ExcelWriter(self.beta_file_path, mode='a', engine='openpyxl', if_sheet_exists='overlay') as writer:
                    existing_beta.to_excel(writer, sheet_name='P200_F60', index=False)
                    
        except Exception as e:
            print(f"Error in beta recalculation: {e}")
            traceback.print_exc()

    def calculate_beta_monthly(self, target_date):
        """
        Fisher Z Regression beta calculation for a specific month (1st).
        y (Future_Z) = alpha + beta * x (Past_Z)
        """
        if isinstance(target_date, str):
            target_date = pd.to_datetime(target_date)
        
        # 1. Get KOSPI 50 universe at that time
        kospi50 = pd.read_csv(self.kospi50_list_path, dtype=str, index_col=0)
        kospi50.index = pd.to_datetime(kospi50.index)
        year, month = target_date.year, target_date.month
        k_offset = 1 if month <= 6 else 7
        target_list_date = kospi50.index[(kospi50.index.year == year) & (kospi50.index.month == k_offset)]
        if len(target_list_date) == 0:
            target_list_date = [kospi50.index[kospi50.index <= target_date].max()]
        kospi_list = kospi50.loc[target_list_date[0]].dropna().unique().tolist()
        kospi_list = [str(c).strip() for c in kospi_list if str(c).strip()]
        kospi_list = [c.zfill(6) if c.isdigit() else c for c in kospi_list]

        # 2. Get returns
        all_rets = {}
        # We need data from target_date - 200 trading days to target_date + 60 trading days
        start_data = target_date - pd.DateOffset(days=400) # buffer
        end_data = target_date + pd.DateOffset(days=120) # buffer
        
        for code in kospi_list:
            fpath = os.path.join(self.stock_data_dir, f"{code}.csv")
            if os.path.exists(fpath):
                df = pd.read_csv(fpath, index_col=0, parse_dates=True)
                all_rets[code] = df['Close'].pct_change()

        rets_df = pd.DataFrame(all_rets).sort_index()
        past_rets = rets_df.loc[:target_date].iloc[-200:]
        future_rets = rets_df.loc[target_date:].iloc[1:61] # Exclude today, take next 60
        
        # 사용자가 요청한 엄격한 미래 60일 데이터 체크 (Today 기준 2026-01-01은 59일일 수 있어 Skip됨)
        if len(past_rets) < 200 or len(future_rets) < 60:
            return None 
            
        # 3. Calculate 1225 pairs
        x_vals, y_vals = [], []
        codes = list(all_rets.keys())
        total_pairs = (len(codes) * (len(codes)-1)) // 2
        pair_count = 0
        print(f"Starting Beta calculation for {len(codes)} stocks ({total_pairs} pairs)...")
        
        for i in range(len(codes)):
            for j in range(i+1, len(codes)):
                pair_count += 1
                if pair_count % 100 == 0:
                    print(f"Progress: {pair_count}/{total_pairs} pairs calculated...")
                c1, c2 = codes[i], codes[j]
                if c1 in past_rets.columns and c2 in past_rets.columns:
                    # Past Z
                    corr_p = past_rets[[c1, c2]].corr().iloc[0, 1]
                    if not np.isnan(corr_p):
                        x_vals.append(np.arctanh(np.clip(corr_p, -0.999, 0.999)))
                        # Future Z
                        corr_f = future_rets[[c1, c2]].corr().iloc[0, 1]
                        y_vals.append(np.arctanh(np.clip(corr_f, -0.999, 0.999)))

        if len(x_vals) < 100: return None
        
        # 4. Regression
        from scipy.stats import linregress
        res = linregress(x_vals, y_vals)
        return res.slope # This is the "Beta" we use

    def get_portfolio_snapshot(self, date, prev_date=None):
        if isinstance(date, str): date = pd.to_datetime(date)
        
        # 1. Basics & Universe
        kospi50_df = pd.read_csv(self.kospi50_list_path, dtype=str, index_col=0)
        kospi50_df.index = pd.to_datetime(kospi50_df.index)
        year, month = date.year, date.month
        k_offset = 1 if month <= 6 else 7
        u_dates = kospi50_df.index[(kospi50_df.index.year == year) & (kospi50_df.index.month == k_offset)]
        if len(u_dates) > 0:
            kospi_list = kospi50_df.loc[u_dates[0]].dropna().unique().tolist()
            kospi_list = [str(c).strip() for c in kospi_list if str(c).strip()]
            kospi_list = [c.zfill(6) if c.isdigit() else c for c in kospi_list]
        else:
            kospi_list = []

        # 2. Daily returns for MDP
        all_rets = {}
        all_prices = {}
        for code in kospi_list:
            fpath = os.path.join(self.stock_data_dir, f"{code}.csv")
            if os.path.exists(fpath):
                df = pd.read_csv(fpath, index_col=0, parse_dates=True)
                p = df['Close'].sort_index()
                all_prices[code] = p
                all_rets[code] = p.pct_change()
        daily_returns = pd.DataFrame(all_rets).loc[:date]

        # 3. 5-Week MA Filter
        eligible = []
        for code, p in all_prices.items():
            hist = p[:date]
            if not hist.empty:
                hist_w = hist.resample('W-FRI').last().dropna()
                if len(hist_w) >= 5 and hist.iloc[-1] > hist_w.iloc[-5:].mean():
                    eligible.append(code)

        # 4. Hedge Logic
        etf_data = self.load_local_etf()
        # Simplify: assume we are re-running for a rebalance day
        # In a real app, we need to track state or re-calculate history to find if it was 2 months bear
        is_bear_now = False
        etf_w = etf_data[:date]['Close'].resample('W-FRI').last().dropna()
        if len(etf_w) >= 20 and etf_w.iloc[-5:].mean() > etf_w.iloc[-20:].mean():
            is_bear_now = True
        
        # Mocking bear count history - in production we'd look back 2 monthly points
        hedge_ratio = 0.3 if is_bear_now else 0.0 # Placeholder logic
        invest_ratio = 1.0 - hedge_ratio

        weights = {}
        if hedge_ratio > 0: weights['114800'] = hedge_ratio

        if eligible and invest_ratio > 0:
            # Cointegration Pairing & MDP
            prices_60 = pd.DataFrame({s: all_prices[s].loc[:date].iloc[-60:] for s in eligible}).ffill().dropna(axis=1)
            eligible_synced = prices_60.columns.tolist()
            units_info = []
            if len(eligible_synced) >= 2:
                p_vals = []
                for j in range(len(eligible_synced)):
                    for k in range(j+1, len(eligible_synced)):
                        try:
                            _, p, _ = coint(prices_60[eligible_synced[j]], prices_60[eligible_synced[k]])
                            p_vals.append((p, eligible_synced[j], eligible_synced[k]))
                        except: pass
                p_vals.sort()
                matched = set()
                for p, s1, s2 in p_vals:
                    if p <= 0.05 and s1 not in matched and s2 not in matched:
                        matched.add(s1); matched.add(s2); units_info.append([s1, s2])
                for s in eligible:
                    if s not in matched: units_info.append([s])
                
                look_250 = daily_returns.iloc[-250:].fillna(0)
                u_rets = [(0.5*look_250[u[0]]+0.5*look_250[u[1]]) if len(u)==2 else look_250[u[0]] for u in units_info]
                df_u = pd.concat(u_rets, axis=1).fillna(0)
                
                # Beta Prediction (10-month average)
                # Load from excel and extend if needed
                beta_df = pd.read_excel(self.beta_file_path, sheet_name='P200_F60').set_index('Date')
                b_val = beta_df['Pred (10-Month Avg)'].iloc[-1] # Simplification
                
                adj_cov = self.get_adjusted_unit_cov(df_u, b_val)
                u_ws = self.calculate_mdp_weights(adj_cov.values)
                
                raw_stocks = {}
                for idx, w in enumerate(u_ws):
                    u, uw = units_info[idx], w * invest_ratio
                    if len(u) == 2: raw_stocks[u[0]] = uw*0.5; raw_stocks[u[1]] = uw*0.5
                    else: raw_stocks[u[0]] = uw
                
                # 1% Floor
                keep_stocks = {s: w for s, w in raw_stocks.items() if w >= 0.01}
                if keep_stocks:
                    total_keep = sum(keep_stocks.values())
                    for s, w in keep_stocks.items(): weights[s] = (w / total_keep) * invest_ratio
                else:
                    for s in eligible: weights[s] = (1.0/len(eligible)) * invest_ratio
                    
        return weights

    def run_full_backtest_and_save(self):
        """Runs backtest from 2016 to today and saves daily results/weights."""
        # This will be used to populate the 'results' and 'history' for the web app
        # For efficiency, we can reuse logic from RealV2Backtester
        pass # Implementation for initializing app data

    def calculate_shares(self, amount_krw, weights, prices, mode='both'):
        """
        Calculate integer shares guaranteeing the requested tolerance mode.
        mode: 'both' (+/- 5%), 'plus' (spend >= amount, up to +5%), 'minus' (spend <= amount, down to -5%)
        """
        shares = {}
        total_spent = 0
        exact_targets = {}
        
        # 1. Provide initial integer floors and track exact targets
        for code, weight in weights.items():
            price = prices.get(code)
            if price and price > 0:
                target_krw = amount_krw * weight
                exact_targets[code] = target_krw
                count = int(target_krw // price)  # Use floor division first
                shares[code] = count
                total_spent += count * price
                
        # 2. Greedy adjustment to hit the tolerance window
        # Calculate how much more we need to spend to hit the minimum required bound
        min_target = amount_krw * 0.95 if mode in ['both', 'minus'] else amount_krw
        max_target = amount_krw * 1.05 if mode in ['both', 'plus'] else amount_krw
        
        # Iteratively buy one share of the stock that is furthest below its exact target Krw weight
        # Only buy if it won't push us over the max target
        iteration_limit = 1000
        loops = 0
        
        while loops < iteration_limit:
            loops += 1
            
            # Check if we are inside the acceptable range
            diff_pct = (total_spent / amount_krw) - 1.0 if amount_krw > 0 else 0
            isValid = self._validate_mode(diff_pct, mode)
            
            # If we are valid AND we don't necessarily want to maximize (or we do?), let's just stop when valid
            if isValid and (mode == 'minus' or mode == 'both'):
                break 
                
            # If we are under the max target, try to find a share to add
            if total_spent < max_target:
                # Find the stock that is most "under-allocated" relative to target
                # Score = (Ideal Krw - Actual Krw Spent)
                best_code = None
                best_score = -float('inf')
                
                for code in shares.keys():
                    price = prices.get(code, 0)
                    if price <= 0: continue
                    current_capital = shares[code] * price
                    ideal_capital = exact_targets[code]
                    score = ideal_capital - current_capital
                    
                    # Only consider if adding one share doesn't blow past maximum allowable
                    if total_spent + price <= max_target:
                        if score > best_score:
                            best_score = score
                            best_code = code
                
                if best_code is not None:
                    shares[best_code] += 1
                    total_spent += prices[best_code]
                    continue # Successfully added
            
            # If we reach here, we either couldn't find a stock that fits under max_target, 
            # or we are already at/over max target.
            
            # If we are over the max_target (can happen if initial floor + 1 jumped over, though unlikely with floor)
            if total_spent > max_target:
                # Need to sell something. Find the stock most "over-allocated"
                worst_code = None
                worst_score = -float('inf')
                for code in shares.keys():
                    if shares[code] > 0:
                        price = prices.get(code, 0)
                        if price <= 0: continue
                        current_capital = shares[code] * price
                        ideal_capital = exact_targets[code]
                        score = current_capital - ideal_capital # Positive means over-allocated
                        if score > worst_score:
                            worst_score = score
                            worst_code = code
                
                if worst_code is not None:
                    shares[worst_code] -= 1
                    total_spent -= prices[worst_code]
                    continue
            
            # If no modifications can be made, break
            break

        diff_pct = (total_spent / amount_krw) - 1.0 if amount_krw > 0 else 0
        
        # Calculate final capital spent per stock
        stock_capital = {code: count * prices.get(code, 0) for code, count in shares.items()}
        
        return {
            "shares": shares,
            "prices": prices,
            "stock_capital": stock_capital,
            "total_spent": total_spent,
            "diff_pct": diff_pct,
            "is_valid": self._validate_mode(diff_pct, mode)
        }

    def _validate_mode(self, diff_pct, mode):
        if mode == 'both': return abs(diff_pct) <= 0.05
        if mode == 'plus': return 0.0 <= diff_pct <= 0.05
        if mode == 'minus': return -0.05 <= diff_pct <= 0.0
        return False

    def calculate_mdp_weights(self, cov_matrix):
        n = len(cov_matrix)
        if n == 0: return np.array([])
        if n == 1: return np.array([1.0])
        vols = np.sqrt(np.diag(cov_matrix))
        def objective(w):
            port_vol = np.sqrt(np.dot(w.T, np.dot(cov_matrix, w)))
            if port_vol < 1e-9: return 0
            return -(np.dot(w, vols) / port_vol)
        constraints = ({'type': 'eq', 'fun': lambda x: np.sum(x) - 1.0})
        bounds = [(0, 1.0) for _ in range(n)]
        initial_w = np.array([1.0 / n] * n)
        res = minimize(objective, initial_w, method='SLSQP', bounds=bounds, constraints=constraints)
        return res.x / np.sum(res.x) if res.success else initial_w

    def get_adjusted_unit_cov(self, unit_returns_df, beta_val):
        corr_mat = unit_returns_df.corr().values
        z_std = np.arctanh(np.clip(corr_mat, -0.999, 0.999))
        mask = np.triu_indices_from(z_std, k=1)
        avg_z = np.nanmean(z_std[mask]) if len(z_std[mask]) > 0 else 0
        corr_pred = np.tanh((1 - beta_val) * avg_z + beta_val * z_std)
        np.fill_diagonal(corr_pred, 1.0)
        std_d = unit_returns_df.std().values * np.sqrt(252)
        adj_cov = np.outer(std_d, std_d) * corr_pred
        return pd.DataFrame(adj_cov, index=unit_returns_df.columns, columns=unit_returns_df.columns)
