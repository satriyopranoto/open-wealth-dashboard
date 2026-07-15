from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
import yfinance as yf
import pandas as pd
import numpy as np
from yahooquery import Screener
from bokeh_chart import generate_chart
import os
import json
import time
import threading
import io
import xml.etree.ElementTree as ET
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from pygooglenews import GoogleNews
from log_utils import log_action, _get_client_ip, read_recent_logs
from collections import defaultdict

# Load environment variables dari file .env
load_dotenv()

app = Flask(__name__)

# Enable CORS for all routes
CORS(app, resources={r"/*": {"origins": "*"}})

# Load konfigurasi dari environment variables
app.config['API_BASE_URL'] = os.getenv('API_BASE_URL', 'http://localhost:5000')
app.config['FLASK_PORT'] = int(os.getenv('FLASK_PORT', 5000))

# Serve assets (favicon, etc.)
@app.route('/assets/<path:filename>')
def serve_assets(filename):
    return send_from_directory('assets', filename)

# Konfigurasi waktu download
RETRY_DELAY = 5
MAX_RETRIES = 3

def _default_basis_adx_ip():
    return {
        'is_running': False,
        'current_ticker': '',
        'progress': 0,
        'total': 0,
        'results': [],
        'status': 'idle',
        'message': '',
        'run_id': 0
    }

basis_adx_screener_progress_map = defaultdict(_default_basis_adx_ip)

def _default_basis_adx_mt_ip():
    return {
        'is_running': False,
        'current_ticker': '',
        'progress': 0,
        'total': 0,
        'results': [],
        'status': 'idle',
        'message': '',
        'run_id': 0
    }

basis_adx_mt_screener_progress_map = defaultdict(_default_basis_adx_mt_ip)

def _default_fundamental_ip():
    return {
        'is_running': False,
        'current_ticker': '',
        'progress': 0,
        'total': 0,
        'results': [],
        'status': 'idle',
        'message': '',
        'run_id': 0
    }

fundamental_screener_progress_map = defaultdict(_default_fundamental_ip)

# Rate limit threshold dalam menit
RATE_LIMIT_MINUTES = 60
SCREENER_COOLDOWN_MINUTES = 30  # BB Screener minimal jeda antar eksekusi
CACHE_DIR = os.path.join(os.path.dirname(__file__), 'cache')
os.makedirs(CACHE_DIR, exist_ok=True)

# Data sync lock untuk multi-user
DATA_SYNC_LOCK_FILE = os.path.join(CACHE_DIR, '.data_sync_lock')

def acquire_data_sync_lock(client_ip):
    """Coba acquire lock untuk data sync. Returns (success, owner_ip)."""
    if os.path.exists(DATA_SYNC_LOCK_FILE):
        try:
            with open(DATA_SYNC_LOCK_FILE, 'r') as f:
                owner_ip = f.read().strip()
            if owner_ip == client_ip:
                return True, client_ip
            return False, owner_ip
        except Exception:
            pass
    try:
        with open(DATA_SYNC_LOCK_FILE, 'w') as f:
            f.write(client_ip)
        return True, client_ip
    except Exception:
        return False, 'unknown'

def release_data_sync_lock():
    """Release lock untuk data sync."""
    try:
        if os.path.exists(DATA_SYNC_LOCK_FILE):
            os.remove(DATA_SYNC_LOCK_FILE)
    except Exception:
        pass

# Add CORS headers to all responses
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

def get_cache_file_path(ticker):
    """
    Mendapatkan path file cache untuk ticker tertentu
    """
    return os.path.join(CACHE_DIR, f"{ticker}.csv")

def get_fundamental_cache_file(ticker):
    """
    Mendapatkan path file cache untuk data fundamental
    """
    return os.path.join(CACHE_DIR, f"{ticker}_fundamental.json")

def touch_screener_marker(screener_name):
    """Update marker file untuk screener cache."""
    marker_file = os.path.join(CACHE_DIR, f".screener_{screener_name}_marker.txt")
    try:
        with open(marker_file, 'w') as f:
            f.write(datetime.now().isoformat())
    except Exception as e:
        print(f"Error touch_screener_marker {screener_name}: {e}")

def get_screener_cache_file(screener_name):
    """
    Mendapatkan path file cache untuk data screener
    """
    return os.path.join(CACHE_DIR, f"screener_{screener_name}.csv")

def load_cached_screener(screener_name):
    """
    Memuat data screener dari cache jika ada dan masih valid (TTL 1 jam).
    Mengembalikan tuple (data, metadata, error)
    """
    cache_file = get_screener_cache_file(screener_name)
    
    if not os.path.exists(cache_file):
        return None, None, None
    
    try:
        with open(cache_file, 'r') as f:
            lines = f.readlines()
        
        if len(lines) < 2:
            print(f"Cache screener tidak valid untuk {screener_name} (terlalu sedikit baris)")
            return None, None, None
        
        metadata_line = lines[0].strip()
        if not metadata_line.startswith('#'):
            print(f"Format cache screener tidak valid untuk {screener_name}")
            return None, None, None
        
        metadata = json.loads(metadata_line[1:].strip())
        cache_mtime = os.path.getmtime(cache_file)
        
        # TTL 1 jam — fallback sederhana
        cached_time = datetime.fromisoformat(metadata['timestamp'])
        age = datetime.now() - cached_time
        
        if age.total_seconds() > 1 * 60 * 60:
            print(f"Cache screener untuk {screener_name} sudah kadaluarsa ({age.total_seconds() / 3600:.1f} jam)")
            return None, None, None
        print(f"Data screener {screener_name} dimuat dari cache (usia: {age.total_seconds() / 3600:.1f} jam)")
        
        csv_content = ''.join(lines[1:])
        data = pd.read_csv(io.StringIO(csv_content))
        
        return data, metadata, None
        
    except Exception as e:
        print(f"Error membaca cache screener: {str(e)}")
        import traceback
        traceback.print_exc()
        return None, None, None

