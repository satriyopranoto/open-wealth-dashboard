# Graph Report - stocktrade  (2026-06-08)

## Corpus Check
- 12 files · ~18,738 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 251 nodes · 412 edges · 14 communities (10 shown, 4 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 23 edges (avg confidence: 0.82)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `64cb8301`
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

## God Nodes (most connected - your core abstractions)
1. `log_action()` - 38 edges
2. `save_screener_to_cache()` - 15 edges
3. `load_cached_screener()` - 14 edges
4. `Architecture` - 10 edges
5. `load_cached_screener()` - 10 edges
6. `save_screener_to_cache()` - 10 edges
7. `check_rate_limit()` - 9 edges
8. `analyze_stock()` - 8 edges
9. `run_bb_screener()` - 8 edges
10. `run_fundamental_screener()` - 8 edges

## Surprising Connections (you probably didn't know these)
- `index()` --calls--> `log_action()`  [INFERRED]
  app.py → //wsl$/Ubuntu/home/satri/stocktrade/log_utils.py
- `refresh_data()` --calls--> `log_action()`  [INFERRED]
  app.py → //wsl$/Ubuntu/home/satri/stocktrade/log_utils.py
- `analyze_stock()` --calls--> `log_action()`  [INFERRED]
  app.py → //wsl$/Ubuntu/home/satri/stocktrade/log_utils.py
- `screener_most_active()` --calls--> `log_action()`  [INFERRED]
  app.py → //wsl$/Ubuntu/home/satri/stocktrade/log_utils.py
- `screener_day_gainers()` --calls--> `log_action()`  [INFERRED]
  app.py → //wsl$/Ubuntu/home/satri/stocktrade/log_utils.py

## Import Cycles
- None detected.

## Communities (14 total, 4 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.06
Nodes (55): index(), analyze_stock(), calculate_bollinger_bands(), calculate_rsi(), calculate_sl(), create_extraction_marker(), download_stock_data(), extract_id_stocks() (+47 more)

### Community 1 - "Community 1"
Cohesion: 0.06
Nodes (52): analyze_stock(), calculate_rsi(), calculate_sl(), check_fundamental_run_status(), check_rate_limit_for_list(), clean_float(), clean_nan_in_records(), create_extraction_marker() (+44 more)

### Community 2 - "Community 2"
Cohesion: 0.10
Nodes (21): Halaman untuk melihat log activity dengan filter tanggal dan limit., view_logs(), Logging System, Action Logging — Implementation Plan, Task 1: Create log_utils.py module, Task 4: Add logging to all 8 screener routes, Task 5: Add logging to extraction routes, Task 6: Add logging to BB Breakout routes (+13 more)

### Community 3 - "Community 3"
Cohesion: 0.29
Nodes (9): extract_status(), Memeriksa apakah ekstraksi sudah dilakukan kurang dari RATE_LIMIT_MINUTES menit, Endpoint untuk mendapatkan status extraction saat ini, check_rate_limit(), download_ticker_data(), get_last_date(), main(), Membaca tanggal terakhir dari file CSV yang sudah ada. (+1 more)

### Community 4 - "Community 4"
Cohesion: 0.09
Nodes (30): calculate_bollinger_bands(), get_last_extraction_time(), load_cached_screener(), Mengembalikan mtime marker file ekstraksi terakhir, atau None jika belum pernah., Memuat data screener dari cache jika ada dan masih valid.          Jika extracti, Endpoint untuk mendapatkan data screener most active stocks Indonesia, Endpoint untuk mendapatkan data screener day gainers Indonesia, Endpoint untuk mendapatkan data screener net net strategy Indonesia (+22 more)

### Community 5 - "Community 5"
Cohesion: 0.16
Nodes (12): Cache System, Cara Mengubah Base URL, Catatan Penting, File `.env`, Instalasi Dependencies, Isi File `.env`, Konfigurasi Environment Stock Analyzer, Menjalankan Aplikasi (+4 more)

### Community 6 - "Community 6"
Cohesion: 0.29
Nodes (8): download_fundamental_data(), get_fundamental_cache_file(), load_cached_fundamental(), Memuat data fundamental dari cache jika ada dan masih valid (maksimal 1 hari), Menyimpan data fundamental ke cache, Download data fundamental dari Yahoo Finance, Mendapatkan path file cache untuk data fundamental, save_fundamental_to_cache()

### Community 9 - "Community 9"
Cohesion: 0.12
Nodes (15): Architecture, Backend (`app.py`), Cache summary, CLI downloader (`downloader.py`), Commands, Data pipeline per `/analyze` request, Docker / Nginx, Environment (+7 more)

### Community 10 - "Community 10"
Cohesion: 0.14
Nodes (14): Action Logging, Architecture, Backend routes, Cache structure (`cache/`), Deployment, Docker Networking & Client IP, Docker (recommended), Features (+6 more)

## Knowledge Gaps
- **38 isolated node(s):** `allow`, `allow`, `graphify`, `Commands`, `Files` (+33 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `log_action()` connect `Community 0` to `Community 1`, `Community 2`, `Community 4`?**
  _High betweenness centrality (0.425) - this node is a cross-community bridge._
- **Why does `Open Wealth Dashboard` connect `Community 10` to `Community 5`?**
  _High betweenness centrality (0.095) - this node is a cross-community bridge._
- **Are the 19 inferred relationships involving `log_action()` (e.g. with `analyze_stock()` and `extract_id_stocks()`) actually correct?**
  _`log_action()` has 19 INFERRED edges - model-reasoned connections that need verification._
- **What connects `allow`, `allow`, `Mendapatkan path file cache untuk ticker tertentu` to the rest of the system?**
  _115 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.06019871420222092 - nodes in this community are weakly interconnected._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.05649350649350649 - nodes in this community are weakly interconnected._
- **Should `Community 2` be split into smaller, more focused modules?**
  _Cohesion score 0.09686609686609686 - nodes in this community are weakly interconnected._