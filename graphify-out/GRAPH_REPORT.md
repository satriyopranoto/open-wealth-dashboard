# Graph Report - stocktrade  (2026-07-21)

## Corpus Check
- 12 files · ~26,045 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 423 nodes · 674 edges · 31 communities (27 shown, 4 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 23 edges (avg confidence: 0.82)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `3e7c22ae`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]

## God Nodes (most connected - your core abstractions)
1. `log_action()` - 49 edges
2. `save_screener_to_cache()` - 19 edges
3. `load_cached_screener()` - 17 edges
4. `_get_client_ip()` - 17 edges
5. `save_screener_to_cache()` - 15 edges
6. `load_cached_screener()` - 14 edges
7. `analyze_stock()` - 13 edges
8. `run_basis_adx_multitf_screener()` - 13 edges
9. `Common Issues & Fixes` - 13 edges
10. `run_basis_adx_screener()` - 12 edges

## Surprising Connections (you probably didn't know these)
- `index()` --calls--> `log_action()`  [INFERRED]
  app.py → log_utils.py
- `refresh_data()` --calls--> `log_action()`  [INFERRED]
  app.py → log_utils.py
- `analyze_stock()` --calls--> `log_action()`  [INFERRED]
  app.py → log_utils.py
- `extract_us_stocks()` --calls--> `log_action()`  [INFERRED]
  app.py → log_utils.py
- `extract_id_stocks()` --calls--> `log_action()`  [INFERRED]
  app.py → log_utils.py

## Communities (31 total, 4 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.06
Nodes (55): check_fundamental_run_status(), clean_nan_in_records(), get_screener_cache_file(), load_cached_fundamental_screener(), load_cached_screener(), Endpoint untuk mendapatkan data screener day gainers Indonesia, Endpoint untuk mendapatkan data screener net net strategy Indonesia, Endpoint untuk mendapatkan data screener The Acquirers Multiple Indonesia (+47 more)

### Community 1 - "Community 1"
Cohesion: 0.12
Nodes (16): check_rate_limit_for_list(), create_extraction_marker(), extract_id_stocks(), extract_progress(), extract_status(), extract_us_stocks(), get_last_extraction_time(), Mengembalikan mtime marker file ekstraksi terakhir, atau None jika belum pernah. (+8 more)

### Community 2 - "Community 2"
Cohesion: 0.09
Nodes (20): Halaman untuk melihat log activity dengan filter tanggal dan limit., view_logs(), Logging System, Action Logging — Implementation Plan, Task 1: Create log_utils.py module, Task 4: Add logging to all 8 screener routes, Task 5: Add logging to extraction routes, Task 6: Add logging to BB Breakout routes (+12 more)

### Community 3 - "Community 3"
Cohesion: 0.19
Nodes (13): extract_id_stocks(), extract_status(), extract_us_stocks(), Endpoint untuk mengekstrak data US stocks dari uslist.csv, Memeriksa apakah ekstraksi sudah dilakukan kurang dari RATE_LIMIT_MINUTES menit, Endpoint untuk mengekstrak data ID stocks dari idlist.csv, Endpoint untuk mendapatkan status extraction saat ini, check_rate_limit() (+5 more)

### Community 4 - "Community 4"
Cohesion: 0.13
Nodes (26): index(), load_cached_screener(), Memuat data screener dari cache jika ada dan masih valid.          Jika extracti, Endpoint untuk mendapatkan data screener most active stocks Indonesia, Endpoint untuk mendapatkan data screener day gainers Indonesia, Endpoint untuk mendapatkan data screener net net strategy Indonesia, Endpoint untuk mendapatkan data screener The Acquirers Multiple Indonesia, Endpoint untuk mendapatkan data screener US most active stocks (+18 more)

### Community 5 - "Community 5"
Cohesion: 0.14
Nodes (13): Cache System, Commands, Cara Mengubah Base URL, Catatan Penting, File `.env`, Instalasi Dependencies, Isi File `.env`, Konfigurasi Environment Stock Analyzer (+5 more)

### Community 6 - "Community 6"
Cohesion: 0.16
Nodes (15): clean_float(), download_fundamental_data(), get_fundamental_cache_file(), load_cached_fundamental(), Mendapatkan path file cache untuk data fundamental, Memuat data fundamental dari cache jika ada dan masih valid (maksimal 1 hari), Menyimpan data fundamental ke cache, Helper function untuk menjalankan fundamental screener pada watchlist (+7 more)