def save_screener_to_cache(screener_name, data):
    """
    Menyimpan data screener ke cache dalam format CSV dengan metadata
    """
    cache_file = get_screener_cache_file(screener_name)
    
    try:
        metadata = {
            'timestamp': datetime.now().isoformat(),
            'screener_name': screener_name
        }
        
        csv_buffer = io.StringIO()
        data.to_csv(csv_buffer, index=False)
        csv_content = csv_buffer.getvalue()
        
        with open(cache_file, 'w') as f:
            f.write(f"# {json.dumps(metadata)}\n")
            f.write(csv_content)
        
        print(f"Data screener {screener_name} disimpan ke cache: {cache_file}")
        return True
    except Exception as e:
        print(f"Error menyimpan cache screener: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def clean_float(val):
    if val is None:
        return None
    try:
        fval = float(val)
        if np.isnan(fval) or np.isinf(fval):
            return None
        return fval
    except (ValueError, TypeError):
        return None

def clean_nan_in_records(records):
    cleaned = []
    for record in records:
        cleaned_rec = {}
        for k, v in record.items():
            if v is None:
                cleaned_rec[k] = None
            elif isinstance(v, float) and (np.isnan(v) or np.isinf(v)):
                cleaned_rec[k] = None
            elif isinstance(v, dict):
                cleaned_rec[k] = clean_nan_in_records([v])[0]
            elif isinstance(v, list):
                cleaned_rec[k] = [clean_nan_in_records([item])[0] if isinstance(item, dict) else item for item in v]
            else:
                cleaned_rec[k] = v
        cleaned.append(cleaned_rec)
    return cleaned

def check_fundamental_run_status(market):
    """
    Check if we can use cached screener results or if we need to pull fresh data.
    Returns: (use_cache, run_timestamp)
    """
    screener_name = f"{market.lower()}-fundamental"
    cache_file = get_screener_cache_file(screener_name)
    run_file = os.path.join(CACHE_DIR, f'.fundamental_{market.lower()}_run.txt')
    
    # Check if cached results file exists
    if not os.path.exists(cache_file):
        return False, None
        
    # Check if run file exists
    if not os.path.exists(run_file):
        return False, None
        
    try:
        with open(run_file, 'r') as f:
            timestamp_str = f.read().strip()
        last_run_time = datetime.fromisoformat(timestamp_str)
        age = datetime.now() - last_run_time
        
        # If age is not > 24 hours
        if age < timedelta(hours=24):
            return True, timestamp_str
    except Exception as e:
        print(f"Error checking fundamental run file: {e}")
        
    return False, None

def load_cached_fundamental_screener(screener_name):
    """
    Memuat data fundamental screener dari cache tanpa membatasi dengan TTL 1 jam.
    """
    cache_file = get_screener_cache_file(screener_name)
    if not os.path.exists(cache_file):
        return None, None, None
    try:
        with open(cache_file, 'r') as f:
            lines = f.readlines()
        if len(lines) < 2:
            return None, None, None
        metadata_line = lines[0].strip()
        if not metadata_line.startswith('#'):
            return None, None, None
        metadata = json.loads(metadata_line[1:].strip())
        csv_content = ''.join(lines[1:])
        data = pd.read_csv(io.StringIO(csv_content))
        return data, metadata, None
    except Exception as e:
        print(f"Error membaca cache fundamental screener: {str(e)}")
        return None, None, str(e)

    """
    Memuat data fundamental dari cache jika ada dan masih valid (maksimal 1 hari)
    """
    cache_file = get_fundamental_cache_file(ticker)
    
    if not os.path.exists(cache_file):
        return None, None
    
    try:
        with open(cache_file, 'r') as f:
            metadata = json.load(f)
        
        # Cek apakah cache masih valid (maksimal 1 hari)
        cached_time = datetime.fromisoformat(metadata['timestamp'])
        age = datetime.now() - cached_time
        
        if age.total_seconds() > 24 * 60 * 60:  # 24 jam
            print(f"Cache fundamental untuk {ticker} sudah kadaluarsa")
            return None, None
        
        print(f"Data fundamental {ticker} dimuat dari cache")
        data = metadata['data']
        # Bersihin NaN dari data cache (safety net)
        if isinstance(data, dict):
            for key in list(data.keys()):
                if isinstance(data[key], float):
                    data[key] = clean_float(data[key])
        # Safety net: pastiin long_term_debt_to_equity dalam format desimal
        if 'long_term_debt_to_equity' in data and data['long_term_debt_to_equity'] is not None:
            if data['long_term_debt_to_equity'] > 1.0:
                data['long_term_debt_to_equity'] = round(data['long_term_debt_to_equity'] / 100.0, 6)
        return data, None
        
    except Exception as e:
        print(f"Error membaca cache fundamental: {str(e)}")
        return None, None

def save_fundamental_to_cache(ticker, data):
    """
    Menyimpan data fundamental ke cache
    """
    cache_file = get_fundamental_cache_file(ticker)
    
    try:
        metadata = {
            'timestamp': datetime.now().isoformat(),
            'ticker': ticker,
            'data': data
        }
        
        with open(cache_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        print(f"Data fundamental {ticker} disimpan ke cache")
        return True
    except Exception as e:
        print(f"Error menyimpan cache fundamental: {str(e)}")
        return False

def download_fundamental_data(ticker, force_refresh=False):
    """
    Download data fundamental dari Yahoo Finance
    """
    # Cek cache jika tidak force refresh
    if not force_refresh:
        cached_data, error = load_cached_fundamental(ticker)
        if cached_data is not None:
            return cached_data, None
    
    try:
        print(f"Mengambil data fundamental untuk {ticker}...")
        stock = yf.Ticker(ticker)
        
        # Ambil info
        info = stock.info
        
        # Ekstrak metrik yang diminta
        fundamental = {
            'net_profit_margin': info.get('profitMargins'),
            'operating_margin': info.get('operatingMargins'),
            'free_cash_flow': info.get('freeCashflow'),
            'operating_cash_flow': info.get('operatingCashflow'),
            'payout_ratio': info.get('payoutRatio'),
            'long_term_debt_to_equity': info.get('debtToEquity') / 100.0 if info.get('debtToEquity') is not None else None,
            'return_on_assets': info.get('returnOnAssets'),
            'return_on_equity': info.get('returnOnEquity'),
            'revenue_growth': info.get('revenueGrowth'),
            'eps_growth': info.get('earningsGrowth'),
            'trailing_pe': info.get('trailingPE'),
            'peg_ratio': info.get('pegRatio'),
            'company_description': info.get('longBusinessSummary')
        }

        # PE-based fair price: forwardEps * trailingPE
        # Menjawab: "jika laba tumbuh sesuai proyeksi analis dan multiple PE tetap, berapa target harganya?"
        forward_eps = info.get('forwardEps')
        pe_current  = info.get('trailingPE')
        if forward_eps and pe_current:
            fundamental['fair_price_pe'] = forward_eps * pe_current
        else:
            fundamental['fair_price_pe'] = None

        # DCF-based fair price: dynamic WACC + 3-year avg FCF projection + terminal value
        try:
            cash_flow = stock.cashflow
            balance_sheet = stock.balance_sheet if hasattr(stock, 'balance_sheet') else getattr(stock, 'balancesheet', None)
            income_statement = stock.income_stmt if hasattr(stock, 'income_stmt') else getattr(stock, 'income_statement', None)

            if cash_flow is None or cash_flow.empty or balance_sheet is None or balance_sheet.empty or income_statement is None or income_statement.empty:
                raise ValueError("Incomplete financial data for DCF")

            idx = cash_flow.index

            # --- 3-year average Free Cash Flow ---
            if 'Free Cash Flow' in idx:
                fcf_series = cash_flow.loc['Free Cash Flow'].iloc[:3]
            elif 'Operating Cash Flow' in idx:
                capex_key = 'Capital Expenditure' if 'Capital Expenditure' in idx else 'Capital Expenditures'
                ocf_series = cash_flow.loc['Operating Cash Flow'].iloc[:3]
                capex_series = abs(cash_flow.loc[capex_key].iloc[:3])
                fcf_series = ocf_series - capex_series
            else:
                raise KeyError("Neither 'Free Cash Flow' nor 'Operating Cash Flow' found in cash flow statement")
            avg_fcf = fcf_series.mean()

            # --- Dynamic WACC ---
            beta = info.get('beta', 1.0)
            market_cap = info.get('marketCap', 0)

            risk_free_rate = 0.065
            market_risk_premium = 0.055
            terminal_growth = 0.04

            cost_of_equity = risk_free_rate + (beta * market_risk_premium)

            total_debt = balance_sheet.loc['Total Debt'].iloc[0] if 'Total Debt' in balance_sheet.index else 0
            interest_expense = abs(income_statement.loc['Interest Expense'].iloc[0]) if 'Interest Expense' in income_statement.index else 0
            tax_provision = income_statement.loc['Tax Provision'].iloc[0] if 'Tax Provision' in income_statement.index else 0
            pretax_income = income_statement.loc['Pretax Income'].iloc[0] if 'Pretax Income' in income_statement.index else 0

            cost_of_debt = interest_expense / total_debt if total_debt > 0 else 0
            tax_rate = tax_provision / pretax_income if pretax_income > 0 else 0

            total_capital = market_cap + total_debt
            weight_of_equity = market_cap / total_capital if total_capital > 0 else 1
            weight_of_debt = total_debt / total_capital if total_capital > 0 else 0

            wacc = (weight_of_equity * cost_of_equity) + (weight_of_debt * cost_of_debt * (1 - tax_rate))

            shares = info.get('sharesOutstanding')
            g = max(info.get('earningsGrowth') or 0.10, 0.0)
            gn = terminal_growth

            total_pv = 0
            fcf_proj = avg_fcf
            for t in range(1, 6):
                fcf_proj *= (1 + g)
                total_pv += fcf_proj / ((1 + wacc) ** t)

            tv = (fcf_proj * (1 + gn)) / (wacc - gn)
            pv_tv = tv / ((1 + wacc) ** 5)

            fundamental['fair_price_dcf'] = (total_pv + pv_tv) / shares if shares else None
        except Exception:
            fundamental['fair_price_dcf'] = None
        
        # Bersihin NaN dari semua nilai numerik
        for key in list(fundamental.keys()):
            if isinstance(fundamental[key], float):
                fundamental[key] = clean_float(fundamental[key])
        
        # Ambil Major Holders
        try:
            major_holders = stock.major_holders
            major_holders_list = []
            if major_holders is not None and not major_holders.empty:
                # Handle MultiIndex columns if present
                if isinstance(major_holders.columns, pd.MultiIndex):
                    major_holders.columns = major_holders.columns.get_level_values(0)
                
                # Cek format: apakah breakdown (1 kolom) atau list (multiple kolom)
                if major_holders.shape[1] == 1:
                    # Format breakdown untuk saham Indonesia
                    for idx, row in major_holders.iterrows():
                        label = str(idx).replace('PercentHeld', '%').replace('Count', ' Count')
                        value = row.iloc[0]
                        if pd.notna(value):
                            if 'Count' in label:
                                major_holders_list.append({'holder': label, 'shares': str(int(value)), 'percentage': '-'})
                            else:
                                # yfinance returns decimal, perlu dikali 100
                                pct = float(value) * 100 if isinstance(value, (int, float)) else value
                                major_holders_list.append({'holder': label, 'shares': '-', 'percentage': f"{pct:.2f}%"})
                else:
                    # Format list untuk US stocks
                    for idx, row in major_holders.head(10).iterrows():
                        try:
                            holder_data = {
                                'holder': str(row.iloc[0]) if pd.notna(row.iloc[0]) else '',
                                'shares': str(row.iloc[1]) if pd.notna(row.iloc[1]) else '',
                                'percentage': str(row.iloc[2]) if pd.notna(row.iloc[2]) else ''
                            }
                            major_holders_list.append(holder_data)
                        except Exception:
                            continue
            fundamental['major_holders'] = major_holders_list
            print(f"✓ Major holders untuk {ticker}: {len(major_holders_list)} entries")
        except Exception as e:
            import traceback
            print(f"⚠ Error mengambil major holders: {str(e)}")
            traceback.print_exc()
            fundamental['major_holders'] = []
        
        # Ambil Institutional Holders
        try:
            institutional_holders = stock.institutional_holders
            institutional_holders_list = []
            if institutional_holders is not None and not institutional_holders.empty:
                # Handle MultiIndex columns if present
                if isinstance(institutional_holders.columns, pd.MultiIndex):
                    institutional_holders.columns = institutional_holders.columns.get_level_values(0)
                
                print(f"Debug institutional_holders columns: {institutional_holders.columns.tolist()}")
                print(f"Debug institutional_holders shape: {institutional_holders.shape}")
                print(f"Debug institutional_holders sample:\n{institutional_holders.head(2)}")
                
                # Ambil max 10 entries
                for idx, row in institutional_holders.head(10).iterrows():
                    try:
                        # Reset index agar idx tidak masuk ke data
                        row = row.reset_index(drop=True)
                        holder = str(row.iloc[0]) if pd.notna(row.iloc[0]) else ''
                        shares = str(row.iloc[1]) if pd.notna(row.iloc[1]) else ''
                        # Percentage typically di column 3 (% Out) atau 2 (berdasarkan data)
                        # yfinance returns decimal (0.07), perlu dikali 100 untuk tampilkan %
                        pct_val = None
                        if len(row) > 2 and pd.notna(row.iloc[2]):
                            try:
                                pct_val = float(row.iloc[2]) * 100
                            except:
                                pass
                        elif len(row) > 3 and pd.notna(row.iloc[3]):
                            try:
                                pct_val = float(row.iloc[3]) * 100
                            except:
                                pass
                        percentage = f"{pct_val:.2f}%" if pct_val is not None else '-'
                        institutional_holders_list.append({
                            'holder': holder,
                            'shares': shares,
                            'percentage': percentage
                        })
                    except Exception as e2:
                        print(f"Error parsing row: {e2}")
                        continue
            fundamental['institutional_holders'] = institutional_holders_list
            print(f"✓ Institutional holders untuk {ticker}: {len(institutional_holders_list)} entries")
        except Exception as e:
            import traceback
            print(f"⚠ Error mengambil institutional holders: {str(e)}")
            traceback.print_exc()
            fundamental['institutional_holders'] = []
        
        # Debug: cek apakah company_description ada
        if fundamental['company_description']:
            print(f"✓ Company description untuk {ticker} ditemukan (panjang: {len(fundamental['company_description'])} karakter)")
        else:
            print(f"⚠ Company description untuk {ticker} tidak tersedia dari Yahoo Finance")

        # Ambil Events (Earnings, Dividends, Splits)
        try:
            events_data = {'earnings': [], 'dividends': [], 'splits': []}

            # --- Earnings: pakai earnings_dates (lebih reliable dari ticker.events) ---
            try:
                earnings_df = stock.earnings_dates
                if earnings_df is not None and not earnings_df.empty:
                    for idx, row in earnings_df.head(8).iterrows():
                        try:
                            date_str = idx.isoformat() if hasattr(idx, 'isoformat') else str(idx)
                            eps_est = eps_actual = eps_surprise = None
                            for col in row.index:
                                cl = col.lower()
                                val = row[col]
                                if not pd.notna(val):
                                    continue
                                if 'estimate' in cl:
                                    eps_est = float(val)
                                elif 'reported' in cl or ('eps' in cl and 'estimate' not in cl and 'surprise' not in cl):
                                    eps_actual = float(val)
                                elif 'surprise' in cl or '%' in cl:
                                    eps_surprise = float(val)
                            events_data['earnings'].append({
                                'date': date_str,
                                'eps_estimate': eps_est,
                                'eps_actual': eps_actual,
                                'eps_surprise_pct': eps_surprise,
                            })
                        except Exception:
                            continue
            except Exception as e:
                print(f"⚠ earnings_dates error: {e}")

            # Fallback ke ticker.events['Earnings'] jika earnings_dates kosong
            if not events_data['earnings']:
                try:
                    raw_events = stock.events
                    if raw_events is not None:
                        ef = raw_events.get('Earnings')
                        if ef is not None and not ef.empty:
                            for idx, row in ef.iterrows():
                                try:
                                    date_str = idx.isoformat() if hasattr(idx, 'isoformat') else str(idx)
                                    events_data['earnings'].append({
                                        'date': date_str,
                                        'eps_estimate': float(row['EPS Estimate']) if 'EPS Estimate' in row and pd.notna(row['EPS Estimate']) else None,
                                        'eps_actual': float(row['EPS Actual']) if 'EPS Actual' in row and pd.notna(row['EPS Actual']) else None,
                                        'eps_surprise_pct': float(row['EPSSurprisePct']) if 'EPSSurprisePct' in row and pd.notna(row['EPSSurprisePct']) else None,
                                    })
                                except Exception:
                                    continue
                except Exception as e:
                    print(f"⚠ ticker.events earnings fallback error: {e}")

            # --- Dividends & Splits dari ticker.events ---
            try:
                raw_events = stock.events
                if raw_events is not None:
                    divs = raw_events.get('Dividends')
                    if divs is not None and len(divs) > 0:
                        for date_idx, amount in divs.items():
                            try:
                                events_data['dividends'].append({
                                    'date': date_idx.isoformat() if hasattr(date_idx, 'isoformat') else str(date_idx),
                                    'amount': float(amount) if pd.notna(amount) else None,
                                })
                            except Exception:
                                continue

                    splits = raw_events.get('Splits')
                    if splits is not None and len(splits) > 0:
                        for date_idx, ratio in splits.items():
                            try:
                                events_data['splits'].append({
                                    'date': date_idx.isoformat() if hasattr(date_idx, 'isoformat') else str(date_idx),
                                    'ratio': float(ratio) if pd.notna(ratio) else None,
                                })
                            except Exception:
                                continue
            except Exception as e:
                print(f"⚠ ticker.events div/splits error: {e}")

            fundamental['events'] = events_data
            print(f"✓ Events {ticker}: {len(events_data['earnings'])} earnings, {len(events_data['dividends'])} dividends, {len(events_data['splits'])} splits")
        except Exception as e:
            print(f"⚠ Error mengambil events: {str(e)}")
            fundamental['events'] = {'earnings': [], 'dividends': [], 'splits': []}

        # Simpan ke cache
        save_fundamental_to_cache(ticker, fundamental)
        
        return fundamental, None
        
    except Exception as e:
        print(f"Error mengambil data fundamental: {str(e)}")
        return None, f"Gagal mengambil data fundamental: {str(e)}"

def load_cached_data(ticker):
    """
    Memuat data dari cache jika ada dan masih valid (maksimal 1 hari)
    Mengembalikan tuple (data, metadata, error)
    """
    cache_file = get_cache_file_path(ticker)
    
    if not os.path.exists(cache_file):
        return None, None, None
    
    try:
        # Baca semua baris
        with open(cache_file, 'r') as f:
            lines = f.readlines()
        
        if len(lines) < 2:
            print(f"Cache tidak valid untuk {ticker} (terlalu sedikit baris)")
            return None, None, None
        
        # Baris pertama adalah metadata JSON (dimulai dengan #)
        metadata_line = lines[0].strip()
        if not metadata_line.startswith('#'):
            print(f"Format cache tidak valid untuk {ticker}")
            return None, None, None
        
        # Parse metadata (hapus karakter #)
        metadata = json.loads(metadata_line[1:].strip())
        
        # Cek apakah cache masih valid (maksimal 1 hari)
        cached_time = datetime.fromisoformat(metadata['timestamp'])
        age = datetime.now() - cached_time
        
        if age.total_seconds() > 1 * 60 * 60:  # 1 jam
            print(f"Cache untuk {ticker} sudah kadaluarsa ({age.total_seconds() / 3600:.1f} jam yang lalu)")
            return None, None, None
        
        # Load data CSV dari baris kedua dst
        csv_content = ''.join(lines[1:])
        data = pd.read_csv(io.StringIO(csv_content), index_col=0, parse_dates=True, date_format='ISO8601')
        
        # Pastikan kolom numerik bertipe float
        numeric_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        for col in numeric_cols:
            if col in data.columns:
                data[col] = pd.to_numeric(data[col], errors='coerce')
        
        print(f"Data {ticker} dimuat dari cache (usia: {age.total_seconds() / 3600:.1f} jam)")
        return data, metadata, None
        
    except Exception as e:
        print(f"Error membaca cache: {str(e)}")
        import traceback
        traceback.print_exc()
        return None, None, None

def save_data_to_cache(ticker, data):
    """
    Menyimpan data ke cache dalam format CSV dengan metadata
    """
    cache_file = get_cache_file_path(ticker)
    
    try:
        # Simpan metadata di baris pertama sebagai komentar JSON
        metadata = {
            'timestamp': datetime.now().isoformat(),
            'ticker': ticker
        }
        
        # Simpan data CSV ke StringIO dulu
        csv_buffer = io.StringIO()
        data.to_csv(csv_buffer)
        csv_content = csv_buffer.getvalue()
        
        # Tulis ke file: metadata + CSV
        with open(cache_file, 'w') as f:
            # Baris pertama: metadata JSON dengan prefix #
            f.write(f"# {json.dumps(metadata)}\n")
            # Baris kedua dst: data CSV
            f.write(csv_content)
        
        print(f"Data {ticker} disimpan ke cache: {cache_file}")
        return True
    except Exception as e:
        print(f"Error menyimpan cache: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def download_stock_data(ticker, period="400d", force_refresh=False):
    """
    Fungsi helper untuk download data dengan retry logic sederhana
    force_refresh: jika True, akan download ulang meskipun ada cache
    Mengembalikan tuple (data, metadata, error)
    """
    # Cek cache jika tidak force refresh
    if not force_refresh:
        cached_data, metadata, error = load_cached_data(ticker)
        if cached_data is not None:
            return cached_data, metadata, None
    
    # Download data baru
    for attempt in range(MAX_RETRIES):
        try:
            print(f"Mencoba mengambil data untuk {ticker} (Upaya {attempt + 1}/{MAX_RETRIES})...")
            # Mengambil data dengan progress False agar tidak muncul progress bar yang mengganggu
            data = yf.download(ticker, period=period, progress=False)

            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)

            if data.empty:
                return None, None, f"Data untuk {ticker} tidak ditemukan."
            
            # Simpan ke cache
            save_data_to_cache(ticker, data)
            
            # Buat metadata baru untuk data yang baru di-download
            metadata = {
                'timestamp': datetime.now().isoformat(),
                'ticker': ticker
            }
                
            return data, metadata, None
            
        except Exception as e:
            print(f"Gagal mengambil data (Upaya {attempt + 1}): {str(e)}")
            if attempt < MAX_RETRIES - 1:
                import time
                print(f"Menunggu {RETRY_DELAY} detik sebelum mencoba lagi...")
                time.sleep(RETRY_DELAY)
            else:
                return None, None, f"Terjadi error jaringan setelah {MAX_RETRIES} percobaan: {str(e)}"

def calculate_rsi(close_prices, period=14):
    """
    Menghitung RSI menggunakan rumus standar
    """
    close_prices = close_prices.astype(float)
    delta = close_prices.diff()
    
     # 2. Pisahkan Gain (Kenaikan) dan Loss (Penurunan)
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    # 3. Hitung Average Gain dan Average Loss (SMA awal)
    # Menggunakan .ewm(com=14).mean() adalah cara umum yang lebih baik untuk RSI daripada SMA sederhana.
    avg_gain = gain.ewm(com=14 - 1, min_periods=14).mean()
    avg_loss = loss.ewm(com=14 - 1, min_periods=14).mean()

    # Hindari pembagian nol jika ada - gunakan where untuk replacement element-wise
    rs = avg_gain / avg_loss.replace(0, 1e-10)
    
    # 5. Hitung RSI
    rsi = 100 - (100 / (1 + rs))
    
    return rsi
def calculate_sl(df, atr_multiple=2.8, atr_period=10):
    """
    Konversi logika Pine Script ke Python:
    erof = atr_multiple * atr_period
    r = highest(high, ero), s = lowest(low, ero)
    sl = ac == 1 ? s : r
    """
    # 1. Hitung Periode Lookback (ero)
    ero = int(atr_multiple * atr_period)
    
    # 2. Hitung Highest High dan Lowest Low (Donchian Channel)
    # Gunakan .shift(1) karena Pine Script menggunakan r[1] dan s[1]
    r_prev = df['High'].rolling(window=ero).max().shift(1)
    s_prev = df['Low'].rolling(window=ero).min().shift(1)
    
    # Current r dan s untuk output akhir
    r_curr = df['High'].rolling(window=ero).max()
    s_curr = df['Low'].rolling(window=ero).min()

    # 3. Hitung Variabel 'ab' (Trigger arah)
    # high > r[1] ? 1 : (low < s[1] ? -1 : 0)
    ab = np.where(df['High'] > r_prev, 1, 
                  np.where(df['Low'] < s_prev, -1, 0))
    
    # 4. Hitung Variabel 'ac' (Trend Direction)
    # ac = ta.valuewhen(ab != 0, ab, 0)
    # Di Pandas: ffill() digunakan untuk mengambil nilai non-zero terakhir
    ac = pd.Series(ab).replace(0, np.nan).ffill().fillna(0)
    
    # 5. Hitung Final SL
    # sl = ac == 1 ? s : r
    sl = np.where(ac == 1, s_curr, r_curr)
    
    return pd.Series(sl, index=df.index)

def calculate_bollinger_bands(df, period=20, num_std=2):
    """
    Menghitung Bollinger Bands
    - Middle Band = SMA period hari
    - Upper Band = Middle + (num_std * std dev)
    - Lower Band = Middle - (num_std * std dev)
    """
    close = df['Close'].astype(float)
    middle = close.rolling(window=period).mean()
    std = close.rolling(window=period).std()
    upper = middle + (num_std * std)
    lower = middle - (num_std * std)
    return upper, middle, lower


def calculate_adx(df, period=14):
    """
    Menghitung ADX, +DI (PDI), dan -DI (MDI)
    Menggunakan Wilder's Smoothing via EWM
    """
    high = df['High'].astype(float)
    low = df['Low'].astype(float)
    close = df['Close'].astype(float)

    # True Range
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)

    # Directional Movement
    up_move = high - high.shift(1)
    down_move = low.shift(1) - low
    plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0), index=df.index)
    minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0), index=df.index)

    # Wilder's Smoothing (alpha = 1/period ≈ EMA)
    alpha = 1.0 / period
    smoothed_tr = tr.ewm(alpha=alpha, adjust=False, min_periods=period).mean()
    smoothed_plus = plus_dm.ewm(alpha=alpha, adjust=False, min_periods=period).mean()
    smoothed_minus = minus_dm.ewm(alpha=alpha, adjust=False, min_periods=period).mean()

    # +DI / -DI  (PDI / MDI)
    pdi = 100 * smoothed_plus / smoothed_tr.replace(0, np.nan)
    mdi = 100 * smoothed_minus / smoothed_tr.replace(0, np.nan)

    # DX
    dm_sum = pdi + mdi
    dx = 100 * (pdi - mdi).abs() / dm_sum.replace(0, np.nan)

    # ADX = smoothed DX
    adx = dx.ewm(alpha=alpha, adjust=False, min_periods=period).mean()

    return adx, pdi, mdi


