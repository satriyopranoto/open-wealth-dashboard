# Graph Report - .  (2026-05-27)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 106 nodes · 180 edges · 9 communities (7 shown, 2 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 3 edges (avg confidence: 0.93)
- Token cost: 0 input · 0 output

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

## God Nodes (most connected - your core abstractions)
1. `log_action()` - 18 edges
2. `load_cached_screener()` - 10 edges
3. `save_screener_to_cache()` - 10 edges
4. `analyze_stock()` - 8 edges
5. `check_rate_limit()` - 8 edges
6. `download_stock_data()` - 7 edges
7. `run_bb_screener()` - 7 edges
8. `read_recent_logs()` - 6 edges
9. `screener_us_bb_breakout()` - 6 edges
10. `download_fundamental_data()` - 5 edges

## Surprising Connections (you probably didn't know these)
- `index()` --calls--> `log_action()`  [EXTRACTED]
  app.py → log_utils.py
- `run_bb_screener()` --calls--> `log_action()`  [EXTRACTED]
  app.py → log_utils.py
- `refresh_data()` --calls--> `log_action()`  [EXTRACTED]
  app.py → log_utils.py
- `analyze_stock()` --calls--> `log_action()`  [EXTRACTED]
  app.py → log_utils.py
- `extract_us_stocks()` --calls--> `log_action()`  [EXTRACTED]
  app.py → log_utils.py

## Communities (9 total, 2 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.11
Nodes (20): analyze_stock(), calculate_bollinger_bands(), calculate_rsi(), calculate_sl(), create_extraction_marker(), extract_progress(), fetch_related_news(), index() (+12 more)

### Community 1 - "Community 1"
Cohesion: 0.18
Nodes (20): get_screener_cache_file(), load_cached_screener(), Endpoint untuk mendapatkan data screener day gainers Indonesia, Endpoint untuk mendapatkan data screener net net strategy Indonesia, Endpoint untuk mendapatkan data screener The Acquirers Multiple Indonesia, Menyimpan data screener ke cache dalam format CSV dengan metadata, Endpoint untuk mendapatkan data screener US BB Breakout, Mendapatkan path file cache untuk data screener (+12 more)

### Community 2 - "Community 2"
Cohesion: 0.15
Nodes (13): Logging System, Halaman untuk melihat log activity dengan filter tanggal dan limit., view_logs(), _get_client_ip(), _get_log_path(), _get_log_path_for_date(), list_available_dates(), Logging utility untuk mencatat setiap action/penggunaan feature. Menyimpan log d (+5 more)

### Community 3 - "Community 3"
Cohesion: 0.18
Nodes (13): extract_id_stocks(), extract_status(), extract_us_stocks(), Endpoint untuk mengekstrak data US stocks dari uslist.csv, Memeriksa apakah ekstraksi sudah dilakukan kurang dari RATE_LIMIT_MINUTES menit, Endpoint untuk mengekstrak data ID stocks dari idlist.csv, Endpoint untuk mendapatkan status extraction saat ini, check_rate_limit() (+5 more)

### Community 4 - "Community 4"
Cohesion: 0.22
Nodes (10): download_stock_data(), get_cache_file_path(), load_cached_data(), Memuat data dari cache jika ada dan masih valid (maksimal 1 hari)     Mengembali, Menyimpan data ke cache dalam format CSV dengan metadata, Fungsi helper untuk download data dengan retry logic sederhana     force_refresh, Endpoint untuk refresh data - mendownload ulang data dari Yahoo Finance, Mendapatkan path file cache untuk ticker tertentu (+2 more)

### Community 5 - "Community 5"
Cohesion: 0.39
Nodes (4): Cache System, Flask Backend, Frontend SPA, Nginx Reverse Proxy

### Community 6 - "Community 6"
Cohesion: 0.29
Nodes (8): download_fundamental_data(), get_fundamental_cache_file(), load_cached_fundamental(), Memuat data fundamental dari cache jika ada dan masih valid (maksimal 1 hari), Menyimpan data fundamental ke cache, Download data fundamental dari Yahoo Finance, Mendapatkan path file cache untuk data fundamental, save_fundamental_to_cache()

## Knowledge Gaps
- **2 isolated node(s):** `allow`, `python.defaultInterpreterPath`
  These have ≤1 connection - possible missing edges or undocumented components.
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `check_rate_limit()` connect `Community 3` to `Community 0`?**
  _High betweenness centrality (0.122) - this node is a cross-community bridge._
- **Why does `log_action()` connect `Community 1` to `Community 0`, `Community 2`, `Community 3`, `Community 4`?**
  _High betweenness centrality (0.063) - this node is a cross-community bridge._
- **Why does `read_recent_logs()` connect `Community 2` to `Community 0`?**
  _High betweenness centrality (0.037) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `Flask Backend` (e.g. with `index.html` and `Frontend SPA`) actually correct?**
  _`Flask Backend` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Logging utility untuk mencatat setiap action/penggunaan feature. Menyimpan log d`, `Mendapatkan path file log untuk tanggal tertentu.`, `Mengembalikan daftar tanggal yang memiliki file log.` to the rest of the system?**
  _40 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.10507246376811594 - nodes in this community are weakly interconnected._