### Community 9 - "Community 9"
Cohesion: 0.14
Nodes (14): Architecture, Backend (`app.py`), Cache summary, CLI downloader (`downloader.py`), Data pipeline per `/analyze` request, Docker / Nginx, Environment, Extraction system (+6 more)

### Community 10 - "Community 10"
Cohesion: 0.14
Nodes (14): Action Logging, Architecture, Backend routes, Cache structure (`cache/`), Deployment, Docker Networking & Client IP, Docker (recommended), Features (+6 more)

### Community 14 - "Community 14"
Cohesion: 0.11
Nodes (17): Architecture, Backend (`app.py`), Cache summary, CLI downloader (`downloader.py`), code:bash (# Install dependencies), code:block2 (FLASK_APP=app.py), Commands, Data pipeline per `/analyze` request (+9 more)

### Community 15 - "Community 15"
Cohesion: 0.11
Nodes (18): Action Logging, Architecture, Backend routes, Cache structure (`cache/`), code:yaml (services:), code:bash (# Build dan run containers), code:yaml (environment:), code:bash (# 1. Create and activate virtual environment) (+10 more)

### Community 16 - "Community 16"
Cohesion: 0.11
Nodes (17): 10. SL Timeframe Sync (Risk Management), 11. Screener State Management & Clean Restart, 12. Timeframe-Aware Recommendation, 1. CONNECTION ABORTED / JSON Parse Error, 2. Bokeh Chart Not Stretching Width, 3. Nginx DNS Resolution (Network Alias), 4. Docker Infrastructure, 5. Analyze Endpoint Method Change (+9 more)

### Community 17 - "Community 17"
Cohesion: 0.12
Nodes (11): acquire_data_sync_lock(), create_extraction_marker(), extract_progress(), Release lock untuk data sync., SSE endpoint untuk real-time progress extraction, Membuat marker file untuk tracking waktu ekstraksi terakhir., SSE endpoint untuk real-time progress BB screener, Coba acquire lock untuk data sync. Returns (success, owner_ip). (+3 more)

### Community 18 - "Community 18"
Cohesion: 0.18
Nodes (16): calculate_adx(), calculate_adx_sma_pct(), calculate_daily_di_from_h1(), download_h1_data(), get_recommendation(), get_recommendation_for_timeframe(), Return trading recommendation for a specific timeframe.     - D1, W1, MN: Basis, Helper function untuk menjalankan Basis ADX screener pada watchlist     Logic: L (+8 more)

### Community 19 - "Community 19"
Cohesion: 0.13
Nodes (14): Cara Mengubah Base URL, Catatan Penting, code:bash (# Konfigurasi Flask App), code:bash (API_BASE_URL=http://127.0.0.1:5000), code:bash (API_BASE_URL=http://192.168.1.100:5000), code:bash (API_BASE_URL=https://your-domain.com), code:bash (pip install -r requirements.txt), code:bash (python app.py) (+6 more)

### Community 20 - "Community 20"
Cohesion: 0.14
Nodes (15): download_stock_data(), get_cache_file_path(), load_cached_data(), Mendapatkan path file cache untuk ticker tertentu, Memuat data dari cache jika ada dan masih valid (maksimal 1 hari)     Mengembali, Menyimpan data ke cache dalam format CSV dengan metadata, Fungsi helper untuk download data dengan retry logic sederhana     force_refresh, Endpoint untuk refresh data - mendownload ulang data dari Yahoo Finance (+7 more)

### Community 21 - "Community 21"
Cohesion: 0.19
Nodes (13): _add_hover(), _adx_figure(), _candlestick_figure(), _format_xaxis_date(), generate_chart(), _make_base_figure(), Bokeh interactive chart module for stocktrade. Generates candlestick + ADX char, Draw ADX, +DI, -DI indicators on figure *p*. (+5 more)

### Community 22 - "Community 22"
Cohesion: 0.24
Nodes (11): clean_float(), download_fundamental_data(), get_fundamental_cache_file(), load_cached_fundamental(), Helper function untuk menjalankan fundamental screener pada watchlist, Memuat data fundamental dari cache jika ada dan masih valid (maksimal 1 hari), Menyimpan data fundamental ke cache, Download data fundamental dari Yahoo Finance (+3 more)

### Community 23 - "Community 23"
Cohesion: 0.22
Nodes (10): download_stock_data(), get_cache_file_path(), load_cached_data(), Memuat data dari cache jika ada dan masih valid (maksimal 1 hari)     Mengembali, Menyimpan data ke cache dalam format CSV dengan metadata, Fungsi helper untuk download data dengan retry logic sederhana     force_refresh, Endpoint untuk refresh data - mendownload ulang data dari Yahoo Finance, Mendapatkan path file cache untuk ticker tertentu (+2 more)

### Community 24 - "Community 24"
Cohesion: 0.31
Nodes (9): check_fundamental_run_status(), clean_nan_in_records(), get_screener_cache_file(), load_cached_fundamental_screener(), Mendapatkan path file cache untuk data screener, Check if we can use cached screener results or if we need to pull fresh data., Memuat data fundamental screener dari cache tanpa membatasi dengan TTL 1 jam., screener_id_fundamental() (+1 more)

### Community 25 - "Community 25"
Cohesion: 0.22
Nodes (9): analyze_stock(), calculate_rsi(), fetch_related_news(), Endpoint utama untuk menerima request, mendownload data,      menghitung RSI, me, Fetch related news from Google News dengan multiple languages dan regions, Menghitung RSI menggunakan rumus standar, Endpoint utama untuk menerima request, mendownload data,      menghitung RSI, me, Menghitung RSI menggunakan rumus standar (+1 more)

### Community 26 - "Community 26"
Cohesion: 0.22
Nodes (9): calculate_bollinger_bands(), calculate_trend_analysis(), get_trend_analysis_for_timeframe(), Return trend analysis (ADX + SMA20) for a specific timeframe.     Allows Trend A, Helper function untuk menjalankan BB screener pada watchlist, Trend Analysis menggunakan framework ADX(14) + SMA20.     Menghitung persentase, Menghitung Bollinger Bands     - Middle Band = SMA period hari     - Upper Band, Menghitung Bollinger Bands     - Middle Band = SMA period hari     - Upper Band (+1 more)

### Community 27 - "Community 27"
Cohesion: 0.25
Nodes (8): analyze_stock(), calculate_rsi(), calculate_sl(), fetch_related_news(), Fetch related news from Google News dengan multiple languages dan regions, Menghitung RSI menggunakan rumus standar, Konversi logika Pine Script ke Python:     erof = atr_multiple * atr_period, Endpoint utama untuk menerima request, mendownload data,      menghitung RSI, me

### Community 28 - "Community 28"
Cohesion: 0.29
Nodes (7): calculate_sl(), get_sl_for_timeframe(), Serve standalone Bokeh chart HTML for iframe embedding.     Supports timeframe p, Return SL (Donchian) for a specific timeframe — lightweight, no cache., Konversi logika Pine Script ke Python:     erof = atr_multiple * atr_period, Konversi logika Pine Script ke Python:     erof = atr_multiple * atr_period, serve_chart_html()

### Community 29 - "Community 29"
Cohesion: 0.33
Nodes (6): calculate_bollinger_bands(), Helper function untuk menjalankan BB screener pada watchlist, Endpoint untuk mendapatkan data screener ID BB Breakout, Menghitung Bollinger Bands     - Middle Band = SMA period hari     - Upper Band, run_bb_screener(), screener_id_bb_breakout()

## Knowledge Gaps
- **83 isolated node(s):** `allow`, `allow`, `1. CONNECTION ABORTED / JSON Parse Error`, `code:css ([data-root-id] { display: block !important; width: 100% !imp)`, `code:bash (docker run ... --network stocktrade_default --network-alias )` (+78 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `log_action()` connect `Community 4` to `Community 0`, `Community 1`, `Community 2`, `Community 3`, `Community 6`, `Community 17`, `Community 18`, `Community 20`, `Community 22`, `Community 23`, `Community 24`, `Community 25`, `Community 26`, `Community 27`, `Community 29`?**
  _High betweenness centrality (0.252) - this node is a cross-community bridge._
- **Why does `Architecture` connect `Community 9` to `Community 5`?**
  _High betweenness centrality (0.048) - this node is a cross-community bridge._
- **Why does `Open Wealth Dashboard` connect `Community 10` to `Community 5`?**
  _High betweenness centrality (0.048) - this node is a cross-community bridge._
- **Are the 19 inferred relationships involving `log_action()` (e.g. with `index()` and `refresh_data()`) actually correct?**
  _`log_action()` has 19 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Coba acquire lock untuk data sync. Returns (success, owner_ip).`, `Release lock untuk data sync.`, `Mendapatkan path file cache untuk ticker tertentu` to the rest of the system?**
  _217 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.055218855218855216 - nodes in this community are weakly interconnected._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.11578947368421053 - nodes in this community are weakly interconnected._