@app.route('/', methods=['GET'])
def index():
    """Halaman Landing Page"""
    log_action('landing_page', 'view')
    return render_template('index.html', api_base_url=app.config['API_BASE_URL'])

@app.route('/refresh', methods=['POST', 'OPTIONS'])
def refresh_data():
    """
    Endpoint untuk refresh data - mendownload ulang data dari Yahoo Finance
    """
    # Handle OPTIONS request for CORS preflight
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        return response
    
    ticker = request.form.get('ticker', '').strip().upper()
    
    if not ticker:
        log_action('refresh', 'refresh_data', params={'ticker': ticker}, status='error', detail='Ticker kosong')
        return jsonify({"status": "error", "message": "Ticker tidak boleh kosong."}), 400

    start_time = time.time()

    try:
        print(f"Refreshing data untuk ticker: {ticker}")

        data, metadata, error_msg = download_stock_data(ticker, period="400d", force_refresh=True)

        if error_msg:
            duration = (time.time() - start_time) * 1000
            log_action('refresh', 'refresh_data', params={'ticker': ticker}, status='error',
                      detail=error_msg, duration_ms=duration)
            return jsonify({"status": "error", "message": error_msg}), 500

        if data is None or data.empty:
            duration = (time.time() - start_time) * 1000
            log_action('refresh', 'refresh_data', params={'ticker': ticker}, status='error',
                      detail='Data kosong', duration_ms=duration)
            return jsonify({"status": "error", "message": "Data saham tidak ditemukan atau ada masalah."}), 500

        duration = (time.time() - start_time) * 1000
        log_action('refresh', 'refresh_data', params={'ticker': ticker}, status='success', duration_ms=duration)
        return jsonify({
            "status": "success",
            "message": f"Data untuk {ticker} berhasil direfresh!"
        })
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        duration = (time.time() - start_time) * 1000
        log_action('refresh', 'refresh_data', params={'ticker': ticker}, status='error',
                  detail=str(e), duration_ms=duration)
        return jsonify({"status": "error", "message": f"Terjadi kesalahan saat refresh: {str(e)}"}), 500

@app.route('/chart_html/<ticker>', methods=['GET'])
def serve_chart_html(ticker):
    """Serve standalone Bokeh chart HTML for iframe embedding.
    Supports timeframe parameter: ?tf=1d (default), 1h, 1wk, 1mo
    """
    from bokeh_chart import generate_chart
    import yfinance as yf
    import numpy as np
    
    # Timeframe mapping
    tf = request.args.get('tf', '1d')
    tf_config = {
        '1h':  {'period': '30d',  'interval': '1h',  'label': 'H1'},
        '4h':  {'period': '60d',  'interval': '1h',  'label': 'H4'},
        '1d':  {'period': '400d', 'interval': '1d',  'label': 'D1'},
        '1wk': {'period': '2y',   'interval': '1wk', 'label': 'W1'},
        '1mo': {'period': '10y',  'interval': '1mo', 'label': 'MN'},
    }
    config = tf_config.get(tf, tf_config['1d'])
    
    try:
        # Download data with timeframe-appropriate period and interval
        stock = yf.Ticker(ticker)
        df = stock.history(period=config['period'], interval=config['interval'])
        if df.empty:
            return f"<html><body><p style='color:red'>No data for {ticker} ({tf})</p></body></html>", 404
        
        # For H4, resample 1h to 4h candles
        if tf == '4h' and len(df) > 0:
            df = df.resample('4h').agg({
                'Open': 'first',
                'High': 'max',
                'Low': 'min',
                'Close': 'last',
                'Volume': 'sum'
            }).dropna()
        
        # Calculate required indicators
        df_plot = df.copy()
        df_plot['idx'] = np.arange(len(df_plot))
        
        # SL series — Donchian Channel (sama dengan logika EA)
        sl_series = calculate_sl(df_plot)
        
        # Bollinger Bands
        sma20 = df_plot['Close'].rolling(20).mean()
        std20 = df_plot['Close'].rolling(20).std()
        upper_bb = sma20 + 2 * std20
        middle_bb = sma20
        lower_bb = sma20 - 2 * std20
        
        # ADX calculation (simplified)
        high = df_plot['High']
        low = df_plot['Low']
        close = df_plot['Close']
        
        tr = pd.DataFrame({
            'hl': high - low,
            'hc': (high - close.shift()).abs(),
            'lc': (low - close.shift()).abs()
        }).max(axis=1)
        atr = tr.rolling(14).mean()
        
        up = high - high.shift()
        dn = low.shift() - low
        
        pos_dm = up.where((up > dn) & (up > 0), 0)
        neg_dm = dn.where((dn > up) & (dn > 0), 0)
        
        pdi = 100 * pos_dm.rolling(14).mean() / atr
        mdi = 100 * neg_dm.rolling(14).mean() / atr
        dx = 100 * (pdi - mdi).abs() / (pdi + mdi)
        adx = dx.rolling(14).mean()
        
        adx_series = adx.fillna(0)
        pdi_series = pdi.fillna(0)
        mdi_series = mdi.fillna(0)
        
        # Generate chart — returns (script='', html=standalone_page)
        _, chart_html = generate_chart(
            ticker, df_plot, sl_series,
            upper_bb, middle_bb, lower_bb,
            adx_series, pdi_series, mdi_series
        )
        
        return chart_html, 200, {'Content-Type': 'text/html; charset=utf-8'}
    except Exception as e:
        return f"<html><body><p style='color:red'>Error: {str(e)}</p></body></html>", 500

@app.route('/analyze', methods=['GET', 'POST', 'OPTIONS'])
def analyze_stock():
    """
    Endpoint utama untuk menerima request, mendownload data, 
    menghitung RSI, membuat grafik, dan mengirim kembali ke frontend.
    """
    # Handle OPTIONS request for CORS preflight
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        return response
    
    ticker = request.args.get('ticker') or request.form.get('ticker', '').strip().upper()
    force_refresh = request.args.get('force_refresh', request.form.get('force_refresh', 'false')).lower() == 'true'
    
    log_action('analyze', 'analyze_stock', params={'ticker': ticker, 'force_refresh': force_refresh})
    start_time = time.time()
    
    if not ticker:
        log_action('analyze', 'analyze_stock', params={'ticker': ticker}, status='error',
                  detail='Ticker kosong', duration_ms=(time.time() - start_time) * 1000)
        return jsonify({"status": "error", "message": "Ticker tidak boleh kosong."}), 400

    print(f"Memproses analisis untuk ticker: {ticker} (force_refresh={force_refresh})")

    # 1. Download Data
    data, metadata, error_msg = download_stock_data(ticker, period="400d", force_refresh=force_refresh)
    # TAMBAHKAN INI: Perbaikan MultiIndex yfinance
    if data is not None and isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    if error_msg:
        log_action('analyze', 'analyze_stock', params={'ticker': ticker}, status='error',
                  detail=error_msg, duration_ms=(time.time() - start_time) * 1000)
        return jsonify({"status": "error", "message": error_msg}), 500
    
    if data.empty:
        log_action('analyze', 'analyze_stock', params={'ticker': ticker}, status='error',
                  detail='Data kosong', duration_ms=(time.time() - start_time) * 1000)
        return jsonify({"status": "error", "message": "Data saham tidak ditemukan atau ada masalah."}), 500
    
    # Pastikan tipe data numerik untuk kolom harga
    numeric_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
    for col in numeric_cols:
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors='coerce')

    try:
        # 2. Proses Data & Hitung RSI
        
        # Pastikan kolom 'Close' ada
        if 'Close' not in data.columns:
            log_action('analyze', 'analyze_stock', params={'ticker': ticker}, status='error',
                      detail='Kolom Close tidak ditemukan', duration_ms=(time.time() - start_time) * 1000)
            return jsonify({"status": "error", "message": "Kolom Close tidak ditemukan di data."}), 500
            
        close_prices = data['Close']

        if close_prices.empty or len(close_prices) == 0:
            log_action('analyze', 'analyze_stock', params={'ticker': ticker}, status='error',
                      detail='Close prices kosong', duration_ms=(time.time() - start_time) * 1000)
            return jsonify({"status": "error", "message": "Data harga Close tidak ditemukan atau kosong."}), 500

        if len(close_prices) < 15:
            log_action('analyze', 'analyze_stock', params={'ticker': ticker}, status='error',
                      detail='Data tidak cukup untuk RSI', duration_ms=(time.time() - start_time) * 1000)
            return jsonify({"status": "error", "message": "Data tidak cukup untuk menghitung RSI (memerlukan minimal 15 titik data)."}), 500

        # Ambil nilai terakhir secara aman
        try:
            last_price = close_prices.iloc[-1]
        except IndexError:
            log_action('analyze', 'analyze_stock', params={'ticker': ticker}, status='error',
                      detail='Gagal ambil harga akhir', duration_ms=(time.time() - start_time) * 1000)
            return jsonify({"status": "error", "message": "Gagal mengambil harga akhir dari data."}), 500
            
        try:
            current_date = data.index[-1]
        except IndexError:
            log_action('analyze', 'analyze_stock', params={'ticker': ticker}, status='error',
                      detail='Gagal ambil tanggal akhir', duration_ms=(time.time() - start_time) * 1000)
            return jsonify({"status": "error", "message": "Gagal mengambil tanggal akhir dari data."}), 500

        # Hitung RSI
        rsi_series = calculate_rsi(close_prices, period=14)
        # Paksa menjadi 1D Series dan hapus nilai NaN agar tidak error saat plotting
        rsi_plot_data = rsi_series.squeeze()
        # *** PERBAIKAN UTAMA DI SINI ***
        # Memastikan last_rsi selalu menjadi skalar (float), bukan Series
        if rsi_series.empty:
            last_rsi = float('nan')
        else:
            # Ambil nilai terakhir sebagai skalar menggunakan .item() untuk memastikan scalar
            val = rsi_series.iloc[-1]
            # Konversi ke float untuk memastikan tipe data benar
            try:
                last_rsi = float(val)
                if np.isnan(last_rsi):
                    last_rsi = float('nan')
            except (TypeError, ValueError):
                last_rsi = float('nan')
        # --- Proses Data & Hitung SL ---
        # Gunakan fungsi baru
        sl_series = calculate_sl(data)
        last_sl = float(sl_series.iloc[-1])
        last_high = float(data['High'].iloc[-1])
        last_low = float(data['Low'].iloc[-1])
        last_price = float(data['Close'].iloc[-1])
        
        # Hitung Bollinger Bands & ADX untuk rekomendasi (samakan dengan BB Screener)
        upper_bb, middle_bb, lower_bb = calculate_bollinger_bands(data)
        adx_series, pdi_series, mdi_series = calculate_adx(data)
        
        last_basis = float(middle_bb.iloc[-1])
        last_adx = float(adx_series.iloc[-1])
        last_pdi = float(pdi_series.iloc[-1])
        last_mdi = float(mdi_series.iloc[-1])
        pdi_5ago = float(pdi_series.iloc[-6]) if len(pdi_series) >= 6 else 0
        adx_5ago = float(adx_series.iloc[-6]) if len(adx_series) >= 6 else 0
        
        pdi_rising = last_pdi > pdi_5ago
        pdi_above_mdi = last_pdi > last_mdi
        adx_strong = last_adx > 20
        adx_rising = last_adx > adx_5ago
        is_nan = np.isnan(last_adx) or np.isnan(last_pdi) or np.isnan(last_mdi)

        # --- Logika Rekomendasi (samakan dengan Basis ADX Screener) ---
        if last_low > last_sl and last_price > last_basis:
            if (not is_nan
                    and pdi_above_mdi and adx_strong and pdi_rising and adx_rising):
                recommendation = "BUY"
                color = "#4ade80"
                icon = "🟢"
            else:
                recommendation = "HOLD LONG"
                color = "#fbbf24"
                icon = "🟡"
        elif last_price > last_sl:
            recommendation = "HOLD LONG"
            color = "#fbbf24"
            icon = "🟡"
        else:
            recommendation = "SHORT SELL"
            color = "#f87171"
            icon = "🔴"


        # 3. Persiapan Data untuk Grafik
        # Cek kolom yang dibutuhkan untuk grafik
        required_cols = ['Open', 'High', 'Low', 'Close']
        missing_cols = [col for col in required_cols if col not in data.columns]
        if missing_cols:
            log_action('analyze', 'analyze_stock', params={'ticker': ticker}, status='error',
                      detail=f'Missing cols: {", ".join(missing_cols)}', duration_ms=(time.time() - start_time) * 1000)
            return jsonify({"status": "error", "message": f"Data tidak lengkap. Kolom yang hilang: {', '.join(missing_cols)}."}), 500
            
        df_plot = data.copy()
        
        # ADX sudah dihitung di atas untuk rekomendasi
        
        # ── Bokeh Interactive Chart ── (via iframe, not inline)
        chart_div = ''
        chart_script = ''
        
        # 5. Download Data Fundamental
        fundamental_data, fundamental_error = download_fundamental_data(ticker, force_refresh=force_refresh)
        if fundamental_error:
            print(f"Warning: {fundamental_error}")
            fundamental_data = {}
        
        # 6. Fetch Related News
        news_items, news_error = fetch_related_news(ticker)
        if news_error:
            print(f"Warning: Failed to fetch news: {news_error}")
            news_items = []
        
        # 7. Kembalikan Hasil ke Frontend
        # Format timestamp untuk display
        cache_timestamp = metadata.get('timestamp', datetime.now().isoformat()) if metadata else datetime.now().isoformat()
        
        # 8. Trend Analysis (ADX + SMA20 framework)
        trend_analysis = calculate_trend_analysis(data, adx_series, pdi_series, mdi_series, middle_bb)
        
        duration = (time.time() - start_time) * 1000
        log_action('analyze', 'analyze_stock', params={'ticker': ticker, 'force_refresh': force_refresh},
                  status='success', duration_ms=duration)
        # Tambahkan fungsi helper untuk sanitasi NaN dari JSON response
        def clean_nan(obj):
            import math
            if isinstance(obj, dict):
                return {k: clean_nan(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [clean_nan(x) for x in obj]
            elif isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
                return None
            return obj
        
        import math
        
        result = {
            "status": "success",
            "ticker": ticker,
            "rsi": None if last_rsi is None or (isinstance(last_rsi, float) and math.isnan(last_rsi)) else float(last_rsi),
            "recommendation": recommendation,
            "last_price": float(last_price) if not math.isnan(last_price) else None,
            "date": str(current_date),
            "chart_div": chart_div,
            "chart_script": chart_script,
            "last_sl": float(last_sl) if not math.isnan(last_sl) else None,
            "adx": float(adx_series.iloc[-1]) if not np.isnan(float(adx_series.iloc[-1])) else None,
            "pdi": float(pdi_series.iloc[-1]) if not np.isnan(float(pdi_series.iloc[-1])) else None,
            "mdi": float(mdi_series.iloc[-1]) if not np.isnan(float(mdi_series.iloc[-1])) else None,
            "cache_timestamp": cache_timestamp,
            "news": news_items,
            "fundamental": fundamental_data,
            "trend_analysis": trend_analysis
        }
        return jsonify(clean_nan(result))

    except Exception as e:
        # Pastikan error message ditampilkan dengan benar
        print(f"Error saat memproses data: {str(e)}")
        # Kadang error -1 muncul karena str(e) tidak menuliskan pesan, tapi kita coba ambil traceback
        import traceback
        print(traceback.format_exc())
        
        log_action('analyze', 'analyze_stock', params={'ticker': ticker}, status='error',
                  detail=str(e), duration_ms=(time.time() - start_time) * 1000)
        return jsonify({"status": "error", "message": f"Terjadi kesalahan internal: {str(e)}"}), 500

def fetch_related_news(ticker):
    """Fetch related news from Google News dengan multiple languages dan regions"""
    # Cache news per ticker selama 1 jam
    news_cache_file = os.path.join(CACHE_DIR, f"{ticker}_news.json")
    if os.path.exists(news_cache_file):
        try:
            with open(news_cache_file, 'r') as f:
                cached = json.load(f)
            cache_age = time.time() - cached.get('timestamp', 0)
            if cache_age < 3600:
                return cached.get('items', []), None
        except Exception:
            pass

    try:
        # Hapus .JK dari ticker jika ada (case-insensitive)
        clean_ticker = ticker.upper()
        if clean_ticker.endswith('.JK'):
            clean_ticker = clean_ticker[:-3]
        
        news_items = []
        seen_titles = set()  # Untuk menghindari duplikasi
        
        # Coba fetch dari multiple languages dan regions
        search_configs = [
            {'lang': 'id', 'country': 'ID'},  # Indonesia
            {'lang': 'en', 'country': 'US'},  # English - US
        ]
        
        for config in search_configs:
            try:
                gn = GoogleNews(lang=config['lang'], country=config['country'])
                # Gunakan method search() dengan parameter when='7d' untuk 7 hari terakhir
                result = gn.search(clean_ticker, when='7d')
                
                # Ambil entries dari hasil
                entries = result.get('entries', [])
                for article in entries:
                    # Hindari duplikasi berdasarkan title
                    title = article.get('title', '')
                    if title and title not in seen_titles:
                        news_item = {
                            'title': title,
                            'link': article.get('link', '')
                        }
                        news_items.append(news_item)
                        seen_titles.add(title)
                        
                        # Stop jika sudah cukup 10 berita
                        if len(news_items) >= 10:
                            break
                
                # Stop looping jika sudah punya 10 berita
                if len(news_items) >= 10:
                    break
                    
            except Exception as config_error:
                print(f"Error fetching news from {config['lang']}/{config['country']}: {str(config_error)}")
                continue
        
        # Ambil hanya 10 berita terbaru
        news_items = news_items[:10]
        
        try:
            with open(news_cache_file, 'w') as f:
                json.dump({'timestamp': time.time(), 'items': news_items}, f)
        except Exception:
            pass

        return news_items, None
    except Exception as e:
        return [], str(e)

@app.route('/screener/most-active', methods=['GET', 'POST', 'OPTIONS'])
def screener_most_active():
    """
    Endpoint untuk mendapatkan data screener most active stocks Indonesia
    """
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
        return response
    
    log_action('screener', 'most_active', params={'market': 'ID'})
    start_time = time.time()
    
    try:
        cached_data, metadata, error = load_cached_screener('most-active')
        if cached_data is not None:
            log_action('screener', 'most_active', params={'market': 'ID'}, status='success',
                      detail=f'cached: {len(cached_data)} results')
            return jsonify({
                "status": "success",
                "count": len(cached_data),
                "data": cached_data.to_dict('records'),
                "from_cache": True,
                "cache_timestamp": metadata['timestamp']
            })
        
        print("Mengambil data screener most active Indonesia...")
        
        s = Screener()
        data = s.get_screeners('most_actives_asia', count=250)
        quotes = data['most_actives_asia']['quotes']
        
        saham_indo = [q for q in quotes if q['symbol'].endswith('.JK')]
        
        results = []
        for q in saham_indo:
            symbol = q.get('symbol', '')
            shortname = q.get('shortName', q.get('symbol', ''))
            regular_market_time = q.get('regularMarketTime', 0)
            price = q.get('regularMarketPrice', 0)
            change_pct = q.get('regularMarketChangePercent', 0)
            
            if change_pct is None:
                change_pct = 0
            
            if regular_market_time:
                dt = datetime.fromtimestamp(regular_market_time)
                datetime_str = dt.strftime('%Y-%m-%d %H:%M:%S')
            else:
                datetime_str = ''
            
            results.append({
                'ticker': symbol,
                'name': shortname,
                'datetime': datetime_str,
                'price': price,
                'change_pct': change_pct
            })
        
        print(f"Ditemukan {len(results)} saham Indonesia dari screener")
        
        results_df = pd.DataFrame(results)
        save_screener_to_cache('most-active', results_df)
        
        duration = (time.time() - start_time) * 1000
        log_action('screener', 'most_active', params={'market': 'ID'}, status='success',
                  detail=f'{len(results)} results', duration_ms=duration)
        return jsonify({
            "status": "success",
            "count": len(results),
            "data": results
        })
        
    except Exception as e:
        duration = (time.time() - start_time) * 1000
        log_action('screener', 'most_active', params={'market': 'ID'}, status='error',
                  detail=str(e), duration_ms=duration)
        import traceback
        print(f"Error saat mengambil screener: {str(e)}")
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"Error screener: {str(e)}"}), 500

