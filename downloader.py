import os
import argparse
import pandas as pd
import yfinance as yf
import time
from datetime import datetime

def check_rate_limit(output_folder, threshold_minutes=60):
    """
    Memeriksa apakah ada file di folder output yang diupdate kurang dari threshold_minutes yang lalu.
    Returns: (is_safe, minutes_left)
    """
    if not os.path.exists(output_folder):
        return True, 0
    
    current_time = time.time()
    files = [f for f in os.listdir(output_folder) if f.endswith(".csv")]
    
    if not files:
        return True, 0

    for filename in files:
        file_path = os.path.join(output_folder, filename)
        last_modified = os.path.getmtime(file_path)
        diff_minutes = (current_time - last_modified) / 60
        
        if diff_minutes < threshold_minutes:
            return False, int(threshold_minutes - diff_minutes)
    
    return True, 0

def get_last_date(file_path):
    """Membaca tanggal terakhir dari file CSV yang sudah ada."""
    try:
        # yfinance CSV has multi-row headers. Read it and get the max date from index.
        df = pd.read_csv(file_path, index_col=0, parse_dates=True, header=[0,1,2])
        if df.empty:
            return None
        return df.index.max()
    except Exception:
        try:
            # Fallback for simple format
            df = pd.read_csv(file_path, index_col=0, parse_dates=True)
            return df.index.max()
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            return None

def download_ticker_data(ticker, output_folder):
    file_path = os.path.join(output_folder, f"{ticker}.csv")
    last_date = None
    
    if os.path.exists(file_path):
        last_date = get_last_date(file_path)
    
    today = datetime.now()
    
    if last_date is not None and not pd.isnull(last_date):
        # Ensure last_date is a datetime object and naive for comparison
        if hasattr(last_date, 'to_pydatetime'):
            last_date = last_date.to_pydatetime()
        if last_date.tzinfo is not None:
            last_date = last_date.replace(tzinfo=None)
            
        delta = (today - last_date).days
        days_to_fetch = max(delta + 1, 1)
            
        print(f"[{ticker}] Incremental update: last date {last_date.date()}, fetching last {days_to_fetch} days.")
        
        new_data = yf.download(ticker, period=f"{days_to_fetch}d", progress=False)
        
        if not new_data.empty:
            # Load old data with same header structure as new_data
            h_count = len(new_data.columns.levels)
            old_data = pd.read_csv(file_path, header=list(range(h_count)), index_col=0, parse_dates=True)
            
            combined_data = pd.concat([old_data, new_data])
            # Drop duplicates by index
            combined_data = combined_data[~combined_data.index.duplicated(keep='last')]
            combined_data.sort_index(inplace=True)
            combined_data.to_csv(file_path)
            print(f"[{ticker}] Updated successfully.")
        else:
            print(f"[{ticker}] No new data found.")
    else:
        print(f"[{ticker}] First time download: fetching last 200 days.")
        data = yf.download(ticker, period="200d", progress=False)
        if not data.empty:
            data.to_csv(file_path)
            print(f"[{ticker}] Saved to {file_path}")
        else:
            print(f"[{ticker}] Failed to download data.")

def main():
    parser = argparse.ArgumentParser(description="Yahoo Finance Stock Downloader")
    parser.add_argument("input_file", help="Path ke file CSV yang berisi daftar ticker (kolom 'Symbol')")
    parser.add_argument("--output-folder", default="cache", help="Folder output untuk menyimpan file CSV (default: cache)")
    args = parser.parse_args()
    
    output_folder = args.output_folder
    
    # Fitur Rate-Limit Protection
    is_safe, minutes_left = check_rate_limit(output_folder)
    if not is_safe:
        print(f"Error: Program baru saja dijalankan kurang dari satu jam lalu.")
        print(f"Harap tunggu sekitar {minutes_left} menit lagi sebelum menarik data kembali untuk mencegah rate limit.")
        return

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    
    if not os.path.exists(args.input_file):
        print(f"Error: File {args.input_file} tidak ditemukan.")
        return
    
    try:
        tickers_df = pd.read_csv(args.input_file)
        if 'Symbol' not in tickers_df.columns:
            print("Error: Kolom 'Symbol' tidak ditemukan dalam file input.")
            return
        
        tickers = tickers_df['Symbol'].tolist()
        
        for ticker in tickers:
            download_ticker_data(ticker, output_folder)
            
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