@app.route('/screener/day-gainers', methods=['GET', 'POST', 'OPTIONS'])
def screener_day_gainers():
    """
    Endpoint untuk mendapatkan data screener day gainers Indonesia
    """
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
        return response
    
    log_action('screener', 'day_gainers', params={'market': 'ID'})
    start_time = time.time()
    
    try:
        cached_data, metadata, error = load_cached_screener('day-gainers')
        if cached_data is not None:
            log_action('screener', 'day_gainers', params={'market': 'ID'}, status='success',
                      detail=f'cached: {len(cached_data)} results')
            return jsonify({
                "status": "success",
                "count": len(cached_data),
                "data": cached_data.to_dict('records'),
                "from_cache": True,
                "cache_timestamp": metadata['timestamp']
            })
        
        print("Mengambil data screener day gainers Indonesia...")
        
        s = Screener()
        data = s.get_screeners('day_gainers_asia', count=250)
        quotes = data['day_gainers_asia']['quotes']
        
        saham_indo = [q for q in quotes if q['symbol'].endswith('.JK')]
        
        results = []
        for q in saham_indo:
            symbol = q.get('symbol', '')
            shortname = q.get('shortName', q.get('symbol', ''))
            regular_market_time = q.get('regularMarketTime', 0)
            price = q.get('regularMarketPrice', 0)
            change_pct = q.get('regularMarketChangePercent', 0)
            
            if change_pct is None:
                change_pct = 0
            
            if regular_market_time:
                dt = datetime.fromtimestamp(regular_market_time)
                datetime_str = dt.strftime('%Y-%m-%d %H:%M:%S')
            else:
                datetime_str = ''
            
            results.append({
                'ticker': symbol,
                'name': shortname,
                'datetime': datetime_str,
                'price': price,
                'change_pct': change_pct
            })
        
        print(f"Ditemukan {len(results)} saham Indonesia dari screener day gainers")
        
        results_df = pd.DataFrame(results)
        save_screener_to_cache('day-gainers', results_df)
        
        return jsonify({
            "status": "success",
            "count": len(results),
            "data": results
        })
        
    except Exception as e:
        import traceback
        print(f"Error saat mengambil screener day gainers: {str(e)}")
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"Error screener: {str(e)}"}), 500

@app.route('/screener/net-net', methods=['GET', 'POST', 'OPTIONS'])
def screener_net_net():
    """
    Endpoint untuk mendapatkan data screener net net strategy Indonesia
    """
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
        return response
    
    log_action('screener', 'net_net', params={'market': 'ID'})
    start_time = time.time()
    
    try:
        cached_data, metadata, error = load_cached_screener('net-net')
        if cached_data is not None:
            log_action('screener', 'net_net', params={'market': 'ID'}, status='success',
                      detail=f'cached: {len(cached_data)} results')
            return jsonify({
                "status": "success",
                "count": len(cached_data),
                "data": cached_data.to_dict('records'),
                "from_cache": True,
                "cache_timestamp": metadata['timestamp']
            })
        
        print("Mengambil data screener net net strategy Indonesia...")
        
        s = Screener()
        data = s.get_screeners('net_net_strategy_asia', count=250)
        quotes = data['net_net_strategy_asia']['quotes']
        
        saham_indo = [q for q in quotes if q['symbol'].endswith('.JK')]
        
        results = []
        for q in saham_indo:
            symbol = q.get('symbol', '')
            shortname = q.get('shortName', q.get('symbol', ''))
            regular_market_time = q.get('regularMarketTime', 0)
            price = q.get('regularMarketPrice', 0)
            change_pct = q.get('regularMarketChangePercent', 0)
            
            if change_pct is None:
                change_pct = 0
            
            if regular_market_time:
                dt = datetime.fromtimestamp(regular_market_time)
                datetime_str = dt.strftime('%Y-%m-%d %H:%M:%S')
            else:
                datetime_str = ''
            
            results.append({
                'ticker': symbol,
                'name': shortname,
                'datetime': datetime_str,
                'price': price,
                'change_pct': change_pct
            })
        
        print(f"Ditemukan {len(results)} saham Indonesia dari screener net net")
        
        results_df = pd.DataFrame(results)
        save_screener_to_cache('net-net', results_df)
        
        return jsonify({
            "status": "success",
            "count": len(results),
            "data": results
        })
        
    except Exception as e:
        import traceback
        print(f"Error saat mengambil screener net net: {str(e)}")
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"Error screener: {str(e)}"}), 500

@app.route('/screener/acquirers-multiple', methods=['GET', 'POST', 'OPTIONS'])
def screener_acquirers_multiple():
    """
    Endpoint untuk mendapatkan data screener The Acquirers Multiple Indonesia
    """
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
        return response
    
    log_action('screener', 'acquirers_multiple', params={'market': 'ID'})
    start_time = time.time()
    
    try:
        cached_data, metadata, error = load_cached_screener('acquirers-multiple')
        if cached_data is not None:
            log_action('screener', 'acquirers_multiple', params={'market': 'ID'}, status='success',
                      detail=f'cached: {len(cached_data)} results')
            return jsonify({
                "status": "success",
                "count": len(cached_data),
                "data": cached_data.to_dict('records'),
                "from_cache": True,
                "cache_timestamp": metadata['timestamp']
            })
        
        print("Mengambil data screener The Acquirers Multiple Indonesia...")
        
        s = Screener()
        data = s.get_screeners('the_acquirers_multiple_asia', count=250)
        quotes = data['the_acquirers_multiple_asia']['quotes']
        
        saham_indo = [q for q in quotes if q['symbol'].endswith('.JK')]
        
        results = []
        for q in saham_indo:
            symbol = q.get('symbol', '')
            shortname = q.get('shortName', q.get('symbol', ''))
            regular_market_time = q.get('regularMarketTime', 0)
            price = q.get('regularMarketPrice', 0)
            change_pct = q.get('regularMarketChangePercent', 0)
            
            if change_pct is None:
                change_pct = 0
            
            if regular_market_time:
                dt = datetime.fromtimestamp(regular_market_time)
                datetime_str = dt.strftime('%Y-%m-%d %H:%M:%S')
            else:
                datetime_str = ''
            
            results.append({
                'ticker': symbol,
                'name': shortname,
                'datetime': datetime_str,
                'price': price,
                'change_pct': change_pct
            })
        
        print(f"Ditemukan {len(results)} saham Indonesia dari screener acquirers multiple")
        
        results_df = pd.DataFrame(results)
        save_screener_to_cache('acquirers-multiple', results_df)
        
        return jsonify({
            "status": "success",
            "count": len(results),
            "data": results
        })
        
    except Exception as e:
        import traceback
        print(f"Error saat mengambil screener acquirers multiple: {str(e)}")
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"Error screener: {str(e)}"}), 500

@app.route('/screener/us-most-active', methods=['GET', 'POST', 'OPTIONS'])
def screener_us_most_active():
    """
    Endpoint untuk mendapatkan data screener US most active stocks
    """
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
        return response
    
    log_action('screener', 'us_most_active', params={'market': 'US'})
    start_time = time.time()
    
    try:
        cached_data, metadata, error = load_cached_screener('us-most-active')
        if cached_data is not None:
            log_action('screener', 'us_most_active', params={'market': 'US'}, status='success',
                      detail=f'cached: {len(cached_data)} results')
            return jsonify({
                "status": "success",
                "count": len(cached_data),
                "data": cached_data.to_dict('records'),
                "from_cache": True,
                "cache_timestamp": metadata['timestamp']
            })
        
        print("Mengambil data screener US most active...")
        
        s = Screener()
        data = s.get_screeners('most_actives_americas', count=100)
        quotes = data['most_actives_americas']['quotes']
        
        results = []
        for q in quotes:
            symbol = q.get('symbol', '')
            shortname = q.get('shortName', q.get('symbol', ''))
            regular_market_time = q.get('regularMarketTime', 0)
            price = q.get('regularMarketPrice', 0)
            change_pct = q.get('regularMarketChangePercent', 0)
            
            if change_pct is None:
                change_pct = 0
            
            if regular_market_time:
                dt = datetime.fromtimestamp(regular_market_time)
                datetime_str = dt.strftime('%Y-%m-%d %H:%M:%S')
            else:
                datetime_str = ''
            
            results.append({
                'ticker': symbol,
                'name': shortname,
                'datetime': datetime_str,
                'price': price,
                'change_pct': change_pct
            })
        
        print(f"Ditemukan {len(results)} saham US dari screener")
        
        results_df = pd.DataFrame(results)
        save_screener_to_cache('us-most-active', results_df)
        
        return jsonify({
            "status": "success",
            "count": len(results),
            "data": results
        })
        
    except Exception as e:
        import traceback
        print(f"Error saat mengambil screener US: {str(e)}")
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"Error screener: {str(e)}"}), 500

@app.route('/screener/us-day-gainers', methods=['GET', 'POST', 'OPTIONS'])
def screener_us_day_gainers():
    """
    Endpoint untuk mendapatkan data screener US day gainers
    """
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
        return response
    
    log_action('screener', 'us_day_gainers', params={'market': 'US'})
    start_time = time.time()
    
    try:
        cached_data, metadata, error = load_cached_screener('us-day-gainers')
        if cached_data is not None:
            log_action('screener', 'us_day_gainers', params={'market': 'US'}, status='success',
                      detail=f'cached: {len(cached_data)} results')
            return jsonify({
                "status": "success",
                "count": len(cached_data),
                "data": cached_data.to_dict('records'),
                "from_cache": True,
                "cache_timestamp": metadata['timestamp']
            })
        
        print("Mengambil data screener US day gainers...")
        
        s = Screener()
        data = s.get_screeners('day_gainers_americas', count=100)
        quotes = data['day_gainers_americas']['quotes']
        
        results = []
        for q in quotes:
            symbol = q.get('symbol', '')
            shortname = q.get('shortName', q.get('symbol', ''))
            regular_market_time = q.get('regularMarketTime', 0)
            price = q.get('regularMarketPrice', 0)
            change_pct = q.get('regularMarketChangePercent', 0)
            
            if change_pct is None:
                change_pct = 0
            
            if regular_market_time:
                dt = datetime.fromtimestamp(regular_market_time)
                datetime_str = dt.strftime('%Y-%m-%d %H:%M:%S')
            else:
                datetime_str = ''
            
            results.append({
                'ticker': symbol,
                'name': shortname,
                'datetime': datetime_str,
                'price': price,
                'change_pct': change_pct
            })
        
        print(f"Ditemukan {len(results)} saham US day gainers")
        
        results_df = pd.DataFrame(results)
        save_screener_to_cache('us-day-gainers', results_df)
        
        return jsonify({
            "status": "success",
            "count": len(results),
            "data": results
        })
        
    except Exception as e:
        import traceback
        print(f"Error saat mengambil screener US day gainers: {str(e)}")
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"Error screener: {str(e)}"}), 500

@app.route('/screener/us-net-net', methods=['GET', 'POST', 'OPTIONS'])
def screener_us_net_net():
    """
    Endpoint untuk mendapatkan data screener US net net strategy
    """
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
        return response
    
    log_action('screener', 'us_net_net', params={'market': 'US'})
    start_time = time.time()
    
    try:
        cached_data, metadata, error = load_cached_screener('us-net-net')
        if cached_data is not None:
            log_action('screener', 'us_net_net', params={'market': 'US'}, status='success',
                      detail=f'cached: {len(cached_data)} results')
            return jsonify({
                "status": "success",
                "count": len(cached_data),
                "data": cached_data.to_dict('records'),
                "from_cache": True,
                "cache_timestamp": metadata['timestamp']
            })
        
        print("Mengambil data screener US net net strategy...")
        
        s = Screener()
        data = s.get_screeners('net_net_strategy', count=100)
        quotes = data['net_net_strategy']['quotes']
        
        results = []
        for q in quotes:
            symbol = q.get('symbol', '')
            shortname = q.get('shortName', q.get('symbol', ''))
            regular_market_time = q.get('regularMarketTime', 0)
            price = q.get('regularMarketPrice', 0)
            change_pct = q.get('regularMarketChangePercent', 0)
            
            if change_pct is None:
                change_pct = 0
            
            if regular_market_time:
                dt = datetime.fromtimestamp(regular_market_time)
                datetime_str = dt.strftime('%Y-%m-%d %H:%M:%S')
            else:
                datetime_str = ''
            
            results.append({
                'ticker': symbol,
                'name': shortname,
                'datetime': datetime_str,
                'price': price,
                'change_pct': change_pct
            })
        
        print(f"Ditemukan {len(results)} saham US net net strategy")
        
        results_df = pd.DataFrame(results)
        save_screener_to_cache('us-net-net', results_df)
        
        return jsonify({
            "status": "success",
            "count": len(results),
            "data": results
        })
        
    except Exception as e:
        import traceback
        print(f"Error saat mengambil screener US net net: {str(e)}")
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"Error screener: {str(e)}"}), 500

@app.route('/screener/us-acquirers-multiple', methods=['GET', 'POST', 'OPTIONS'])
def screener_us_acquirers_multiple():
    """
    Endpoint untuk mendapatkan data screener US The Acquirers Multiple
    """
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
        return response
    
    log_action('screener', 'us_acquirers_multiple', params={'market': 'US'})
    start_time = time.time()
    
    try:
        cached_data, metadata, error = load_cached_screener('us-acquirers-multiple')
        if cached_data is not None:
            log_action('screener', 'us_acquirers_multiple', params={'market': 'US'}, status='success',
                      detail=f'cached: {len(cached_data)} results')
            return jsonify({
                "status": "success",
                "count": len(cached_data),
                "data": cached_data.to_dict('records'),
                "from_cache": True,
                "cache_timestamp": metadata['timestamp']
            })
        
        print("Mengambil data screener US The Acquirers Multiple...")
        
        s = Screener()
        data = s.get_screeners('the_acquirers_multiple', count=100)
        quotes = data['the_acquirers_multiple']['quotes']
        
        results = []
        for q in quotes:
            symbol = q.get('symbol', '')
            shortname = q.get('shortName', q.get('symbol', ''))
            regular_market_time = q.get('regularMarketTime', 0)
            price = q.get('regularMarketPrice', 0)
            change_pct = q.get('regularMarketChangePercent', 0)
            
            if change_pct is None:
                change_pct = 0
            
            if regular_market_time:
                dt = datetime.fromtimestamp(regular_market_time)
                datetime_str = dt.strftime('%Y-%m-%d %H:%M:%S')
            else:
                datetime_str = ''
            
            results.append({
                'ticker': symbol,
                'name': shortname,
                'datetime': datetime_str,
                'price': price,
                'change_pct': change_pct
            })
        
        print(f"Ditemukan {len(results)} saham US The Acquirers Multiple")
        
        results_df = pd.DataFrame(results)
        save_screener_to_cache('us-acquirers-multiple', results_df)
        
        return jsonify({
            "status": "success",
            "count": len(results),
            "data": results
        })
        
    except Exception as e:
        import traceback
        print(f"Error saat mengambil screener US acquirers multiple: {str(e)}")
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"Error screener: {str(e)}"}), 500

def run_basis_adx_screener(list_path, list_type):
    """
    Helper function untuk menjalankan Basis ADX screener pada watchlist
    Logic: Low > Donchian SL, Close > Basis (SMA), ADX > 25, PDI > MDI, PDI rising
    """
    log_action('screener_basis_adx', 'run_basis_adx_screener', params={'type': list_type})
    screener_start = time.time()
    _client_ip = _get_client_ip()
    _basis = basis_adx_screener_progress_map[_client_ip]
    # global basis_adx_screener_progress  (removed: IP-keyed access)
    
    try:
        tickers_df = pd.read_csv(list_path)
        if 'Symbol' not in tickers_df.columns:
            _basis['status'] = 'error'
            _basis['message'] = "Kolom 'Symbol' tidak ditemukan"
            return
        
        tickers = tickers_df['Symbol'].tolist()
        
        _basis['is_running'] = True
        _basis['total'] = len(tickers)
        _basis['progress'] = 0
        _basis['results'] = []
        _basis['status'] = 'running'
        _basis['message'] = f'Starting Basis ADX Screener for {list_type} ({len(tickers)} tickers)...'
        
        for i, ticker in enumerate(tickers):
            ticker = ticker.strip().upper()
            _basis['current_ticker'] = ticker
            _basis['progress'] = i + 1
            _basis['message'] = f'Analyzing {ticker}...'
            
            try:
                data, _, error_msg = download_stock_data(ticker, period="400d", force_refresh=False)
                
                if error_msg or data is None or (hasattr(data, 'empty') and data.empty):
                    _basis['message'] = f'{ticker}: No data'
                    continue
                
                if isinstance(data.columns, pd.MultiIndex):
                    data.columns = data.columns.get_level_values(0)
                
                numeric_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
                for col in numeric_cols:
                    if col in data.columns:
                        data[col] = pd.to_numeric(data[col], errors='coerce')
                
                before = len(data)
                data = data.dropna(subset=['Close'])
                dropped = before - len(data)
                if dropped > 0:
                    print(f"Basis ADX Screener - {ticker}: dropped {dropped} incomplete row(s)")
                
                if len(data) < 220:
                    _basis['message'] = f'{ticker}: Insufficient data'
                    continue
                
                sl_series = calculate_sl(data)
                upper_bb, middle_bb, lower_bb = calculate_bollinger_bands(data)
                adx_series, pdi_series, mdi_series = calculate_adx(data)
                
                last_price = float(data['Close'].iloc[-1])
                last_low = float(data['Low'].iloc[-1])
                last_sl = float(sl_series.iloc[-1])
                last_basis = float(middle_bb.iloc[-1])
                last_volume = float(data['Volume'].iloc[-1]) if 'Volume' in data.columns else 0
                
                if np.isnan(last_sl) or np.isnan(last_basis):
                    _basis['message'] = f'{ticker}: Invalid SL or Basis data'
                    continue
                
                yesterday_close = float(data['Close'].iloc[-2]) if len(data) >= 2 else last_price
                change_pct = ((last_price - yesterday_close) / yesterday_close * 100) if yesterday_close != 0 else 0
                
                value_in_millions = (last_price * last_volume) / 1_000_000
                
                last_date = data.index[-1].strftime('%Y-%m-%d')
                
                last_adx = float(adx_series.iloc[-1])
                last_pdi = float(pdi_series.iloc[-1])
                last_mdi = float(mdi_series.iloc[-1])
                pdi_5ago = float(pdi_series.iloc[-6]) if len(pdi_series) >= 6 else 0
                adx_5ago = float(adx_series.iloc[-6]) if len(adx_series) >= 6 else 0
                
                pdi_rising = last_pdi > pdi_5ago
                pdi_above_mdi = last_pdi > last_mdi
                adx_strong = last_adx > 20
                adx_rising = last_adx > adx_5ago
                is_nan = np.isnan(last_adx) or np.isnan(last_pdi) or np.isnan(last_mdi)
                
                if last_low > last_sl and last_price > last_basis:
                    if (not is_nan
                            and pdi_above_mdi and adx_strong and pdi_rising and adx_rising):
                        recommendation = "BUY"
                    else:
                        recommendation = "HOLD LONG"
                elif last_price > last_sl:
                    recommendation = "HOLD LONG"
                else:
                    recommendation = "SHORT SELL"
                
                # Calculate ADX+SMA% for trend strength
                adx_sma_pct, trend_commentary = calculate_adx_sma_pct(data, adx_series, pdi_series, mdi_series, middle_bb)
                
                result_item = {
                    'ticker': ticker,
                    'last_date': last_date,
                    'price': round(last_price, 2),
                    'basis': round(last_basis, 2),
                    'change_pct': round(change_pct, 2),
                    'volume': float(last_volume),
                    'value': round(value_in_millions, 2),
                    'recommendation': recommendation,
                    'adx': round(float(adx_series.iloc[-1]), 2) if not np.isnan(float(adx_series.iloc[-1])) else None,
                    'pdi': round(float(pdi_series.iloc[-1]), 2) if not np.isnan(float(pdi_series.iloc[-1])) else None,
                    'mdi': round(float(mdi_series.iloc[-1]), 2) if not np.isnan(float(mdi_series.iloc[-1])) else None,
                    'adx_sma_pct': adx_sma_pct,
                    'trend_commentary': trend_commentary
                }
                
                _basis['results'].append(result_item)
                _basis['message'] = f'{ticker}: {recommendation}'
                
            except Exception as e:
                print(f"Error analyzing {ticker}: {e}")
                _basis['message'] = f'{ticker}: Error'
                continue
            
            time.sleep(0.5)
        
        _basis['status'] = 'completed'
        _basis['results'] = sorted(_basis['results'],
            key=lambda x: (
                {'BUY': 3, 'HOLD LONG': 2, 'SHORT SELL': 1}.get(x.get('recommendation', ''), 0),
                x.get('adx_sma_pct', 0) or 0,
                x.get('value', 0) or 0
            ), reverse=True)
        _basis['message'] = f'Basis ADX Screener completed: {len(_basis["results"])} stocks analyzed'
        _basis['is_running'] = False
        log_action('screener_basis_adx', 'run_basis_adx_screener', params={'type': list_type}, status='success',
                  detail=f'{len(_basis["results"])} stocks analyzed')
        
    except Exception as e:
        _basis['status'] = 'error'
        _basis['message'] = str(e)
        _basis['is_running'] = False
        log_action('screener_basis_adx', 'run_basis_adx_screener', params={'type': list_type}, status='error',
                  detail=str(e))


def run_fundamental_screener(list_path, list_type):
    """
    Helper function untuk menjalankan fundamental screener pada watchlist
    """
    log_action('screener_fundamental', 'run_fundamental_screener', params={'type': list_type})
    _client_ip = _get_client_ip()
    _fund = fundamental_screener_progress_map[_client_ip]
    # global fundamental_screener_progress  (removed: IP-keyed access)
    
    try:
        tickers_df = pd.read_csv(list_path)
        if 'Symbol' not in tickers_df.columns:
            _fund['status'] = 'error'
            _fund['message'] = "Kolom 'Symbol' tidak ditemukan"
            return
        
        tickers = tickers_df['Symbol'].tolist()
        
        _fund['is_running'] = True
        _fund['total'] = len(tickers)
        _fund['progress'] = 0
        _fund['results'] = []
        _fund['status'] = 'running'
        _fund['message'] = f'Starting Fundamental Screener for {list_type} ({len(tickers)} tickers)...'
        
        for i, ticker in enumerate(tickers):
            ticker = ticker.strip().upper()
            _fund['current_ticker'] = ticker
            _fund['progress'] = i + 1
            _fund['message'] = f'Analyzing {ticker}...'
            
            try:
                # Ambil data fundamental (pake cache 24 jam, jangan paksa refresh tiap kali)
                fundamental_data, err = download_fundamental_data(ticker, force_refresh=False)
                
                # Cek harga terakhir -- baca langsung dari cache CSV, jangan overwrite
                current_price = None
                try:
                    cache_file = get_cache_file_path(ticker)
                    if os.path.exists(cache_file):
                        with open(cache_file, 'r') as f:
                            lines = f.readlines()
                        if len(lines) >= 2:
                            csv_content = ''.join(lines[1:])
                            df_cache = pd.read_csv(io.StringIO(csv_content))
                            if 'Close' in df_cache.columns and not df_cache.empty:
                                current_price = float(pd.to_numeric(df_cache['Close'].iloc[-1], errors='coerce'))
                except Exception as pe:
                    print(f"Error reading cached price for {ticker}: {pe}")
                
                if current_price is None or current_price == 0:
                    try:
                        stock_yf = yf.Ticker(ticker)
                        info = stock_yf.info
                        current_price = info.get('currentPrice') or info.get('regularMarketPrice') or info.get('previousClose')
                    except:
                        pass
                
                if err or fundamental_data is None:
                    print(f"Fundamental Screener - {ticker}: Missing fundamentals (err={err})")
                    _fund['message'] = f'{ticker}: No data'
                    continue
                
                op_margin = clean_float(fundamental_data.get('operating_margin'))
                fcf = clean_float(fundamental_data.get('free_cash_flow'))
                ocf = clean_float(fundamental_data.get('operating_cash_flow'))
                debt_to_equity = clean_float(fundamental_data.get('long_term_debt_to_equity'))
                fair_price_pe = clean_float(fundamental_data.get('fair_price_pe'))
                fair_price_dcf = clean_float(fundamental_data.get('fair_price_dcf'))
                
                current_price_clean = clean_float(current_price)
                if current_price_clean is None:
                    print(f"Fundamental Screener - {ticker}: Missing price")
                    _fund['message'] = f'{ticker}: No price'
                    continue
                
                # 1. operating margin > 0
                c1 = op_margin is not None and op_margin > 0
                
                # 2. free cash flow > 0
                c2 = fcf is not None and fcf > 0
                
                # 3. operating cash flow > 0
                c3 = ocf is not None and ocf > 0
                
                # 4. debt to equity ratio < 2 (dalam desimal, misal 0.8 = 80%)
                c4 = False
                debt_to_equity_ratio = None
                if debt_to_equity is not None:
                    debt_to_equity_ratio = debt_to_equity
                    c4 = debt_to_equity_ratio < 2.0
                
                # 5. PE Fair Value > current price
                c5 = fair_price_pe is not None and fair_price_pe > current_price_clean
                
                # 6. DCF Fair Value > current price
                c6 = fair_price_dcf is not None and fair_price_dcf > current_price_clean
                
                meet_criteria = c1 and c2 and c3 and c4 and c5 and c6
                conclusion = "Meet Criterias" if meet_criteria else "Does not meet Criterias"
                
                result_item = {
                    'ticker': ticker,
                    'price': round(current_price_clean, 2),
                    'operating_margin': round(op_margin, 4) if op_margin is not None else None,
                    'free_cash_flow': float(fcf) if fcf is not None else None,
                    'operating_cash_flow': float(ocf) if ocf is not None else None,
                    'debt_to_equity_ratio': round(debt_to_equity_ratio, 4) if debt_to_equity_ratio is not None else None,
                    'fair_price_pe': round(fair_price_pe, 2) if fair_price_pe is not None else None,
                    'fair_price_dcf': round(fair_price_dcf, 2) if fair_price_dcf is not None else None,
                    'c1': bool(c1),
                    'c2': bool(c2),
                    'c3': bool(c3),
                    'c4': bool(c4),
                    'c5': bool(c5),
                    'c6': bool(c6),
                    'conclusion': conclusion
                }
                
                _fund['results'].append(result_item)
                _fund['message'] = f'{ticker}: {conclusion}'
                
            except Exception as e:
                print(f"Error analyzing fundamentals for {ticker}: {e}")
                _fund['message'] = f'{ticker}: Error'
                continue
            # Delay antar ticker biar gak kena rate limit Yahoo Finance
            # Random ~1.5-2.5 detik biar natural
            sleep_time = 1.5 + (hash(ticker) % 10) / 10.0
            time.sleep(sleep_time)
            
        _fund['status'] = 'completed'
        _fund['message'] = f'Fundamental Screener completed: {len(_fund["results"])} stocks analyzed'
        _fund['is_running'] = False
        log_action('screener_fundamental', 'run_fundamental_screener', params={'type': list_type}, status='success',
                  detail=f'{len(_fund["results"])} stocks analyzed')
                  
    except Exception as e:
        _fund['status'] = 'error'
        _fund['message'] = str(e)
        _fund['is_running'] = False
        log_action('screener_fundamental', 'run_fundamental_screener', params={'type': list_type}, status='error',
                  detail=str(e))


@app.route('/screener/us-basis-adx', methods=['GET', 'POST', 'OPTIONS'])
def screener_us_basis_adx():
    """Endpoint untuk mendapatkan data screener US Basis ADX"""
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
        return response
    
    log_action('screener_basis_adx', 'us_basis_adx', params={'market': 'US'})
    start_time = time.time()
    
    _client_ip = _get_client_ip()
    _basis = basis_adx_screener_progress_map[_client_ip]
    # global basis_adx_screener_progress  (removed: IP-keyed access)
    
    if _basis['is_running']:
        log_action('screener_basis_adx', 'us_basis_adx', params={'market': 'US'}, status='error',
                  detail='Already running', duration_ms=(time.time() - start_time) * 1000)
        return jsonify({"status": "error", "message": "Basis ADX Screener sedang berjalan"}), 409
    
    _basis['status'] = 'starting'
    _basis['current_ticker'] = ''
    _basis['progress'] = 0
    _basis['total'] = 0
    _basis['results'] = []
    _basis['message'] = 'Initializing...'
    _basis['is_running'] = False
    _basis["run_id"] += 1  # Track new run
    
    # Langsung load cache — gak perlu extraction marker
    cached_data, metadata, error = load_cached_screener('us-basis-adx')
    if cached_data is not None:
        log_action('screener_basis_adx', 'us_basis_adx', params={'market': 'US'}, status='success',
                  detail=f'cached: {len(cached_data)} results')
        _basis['results'] = cached_data.to_dict('records')
        _basis['status'] = 'completed'
        _basis['progress'] = len(cached_data)
        clean_records = []
        for item in cached_data.to_dict('records'):
            cleaned = {}
            for k, v in item.items():
                if isinstance(v, float) and (v != v or v == float('inf') or v == float('-inf')):
                    cleaned[k] = None
                else:
                    cleaned[k] = v
            clean_records.append(cleaned)
        return jsonify({"status": "success", "message": "Data dari cache", "count": len(cached_data), "data": clean_records, "from_cache": True, "cache_timestamp": metadata['timestamp']})
    
    uslist_path = os.path.join(os.path.dirname(__file__), 'uslist.csv')
    if not os.path.exists(uslist_path):
        log_action('screener_basis_adx', 'us_basis_adx', params={'market': 'US'}, status='error',
                  detail='uslist.csv not found', duration_ms=(time.time() - start_time) * 1000)
        return jsonify({"status": "error", "message": "File uslist.csv tidak ditemukan"}), 404
    
    try:
        _basis['is_running'] = True
        run_basis_adx_screener(uslist_path, 'US')
        if _basis['results']:
            results_df = pd.DataFrame(_basis['results'])
            save_screener_to_cache('us-basis-adx', results_df)
        touch_screener_marker('us-basis-adx')
        duration = (time.time() - start_time) * 1000
        log_action('screener_basis_adx', 'us_basis_adx', params={'market': 'US'}, status='success',
                  detail=f'{len(_basis["results"])} results', duration_ms=duration)
        return jsonify({"status": "success", "message": _basis['message'],
            "count": len(_basis['results']), "data": _basis['results']})
    except Exception as e:
        duration = (time.time() - start_time) * 1000
        log_action('screener_basis_adx', 'us_basis_adx', params={'market': 'US'}, status='error', detail=str(e), duration_ms=duration)
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/screener/id-basis-adx', methods=['GET', 'POST', 'OPTIONS'])
def screener_id_basis_adx():
    """Endpoint untuk mendapatkan data screener ID Basis ADX"""
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
        return response
    
    log_action('screener_basis_adx', 'id_basis_adx', params={'market': 'ID'})
    start_time = time.time()
    
    _client_ip = _get_client_ip()
    _basis = basis_adx_screener_progress_map[_client_ip]
    # global basis_adx_screener_progress  (removed: IP-keyed access)
    
    if _basis['is_running']:
        log_action('screener_basis_adx', 'id_basis_adx', params={'market': 'ID'}, status='error',
                  detail='Already running', duration_ms=(time.time() - start_time) * 1000)
        return jsonify({"status": "error", "message": "Basis ADX Screener sedang berjalan"}), 409
    
    _basis['status'] = 'starting'
    _basis['current_ticker'] = ''
    _basis['progress'] = 0
    _basis['total'] = 0
    _basis['results'] = []
    _basis['message'] = 'Initializing...'
    _basis['is_running'] = False
    _basis["run_id"] += 1  # Track new run
    
    # Langsung load cache — gak perlu extraction marker
    cached_data, metadata, error = load_cached_screener('id-basis-adx')
    if cached_data is not None:
        log_action('screener_basis_adx', 'id_basis_adx', params={'market': 'ID'}, status='success',
                  detail=f'cached: {len(cached_data)} results')
        _basis['results'] = cached_data.to_dict('records')
        _basis['status'] = 'completed'
        _basis['progress'] = len(cached_data)
        clean_records = []
        for item in cached_data.to_dict('records'):
            cleaned = {}
            for k, v in item.items():
                if isinstance(v, float) and (v != v or v == float('inf') or v == float('-inf')):
                    cleaned[k] = None
                else:
                    cleaned[k] = v
            clean_records.append(cleaned)
        return jsonify({"status": "success", "message": "Data dari cache", "count": len(cached_data), "data": clean_records, "from_cache": True, "cache_timestamp": metadata['timestamp']})
    
    idlist_path = os.path.join(os.path.dirname(__file__), 'idlist.csv')
    if not os.path.exists(idlist_path):
        log_action('screener_basis_adx', 'id_basis_adx', params={'market': 'ID'}, status='error',
                  detail='idlist.csv not found', duration_ms=(time.time() - start_time) * 1000)
        return jsonify({"status": "error", "message": "File idlist.csv tidak ditemukan"}), 404
    
    try:
        _basis['is_running'] = True
        run_basis_adx_screener(idlist_path, 'ID')
        if _basis['results']:
            results_df = pd.DataFrame(_basis['results'])
            save_screener_to_cache('id-basis-adx', results_df)
        touch_screener_marker('id-basis-adx')
        duration = (time.time() - start_time) * 1000
        log_action('screener_basis_adx', 'id_basis_adx', params={'market': 'ID'}, status='success',
                  detail=f'{len(_basis["results"])} results', duration_ms=duration)
        return jsonify({"status": "success", "message": _basis['message'],
            "count": len(_basis['results']), "data": _basis['results']})
    except Exception as e:
        duration = (time.time() - start_time) * 1000
        log_action('screener_basis_adx', 'id_basis_adx', params={'market': 'ID'}, status='error', detail=str(e), duration_ms=duration)
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/screener/basis-adx-progress', methods=['GET', 'OPTIONS'])
def screener_basis_adx_progress():
    """SSE endpoint untuk real-time progress Basis ADX screener"""
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'GET,OPTIONS')
        return response
    
    _client_ip = _get_client_ip()
    
    def _find_active_basis():
        for ip, p in basis_adx_screener_progress_map.items():
            if p['is_running']:
                return ip, p
        for ip, p in basis_adx_screener_progress_map.items():
            if p['status'] == 'completed' and p['results']:
                return ip, p
        return _client_ip, basis_adx_screener_progress_map[_client_ip]
    
    def generate():
        last_progress = None
        idle_loops = 0
        max_idle_loops = 30
        completed_wait_loops = 0
        active_ip, _basis = _find_active_basis()
        _connected_run_id = _basis["run_id"]
        # global basis_adx_screener_progress  (removed: IP-keyed access)
        while True:
            # Re-check active user
            new_ip, new_basis = _find_active_basis()
            if new_ip != active_ip:
                active_ip = new_ip
                _basis = new_basis
                _connected_run_id = _basis["run_id"]
                last_progress = None
            current_progress = {
                'status': _basis['status'],
                'current_ticker': _basis['current_ticker'],
                'progress': _basis['progress'],
                'total': _basis['total'],
                'results_count': len(_basis['results']),
                'message': _basis['message'],
                'run_id': _basis['run_id'],
            }
            if current_progress['status'] == 'completed' and current_progress['results_count'] > 0:
                completed_wait_loops += 1
                # Tunggu max ~1.5s untuk potential new run, lalu emit completed
                if _connected_run_id == current_progress.get('run_id', 0) and completed_wait_loops <= 3:
                    time.sleep(0.5)
                    continue
                if current_progress != last_progress:
                    yield "data: " + json.dumps(current_progress) + "\n\n"
                break
            if current_progress['status'] == 'starting' and current_progress['results_count'] == 0:
                if current_progress != last_progress:
                    last_progress = current_progress.copy()
                    yield "data: " + json.dumps(current_progress) + "\n\n"
                time.sleep(1)
                continue
            if current_progress['status'] == 'idle':
                idle_loops += 1
                if idle_loops >= max_idle_loops:
                    break
                last_progress = current_progress.copy()
                time.sleep(1)
                continue
            if current_progress != last_progress:
                last_progress = current_progress.copy()
                yield "data: " + json.dumps(current_progress) + "\n\n"
            if current_progress['status'] in ['completed', 'error']:
                break
            time.sleep(1)
    
    from flask import Response
    return Response(generate(), mimetype='text/event-stream')


@app.route('/screener/us-fundamental', methods=['GET', 'POST', 'OPTIONS'])
def screener_us_fundamental():
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
        return response
    
    log_action('screener_fundamental', 'us_fundamental', params={'market': 'US'})
    start_time = time.time()
    
    _client_ip = _get_client_ip()
    _fund = fundamental_screener_progress_map[_client_ip]
    # global fundamental_screener_progress  (removed: IP-keyed access)
    
    use_cache, run_timestamp = check_fundamental_run_status('US')
    if use_cache:
        cached_data, metadata, error = load_cached_fundamental_screener('us-fundamental')
        if cached_data is not None:
            records = clean_nan_in_records(cached_data.to_dict('records'))
            log_action('screener_fundamental', 'us_fundamental', params={'market': 'US'}, status='success',
                      detail=f'cached: {len(cached_data)} results')
            return jsonify({
                "status": "success",
                "message": "Data dari cache",
                "count": len(cached_data),
                "data": records,
                "from_cache": True,
                "cache_timestamp": run_timestamp
            })
    
    uslist_path = os.path.join(os.path.dirname(__file__), 'uslist.csv')
    
    if _fund['is_running']:
        log_action('screener_fundamental', 'us_fundamental', params={'market': 'US'}, status='error',
                  detail='Already running', duration_ms=(time.time() - start_time) * 1000)
        return jsonify({"status": "error", "message": "Fundamental Screener sedang berjalan"}), 409
    
    if not os.path.exists(uslist_path):
        log_action('screener_fundamental', 'us_fundamental', params={'market': 'US'}, status='error',
                  detail='uslist.csv not found', duration_ms=(time.time() - start_time) * 1000)
        return jsonify({"status": "error", "message": "File uslist.csv tidak ditemukan"}), 404
    
    try:
        run_fundamental_screener(uslist_path, 'US')
        
        if _fund['results']:
            results_df = pd.DataFrame(_fund['results'])
            save_screener_to_cache('us-fundamental', results_df)
            
            run_file = os.path.join(CACHE_DIR, '.fundamental_us_run.txt')
            with open(run_file, 'w') as f:
                f.write(datetime.now().isoformat())
        
        duration = (time.time() - start_time) * 1000
        log_action('screener_fundamental', 'us_fundamental', params={'market': 'US'}, status='success',
                  detail=f'{len(_fund["results"])} results', duration_ms=duration)
        records = clean_nan_in_records(_fund['results'])
        response = jsonify({
            "status": "success",
            "message": _fund['message'],
            "count": len(_fund['results']),
            "data": records
        })
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
        
    except Exception as e:
        duration = (time.time() - start_time) * 1000
        log_action('screener_fundamental', 'us_fundamental', params={'market': 'US'}, status='error',
                  detail=str(e), duration_ms=duration)
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/screener/id-fundamental', methods=['GET', 'POST', 'OPTIONS'])
def screener_id_fundamental():
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
        return response
    
    log_action('screener_fundamental', 'id_fundamental', params={'market': 'ID'})
    start_time = time.time()
    
    _client_ip = _get_client_ip()
    _fund = fundamental_screener_progress_map[_client_ip]
    # global fundamental_screener_progress  (removed: IP-keyed access)
    
    use_cache, run_timestamp = check_fundamental_run_status('ID')
    if use_cache:
        cached_data, metadata, error = load_cached_fundamental_screener('id-fundamental')
        if cached_data is not None:
            records = clean_nan_in_records(cached_data.to_dict('records'))
            log_action('screener_fundamental', 'id_fundamental', params={'market': 'ID'}, status='success',
                      detail=f'cached: {len(cached_data)} results')
            return jsonify({
                "status": "success",
                "message": "Data dari cache",
                "count": len(cached_data),
                "data": records,
                "from_cache": True,
                "cache_timestamp": run_timestamp
            })
    
    idlist_path = os.path.join(os.path.dirname(__file__), 'idlist.csv')
    
    if _fund['is_running']:
        log_action('screener_fundamental', 'id_fundamental', params={'market': 'ID'}, status='error',
                  detail='Already running', duration_ms=(time.time() - start_time) * 1000)
        return jsonify({"status": "error", "message": "Fundamental Screener sedang berjalan"}), 409
    
    if not os.path.exists(idlist_path):
        log_action('screener_fundamental', 'id_fundamental', params={'market': 'ID'}, status='error',
                  detail='idlist.csv not found', duration_ms=(time.time() - start_time) * 1000)
        return jsonify({"status": "error", "message": "File idlist.csv tidak ditemukan"}), 404
    
    try:
        run_fundamental_screener(idlist_path, 'ID')
        
        if _fund['results']:
            results_df = pd.DataFrame(_fund['results'])
            save_screener_to_cache('id-fundamental', results_df)
            
            run_file = os.path.join(CACHE_DIR, '.fundamental_id_run.txt')
            with open(run_file, 'w') as f:
                f.write(datetime.now().isoformat())
        
        duration = (time.time() - start_time) * 1000
        log_action('screener_fundamental', 'id_fundamental', params={'market': 'ID'}, status='success',
                  detail=f'{len(_fund["results"])} results', duration_ms=duration)
        records = clean_nan_in_records(_fund['results'])
        response = jsonify({
            "status": "success",
            "message": _fund['message'],
            "count": len(_fund['results']),
            "data": records
        })
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
        
    except Exception as e:
        duration = (time.time() - start_time) * 1000
        log_action('screener_fundamental', 'id_fundamental', params={'market': 'ID'}, status='error',
                  detail=str(e), duration_ms=duration)
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/screener/fundamental-progress', methods=['GET', 'OPTIONS'])
def screener_fundamental_progress():
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'GET,OPTIONS')
        return response
    
    _client_ip = _get_client_ip()
    
    def _find_active_fund():
        for ip, p in fundamental_screener_progress_map.items():
            if p['is_running']:
                return ip, p
        for ip, p in fundamental_screener_progress_map.items():
            if p['status'] == 'completed' and p['results']:
                return ip, p
        return _client_ip, fundamental_screener_progress_map[_client_ip]
    
    def generate():
        last_progress = None
        idle_loops = 0
        active_ip, _fund = _find_active_fund()
        _connected_run_id = _fund["run_id"]
        # global fundamental_screener_progress  (removed: IP-keyed access)
        while True:
            # Re-check active user
            new_ip, new_fund = _find_active_fund()
            if new_ip != active_ip:
                active_ip = new_ip
                _fund = new_fund
                _connected_run_id = _fund["run_id"]
                last_progress = None
            
            current_progress = {
                'status': _fund['status'],
                'current_ticker': _fund['current_ticker'],
                'progress': _fund['progress'],
                'total': _fund['total'],
                'results_count': len(_fund['results']),
                'message': _fund['message'],
                'run_id': _fund['run_id'],
            }
            
            if current_progress != last_progress:
                last_progress = current_progress.copy()
                
                yield f"data: {json.dumps(current_progress)}\n\n"
            
            if _fund['status'] in ['completed', 'error']:
                break
            
            # Safety: kalo idle > 30 detik, tutup SSE
            if _fund['status'] == 'idle':
                idle_loops += 1
                if idle_loops > 30:
                    yield 'data: {"status": "timeout", "message": "No active screener"}' + chr(92)*2 + 'n' + chr(92)*2 + 'n'
                    break
            else:
                idle_loops = 0
            
            time.sleep(1)
    
    from flask import Response
    return Response(generate(), mimetype='text/event-stream')


@app.route('/logs', methods=['GET'])
def view_logs():
    """Halaman untuk melihat log activity dengan filter tanggal dan limit."""
    date_str = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    limit = request.args.get('limit', '20')

    try:
        limit = int(limit)
        if limit < 1:
            limit = 20
        if limit > 500:
            limit = 500
    except ValueError:
        limit = 20

    try:
        entries = read_recent_logs(limit=limit, date=date_str)
        success_count = sum(1 for e in entries if e.get('status') == 'success')
        error_count = sum(1 for e in entries if e.get('status') == 'error')
        return render_template('logs.html', entries=entries, date=date_str,
                              limit=limit, success_count=success_count,
                              error_count=error_count, error=None)
    except Exception as e:
        return render_template('logs.html', entries=[], date=date_str,
                              limit=limit, success_count=0, error_count=0,
                              error=str(e))


if __name__ == '__main__':
    # Debug=True penting untuk melihat log di terminal
    # threaded=True memastikan request datang bersamaan tidak menumpuk
    app.run(debug=True, threaded=True, use_reloader=False)


def calculate_trend_analysis(data, adx_series, pdi_series, mdi_series, middle_bb):
    """
    Trend Analysis menggunakan framework ADX(14) + SMA20.
    Menghitung persentase bar bullish (ADX>25 + Close>SMA20) dan bearish (ADX>25 + Close<SMA20).
    
    Threshold:
      - Strong Bullish: >35% bar ADX>25 dan Close>SMA20
      - Weak Bullish: 30-35%
      - Sideway: <30%
      - Weak Bearish: 30-35% ADX>25 dan Close<SMA20
      - Strong Bearish: >35%
    
    Returns dict dengan trend stats lengkap.
    """
    n = len(data)
    start_idx = 20
    sma20 = middle_bb
    
    valid_bars = 0
    bull_bars = 0
    bear_bars = 0
    sideway_bars = 0
    
    adx_brackets = {
        '0_20': {'count': 0, 'above_sma': 0, 'label': 'ADX 0-20 (No trend)'},
        '20_25': {'count': 0, 'above_sma': 0, 'label': 'ADX 20-25 (Weak trend)'},
        '25_40': {'count': 0, 'above_sma': 0, 'label': 'ADX 25-40 (Strong trend)'},
        '40_999': {'count': 0, 'above_sma': 0, 'label': 'ADX 40+ (Very strong)'},
    }
    
    for i in range(start_idx, n):
        if np.isnan(adx_series.iloc[i]) or np.isnan(sma20.iloc[i]):
            continue
        valid_bars += 1
        close = float(data['Close'].iloc[i])
        sma = float(sma20.iloc[i])
        adx_val = float(adx_series.iloc[i])
        
        if adx_val > 25:
            if close > sma:
                bull_bars += 1
            else:
                bear_bars += 1
        else:
            sideway_bars += 1
        
        if adx_val <= 20:
            bracket = '0_20'
        elif adx_val <= 25:
            bracket = '20_25'
        elif adx_val <= 40:
            bracket = '25_40'
        else:
            bracket = '40_999'
        adx_brackets[bracket]['count'] += 1
        if close > sma:
            adx_brackets[bracket]['above_sma'] += 1
    
    if valid_bars == 0:
        return {'valid_bars': 0, 'error': 'No valid data'}
    
    bull_pct = (bull_bars / valid_bars) * 100
    bear_pct = (bear_bars / valid_bars) * 100
    sideway_pct = (sideway_bars / valid_bars) * 100
    
    if bull_pct > 35:
        classification = 'STRONG BULLISH'
        class_icon = chr(0x1f4c8)
    elif bull_pct >= 30:
        classification = 'WEAK BULLISH'
        class_icon = chr(0x2197) + chr(0xfe0f)
    elif bear_pct > 35:
        classification = 'STRONG BEARISH'
        class_icon = chr(0x1f4c9)
    elif bear_pct >= 30:
        classification = 'WEAK BEARISH'
        class_icon = chr(0x2198) + chr(0xfe0f)
    else:
        classification = 'SIDEWAYS'
        class_icon = chr(0x27a1) + chr(0xfe0f)
    
    # ── Multi-window trend analysis ──
    # Last 100 bars
    last100_start = max(start_idx, n - 100)
    last100_valid = 0
    last100_bull = 0
    last100_bear = 0
    for i in range(last100_start, n):
        if np.isnan(adx_series.iloc[i]) or np.isnan(sma20.iloc[i]):
            continue
        last100_valid += 1
        close = float(data['Close'].iloc[i])
        sma = float(sma20.iloc[i])
        adx_val = float(adx_series.iloc[i])
        if adx_val > 25:
            if close > sma:
                last100_bull += 1
            else:
                last100_bear += 1
    
    last100_bull_pct = (last100_bull / last100_valid * 100) if last100_valid > 0 else 0
    last100_bear_pct = (last100_bear / last100_valid * 100) if last100_valid > 0 else 0
    
    # Last 200 bars
    last200_start = max(start_idx, n - 200)
    last200_valid = 0
    last200_bull = 0
    last200_bear = 0
    for i in range(last200_start, n):
        if np.isnan(adx_series.iloc[i]) or np.isnan(sma20.iloc[i]):
            continue
        last200_valid += 1
        close = float(data['Close'].iloc[i])
        sma = float(sma20.iloc[i])
        adx_val = float(adx_series.iloc[i])
        if adx_val > 25:
            if close > sma:
                last200_bull += 1
            else:
                last200_bear += 1
    
    last200_bull_pct = (last200_bull / last200_valid * 100) if last200_valid > 0 else 0
    last200_bear_pct = (last200_bear / last200_valid * 100) if last200_valid > 0 else 0
    
    # Interpretation helper
    def trend_interpretation(bull_pct, bear_pct):
        if bull_pct > 35:
            return 'Strong Bullish', '#4ade80', chr(0x1f4c8)
        elif bull_pct >= 25:
            return 'Weak Bullish', '#a3e635', chr(0x2197) + chr(0xfe0f)
        elif bear_pct > 35:
            return 'Strong Bearish', '#f87171', chr(0x1f4c9)
        elif bear_pct >= 25:
            return 'Weak Bearish', '#fb923c', chr(0x2198) + chr(0xfe0f)
        else:
            return 'Sideways', '#fbbf24', chr(0x27a1) + chr(0xfe0f)
    
    total_class, total_color, total_icon = trend_interpretation(bull_pct, bear_pct)
    if classification == 'STRONG BULLISH':
        total_class = 'STRONG BULLISH'
    elif classification == 'WEAK BULLISH':
        total_class = 'WEAK BULLISH'
    elif classification == 'STRONG BEARISH':
        total_class = 'STRONG BEARISH'
    elif classification == 'WEAK BEARISH':
        total_class = 'WEAK BEARISH'
    else:
        total_class = 'SIDEWAYS'
    
    l100_class, l100_color, l100_icon = trend_interpretation(last100_bull_pct, last100_bear_pct)
    l200_class, l200_color, l200_icon = trend_interpretation(last200_bull_pct, last200_bear_pct)
    
    if last100_bull_pct > 35:
        last100_class = 'STRONG BULLISH'
    elif last100_bull_pct >= 30:
        last100_class = 'WEAK BULLISH'
    elif last100_bear_pct > 35:
        last100_class = 'STRONG BEARISH'
    elif last100_bear_pct >= 30:
        last100_class = 'WEAK BEARISH'
    else:
        last100_class = 'SIDEWAYS'
    
    # Trend windows data
    trend_windows = [
        {
            'label': 'Last 100 bars',
            'bars': last100_valid,
            'bull_pct': round(last100_bull_pct, 1),
            'bear_pct': round(last100_bear_pct, 1),
            'sideway_pct': round(100 - last100_bull_pct - last100_bear_pct, 1),
            'classification': l100_class,
            'color': l100_color,
        },
        {
            'label': 'Last 200 bars',
            'bars': last200_valid,
            'bull_pct': round(last200_bull_pct, 1),
            'bear_pct': round(last200_bear_pct, 1),
            'sideway_pct': round(100 - last200_bull_pct - last200_bear_pct, 1),
            'classification': l200_class,
            'color': l200_color,
        },
        {
            'label': f'All ({valid_bars} bars)',
            'bars': valid_bars,
            'bull_pct': round(bull_pct, 1),
            'bear_pct': round(bear_pct, 1),
            'sideway_pct': round(sideway_pct, 1),
            'classification': total_class,
            'color': total_color,
        },
    ]
    
    # Current status values
    last_close = float(data['Close'].iloc[-1])
    last_sma20 = float(sma20.iloc[-1])
    last_adx_val = float(adx_series.iloc[-1])
    last_pdi = float(pdi_series.iloc[-1])
    last_mdi = float(mdi_series.iloc[-1])
    sma20_dist = ((last_close / last_sma20) - 1) * 100
    
    return {
        'valid_bars': valid_bars,
        'classification': classification,
        'class_icon': class_icon,
        'bull_pct': round(bull_pct, 1),
        'bear_pct': round(bear_pct, 1),
        'sideway_pct': round(sideway_pct, 1),
        'last100_valid': last100_valid,
        'last100_class': last100_class,
        'last100_bull_pct': round(last100_bull_pct, 1),
        'last100_bear_pct': round(last100_bear_pct, 1),
        'current': {
            'close': round(last_close, 2),
            'sma20': round(last_sma20, 2),
            'sma20_dist': round(sma20_dist, 2),
            'adx': round(last_adx_val, 1),
            'pdi': round(last_pdi, 1),
            'mdi': round(last_mdi, 1),
            'above_sma20': last_close > last_sma20,
            'pdi_above_mdi': last_pdi > last_mdi,
            'adx_above_25': last_adx_val > 25,
        },
        'trend_windows': trend_windows,
    }

def calculate_adx_sma_pct(data, adx_series, pdi_series, mdi_series, middle_bb, window=100):
    """
    Hitung persentase bar di mana ADX > 25 AND Close > SMA20 (Basis)
    dalam window bar terakhir (default: 100).

    Returns:
        (adx_sma_pct, trend_commentary)
    """
    valid_count = 0
    adx_sma_count = 0
    n = len(data)
    start = max(20, n - window)

    for i in range(start, n):
        if np.isnan(adx_series.iloc[i]):
            continue
        valid_count += 1
        close = float(data['Close'].iloc[i])
        sma20 = float(middle_bb.iloc[i])
        adx = float(adx_series.iloc[i])
        if adx > 25 and close > sma20:
            adx_sma_count += 1

    pct = (adx_sma_count / valid_count * 100) if valid_count > 0 else 0.0

    if pct >= 35:
        commentary = f"Uptrend Kuat ({pct:.0f}%)"
    elif pct >= 30:
        commentary = f"Medium Uptrend ({pct:.0f}%)"
    else:
        commentary = f"Sideways ({pct:.0f}%)"

    return round(pct, 1), commentary


# ============================================================
# BASIS ADX MULTI-TF MODERAT — H1 + Daily DI
# ============================================================

def calculate_daily_di_from_h1(h1_data):
    """
    Resample H1 data to daily and calculate +DI/-DI (DMI 14)
    
    Returns:
        (last_daily_pdi, last_daily_mdi) — scalar float or (nan, nan)
    """
    if h1_data is None or len(h1_data) < 30:
        return np.nan, np.nan
    
    # Resample H1 -> Daily
    daily = pd.DataFrame()
    daily['High'] = h1_data['High'].resample('D').max()
    daily['Low'] = h1_data['Low'].resample('D').min()
    daily['Close'] = h1_data['Close'].resample('D').last()
    daily = daily.dropna(subset=['Close'])
    
    if len(daily) < 20:
        return np.nan, np.nan
    
    _, dp, dm = calculate_adx(daily, period=14)
    
    if len(dp) < 1 or np.isnan(dp.iloc[-1]) or np.isnan(dm.iloc[-1]):
        return np.nan, np.nan
    
    return float(dp.iloc[-1]), float(dm.iloc[-1])


def download_h1_data(ticker, period="60d"):
    """Download H1 data from Yahoo Finance. Returns dataframe or None."""
    try:
        data = yf.download(ticker, period=period, interval="1h", progress=False)
        if data is None or data.empty or len(data) < 30:
            return None
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        return data
    except Exception:
        return None


def run_basis_adx_multitf_screener(list_path, list_type):
    """
    Helper function untuk menjalankan Basis ADX Multi-TF Moderat screener
    Data source: H1 (60d) + Daily DI (resampled from H1)
    
    Entry conditions (BUY):
      - Low > Donchian SL
      - Close > Basis (SMA20)
      - ADX > 20
      - PDI > MDI
      - PDI > PDI[5] (rising)
      - Daily PDI > Daily MDI (Multi-TF Moderat)
    """
    log_action('screener_basis_adx_mt', 'run_basis_adx_multitf_screener', params={'type': list_type})
    screener_start = time.time()
    _client_ip = _get_client_ip()
    _basis_mt = basis_adx_mt_screener_progress_map[_client_ip]
    
    try:
        tickers_df = pd.read_csv(list_path)
        if 'Symbol' not in tickers_df.columns:
            _basis_mt['status'] = 'error'
            _basis_mt['message'] = "Kolom 'Symbol' tidak ditemukan"
            return
        
        tickers = tickers_df['Symbol'].tolist()
        
        _basis_mt['is_running'] = True
        _basis_mt['total'] = len(tickers)
        _basis_mt['progress'] = 0
        _basis_mt['results'] = []
        _basis_mt['status'] = 'running'
        _basis_mt['message'] = f'Starting Basis ADX MT Screener for {list_type} ({len(tickers)} tickers)...'
        
        for i, ticker in enumerate(tickers):
            ticker = ticker.strip().upper()
            _basis_mt['current_ticker'] = ticker
            _basis_mt['progress'] = i + 1
            _basis_mt['message'] = f'Analyzing {ticker} (H1)...'
            
            try:
                # 1. Download H1 data
                data = download_h1_data(ticker, period="60d")
                if data is None:
                    _basis_mt['message'] = f'{ticker}: No H1 data'
                    continue
                
                numeric_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
                for col in numeric_cols:
                    if col in data.columns:
                        data[col] = pd.to_numeric(data[col], errors='coerce')
                
                data = data.dropna(subset=['Close'])
                if len(data) < 60:
                    _basis_mt['message'] = f'{ticker}: Insufficient H1 data'
                    continue
                
                # 2. Calculate H1 indicators
                sl_series = calculate_sl(data)
                upper_bb, middle_bb, lower_bb = calculate_bollinger_bands(data)
                adx_series, pdi_series, mdi_series = calculate_adx(data)
                
                last_price = float(data['Close'].iloc[-1])
                last_low = float(data['Low'].iloc[-1])
                last_sl = float(sl_series.iloc[-1])
                last_basis = float(middle_bb.iloc[-1])
                last_volume = float(data['Volume'].iloc[-1]) if 'Volume' in data.columns else 0
                
                if np.isnan(last_sl) or np.isnan(last_basis):
                    _basis_mt['message'] = f'{ticker}: Invalid SL or Basis data'
                    continue
                
                yesterday_close = float(data['Close'].iloc[-2]) if len(data) >= 2 else last_price
                change_pct = ((last_price - yesterday_close) / yesterday_close * 100) if yesterday_close != 0 else 0
                value_in_millions = (last_price * last_volume) / 1_000_000
                last_date = data.index[-1].strftime('%Y-%m-%d %H:%M')
                
                # H1 ADX values
                last_adx = float(adx_series.iloc[-1])
                last_pdi = float(pdi_series.iloc[-1])
                last_mdi = float(mdi_series.iloc[-1])
                pdi_5ago = float(pdi_series.iloc[-6]) if len(pdi_series) >= 6 else 0
                adx_5ago = float(adx_series.iloc[-6]) if len(adx_series) >= 6 else 0
                
                pdi_rising = last_pdi > pdi_5ago
                pdi_above_mdi = last_pdi > last_mdi
                adx_strong = last_adx > 20
                adx_rising = last_adx > adx_5ago
                is_nan = np.isnan(last_adx) or np.isnan(last_pdi) or np.isnan(last_mdi)
                
                # 3. Calculate Daily DI from H1 resample
                d_pdi, d_mdi = calculate_daily_di_from_h1(data)
                daily_mt_ok = (not np.isnan(d_pdi) and not np.isnan(d_mdi) and d_pdi > d_mdi)
                
                # 4. Determine recommendation with Multi-TF filter
                if last_low > last_sl and last_price > last_basis:
                    if (not is_nan
                            and pdi_above_mdi and adx_strong and pdi_rising and adx_rising
                            and daily_mt_ok):
                        recommendation = "BUY"
                    else:
                        recommendation = "HOLD LONG"
                elif last_price > last_sl:
                    recommendation = "HOLD LONG"
                else:
                    recommendation = "SHORT SELL"
                
                adx_sma_pct, trend_commentary = calculate_adx_sma_pct(data, adx_series, pdi_series, mdi_series, middle_bb)
                
                result_item = {
                    'ticker': ticker,
                    'last_date': last_date,
                    'price': round(last_price, 2),
                    'basis': round(last_basis, 2),
                    'change_pct': round(change_pct, 2),
                    'volume': float(last_volume),
                    'value': round(value_in_millions, 2),
                    'recommendation': recommendation,
                    'adx': round(float(adx_series.iloc[-1]), 2) if not np.isnan(float(adx_series.iloc[-1])) else None,
                    'pdi': round(float(pdi_series.iloc[-1]), 2) if not np.isnan(float(pdi_series.iloc[-1])) else None,
                    'mdi': round(float(mdi_series.iloc[-1]), 2) if not np.isnan(float(mdi_series.iloc[-1])) else None,
                    'd_pdi': round(d_pdi, 2) if not np.isnan(d_pdi) else None,
                    'd_mdi': round(d_mdi, 2) if not np.isnan(d_mdi) else None,
                    'adx_sma_pct': adx_sma_pct,
                    'trend_commentary': trend_commentary
                }
                
                _basis_mt['results'].append(result_item)
                _basis_mt['message'] = f'{ticker}: {recommendation}'
                
            except Exception as e:
                print(f"Error analyzing {ticker} (MT): {e}")
                _basis_mt['message'] = f'{ticker}: Error'
                continue
            
            time.sleep(0.5)
        
        _basis_mt['status'] = 'completed'
        _basis_mt['results'] = sorted(_basis_mt['results'],
            key=lambda x: (
                {'BUY': 3, 'HOLD LONG': 2, 'SHORT SELL': 1}.get(x.get('recommendation', ''), 0),
                x.get('adx_sma_pct', 0) or 0,
                x.get('value', 0) or 0
            ), reverse=True)
        _basis_mt['message'] = f'Basis ADX MT Screener completed: {len(_basis_mt["results"])} stocks analyzed'
        _basis_mt['is_running'] = False
        log_action('screener_basis_adx_mt', 'run_basis_adx_multitf_screener', params={'type': list_type}, status='success',
                  detail=f'{len(_basis_mt["results"])} stocks analyzed')
        
    except Exception as e:
        _basis_mt['status'] = 'error'
        _basis_mt['message'] = str(e)
        _basis_mt['is_running'] = False
        log_action('screener_basis_adx_mt', 'run_basis_adx_multitf_screener', params={'type': list_type}, status='error',
                  detail=str(e))


# ─── US Basis ADX MT ───

@app.route('/screener/us-basis-adx-mt', methods=['GET', 'POST', 'OPTIONS'])
def screener_us_basis_adx_mt():
    """Endpoint untuk mendapatkan data screener US Basis ADX Multi-TF"""
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
        return response
    
    log_action('screener_basis_adx_mt', 'us_basis_adx_mt', params={'market': 'US'})
    start_time = time.time()
    
    _client_ip = _get_client_ip()
    _basis_mt = basis_adx_mt_screener_progress_map[_client_ip]
    
    if _basis_mt['is_running']:
        log_action('screener_basis_adx_mt', 'us_basis_adx_mt', params={'market': 'US'}, status='error',
                  detail='Already running', duration_ms=(time.time() - start_time) * 1000)
        return jsonify({"status": "error", "message": "Basis ADX MT Screener sedang berjalan"}), 409
    
    _basis_mt['status'] = 'starting'
    _basis_mt['current_ticker'] = ''
    _basis_mt['progress'] = 0
    _basis_mt['total'] = 0
    _basis_mt['results'] = []
    _basis_mt['message'] = 'Initializing...'
    _basis_mt['is_running'] = False
    _basis_mt["run_id"] += 1  # Track new run
    
    # Load dari cache kalo ada (gak perlu extraction marker — pake H1 sendiri)
    cached_data, metadata, error = load_cached_screener('us-basis-adx-mt')
    if cached_data is not None:
        log_action('screener_basis_adx_mt', 'us_basis_adx_mt', params={'market': 'US'}, status='success',
                  detail=f'cached: {len(cached_data)} results')
        _basis_mt['results'] = cached_data.to_dict('records')
        _basis_mt['status'] = 'completed'
        _basis_mt['progress'] = len(cached_data)
        clean_records = []
        for item in cached_data.to_dict('records'):
            cleaned = {}
            for k, v in item.items():
                if isinstance(v, float) and (v != v or v == float('inf') or v == float('-inf')):
                    cleaned[k] = None
                else:
                    cleaned[k] = v
            clean_records.append(cleaned)
        return jsonify({"status": "success", "message": "Data dari cache", "count": len(cached_data), "data": clean_records, "from_cache": True, "cache_timestamp": metadata['timestamp']})
    
    uslist_path = os.path.join(os.path.dirname(__file__), 'uslist.csv')
    if not os.path.exists(uslist_path):
        log_action('screener_basis_adx_mt', 'us_basis_adx_mt', params={'market': 'US'}, status='error',
                  detail='uslist.csv not found', duration_ms=(time.time() - start_time) * 1000)
        return jsonify({"status": "error", "message": "File uslist.csv tidak ditemukan"}), 404
    
    try:
        _basis_mt['is_running'] = True
        run_basis_adx_multitf_screener(uslist_path, 'US')
        if _basis_mt['results']:
            results_df = pd.DataFrame(_basis_mt['results'])
            save_screener_to_cache('us-basis-adx-mt', results_df)
        touch_screener_marker('us-basis-adx-mt')
        duration = (time.time() - start_time) * 1000
        log_action('screener_basis_adx_mt', 'us_basis_adx_mt', params={'market': 'US'}, status='success',
                  detail=f'{len(_basis_mt["results"])} results', duration_ms=duration)
        return jsonify({"status": "success", "message": _basis_mt['message'],
            "count": len(_basis_mt['results']), "data": _basis_mt['results']})
    except Exception as e:
        duration = (time.time() - start_time) * 1000
        log_action('screener_basis_adx_mt', 'us_basis_adx_mt', params={'market': 'US'}, status='error', detail=str(e), duration_ms=duration)
        return jsonify({"status": "error", "message": str(e)}), 500


# ─── ID Basis ADX MT ───

@app.route('/screener/id-basis-adx-mt', methods=['GET', 'POST', 'OPTIONS'])
def screener_id_basis_adx_mt():
    """Endpoint untuk mendapatkan data screener ID Basis ADX Multi-TF"""
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
        return response
    
    log_action('screener_basis_adx_mt', 'id_basis_adx_mt', params={'market': 'ID'})
    start_time = time.time()
    
    _client_ip = _get_client_ip()
    _basis_mt = basis_adx_mt_screener_progress_map[_client_ip]
    
    if _basis_mt['is_running']:
        log_action('screener_basis_adx_mt', 'id_basis_adx_mt', params={'market': 'ID'}, status='error',
                  detail='Already running', duration_ms=(time.time() - start_time) * 1000)
        return jsonify({"status": "error", "message": "Basis ADX MT Screener sedang berjalan"}), 409
    
    _basis_mt['status'] = 'starting'
    _basis_mt['current_ticker'] = ''
    _basis_mt['progress'] = 0
    _basis_mt['total'] = 0
    _basis_mt['results'] = []
    _basis_mt['message'] = 'Initializing...'
    _basis_mt['is_running'] = False
    _basis_mt["run_id"] += 1
    
    # Load dari cache kalo ada (gak perlu extraction marker)
    cached_data, metadata, error = load_cached_screener('id-basis-adx-mt')
    if cached_data is not None:
        log_action('screener_basis_adx_mt', 'id_basis_adx_mt', params={'market': 'ID'}, status='success',
                  detail=f'cached: {len(cached_data)} results')
        _basis_mt['results'] = cached_data.to_dict('records')
        _basis_mt['status'] = 'completed'
        _basis_mt['progress'] = len(cached_data)
        clean_records = []
        for item in cached_data.to_dict('records'):
            cleaned = {}
            for k, v in item.items():
                if isinstance(v, float) and (v != v or v == float('inf') or v == float('-inf')):
                    cleaned[k] = None
                else:
                    cleaned[k] = v
            clean_records.append(cleaned)
        return jsonify({"status": "success", "message": "Data dari cache", "count": len(cached_data), "data": clean_records, "from_cache": True, "cache_timestamp": metadata['timestamp']})
    
    idlist_path = os.path.join(os.path.dirname(__file__), 'idlist.csv')
    if not os.path.exists(idlist_path):
        log_action('screener_basis_adx_mt', 'id_basis_adx_mt', params={'market': 'ID'}, status='error',
                  detail='idlist.csv not found', duration_ms=(time.time() - start_time) * 1000)
        return jsonify({"status": "error", "message": "File idlist.csv tidak ditemukan"}), 404
    
    try:
        _basis_mt['is_running'] = True
        run_basis_adx_multitf_screener(idlist_path, 'ID')
        if _basis_mt['results']:
            results_df = pd.DataFrame(_basis_mt['results'])
            save_screener_to_cache('id-basis-adx-mt', results_df)
        touch_screener_marker('id-basis-adx-mt')
        duration = (time.time() - start_time) * 1000
        log_action('screener_basis_adx_mt', 'id_basis_adx_mt', params={'market': 'ID'}, status='success',
                  detail=f'{len(_basis_mt["results"])} results', duration_ms=duration)
        return jsonify({"status": "success", "message": _basis_mt['message'],
            "count": len(_basis_mt['results']), "data": _basis_mt['results']})
    except Exception as e:
        duration = (time.time() - start_time) * 1000
        log_action('screener_basis_adx_mt', 'id_basis_adx_mt', params={'market': 'ID'}, status='error', detail=str(e), duration_ms=duration)
        return jsonify({"status": "error", "message": str(e)}), 500


# ─── Basis ADX MT Progress SSE ───

@app.route('/screener/basis-adx-mt-progress', methods=['GET', 'OPTIONS'])
def screener_basis_adx_mt_progress():
    """SSE endpoint untuk real-time progress Basis ADX MT screener"""
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'GET,OPTIONS')
        return response
    
    _client_ip = _get_client_ip()
    
    def _find_active_basis_mt():
        for ip, p in basis_adx_mt_screener_progress_map.items():
            if p['is_running']:
                return ip, p
        for ip, p in basis_adx_mt_screener_progress_map.items():
            if p['status'] == 'completed' and p['results']:
                return ip, p
        return _client_ip, basis_adx_mt_screener_progress_map[_client_ip]
    
    def generate():
        last_progress = None
        idle_loops = 0
        max_idle_loops = 30
        completed_wait_loops = 0
        active_ip, _basis_mt = _find_active_basis_mt()
        _connected_run_id = _basis_mt["run_id"]
        while True:
            new_ip, new_basis_mt = _find_active_basis_mt()
            if new_ip != active_ip:
                active_ip = new_ip
                _basis_mt = new_basis_mt
                _connected_run_id = _basis_mt["run_id"]
                last_progress = None
            current_progress = {
                'status': _basis_mt['status'],
                'current_ticker': _basis_mt['current_ticker'],
                'progress': _basis_mt['progress'],
                'total': _basis_mt['total'],
                'results_count': len(_basis_mt['results']),
                'message': _basis_mt['message'],
                'run_id': _basis_mt['run_id'],
            }
            if current_progress['status'] == 'completed' and current_progress['results_count'] > 0:
                completed_wait_loops += 1
                if _connected_run_id == current_progress.get('run_id', 0) and completed_wait_loops <= 3:
                    time.sleep(0.5)
                    continue
                if current_progress != last_progress:
                    yield "data: " + json.dumps(current_progress) + "\n\n"
                break
            if current_progress['status'] == 'starting' and current_progress['results_count'] == 0:
                if current_progress != last_progress:
                    last_progress = current_progress.copy()
                    yield "data: " + json.dumps(current_progress) + "\n\n"
                time.sleep(1)
                continue
            if current_progress['status'] == 'idle':
                idle_loops += 1
                if idle_loops >= max_idle_loops:
                    break
                last_progress = current_progress.copy()
                time.sleep(1)
                continue
            if current_progress != last_progress:
                last_progress = current_progress.copy()
                yield "data: " + json.dumps(current_progress) + "\n\n"
            if current_progress['status'] in ['completed', 'error']:
                break
            time.sleep(1)
    
    from flask import Response
    return Response(generate(), mimetype='text/event-stream')
