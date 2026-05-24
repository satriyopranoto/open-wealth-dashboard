# Action Logging — Implementation Plan

**Goal:** Add per-action logging to every feature in stocktrade app to track feature usage, stored as JSON-lines in a log file with daily rotation.

**Architecture:** A shared log_utils.py helper provides log_action() that writes structured JSON to logs/usage-YYYY-MM-DD.log. Each route handler calls it with feature name, action, parameters, result status, duration, and client IP.

**Tech Stack:** Python stdlib only — json, datetime, os, pathlib.

---

## Task 1: Create log_utils.py module

**Create:** stocktrade/log_utils.py

Write a module with:
- log_action(feature, action, params=None, status=success, duration_ms=None, detail=None, ip=None) — appends a JSON line to logs/usage-YYYY-MM-DD.log
  - Includes client IP origin for usage tracking
- _get_client_ip() — helper that extracts real IP from Flask request, handling X-Forwarded-For header for reverse proxy setups
- read_recent_logs(limit=50) — reads back recent entries
- Auto-creates logs/ directory
- Sanitizes long param values (>100 chars)
- Fails silently so logging never breaks the app

## Task 2: Add logging to index() and refresh_data()

**Modify:** stocktrade/app.py

- Add "from log_utils import log_action, _get_client_ip" at top
- index() — log landing_page / view
- refresh_data() — log with ticker param, timing, success/error on each return, include _get_client_ip()

## Task 3: Add logging to analyze_stock()

**Modify:** stocktrade/app.py

Log entry with ticker param + timing + IP. Log status on each return path (success + error paths).

## Task 4: Add logging to all 8 screener routes

**Modify:** stocktrade/app.py

For each screener route, log with params including market (ID/US) + client IP:
- most_active, day_gainers, net_net, acquirers_multiple (ID + US variants)

## Task 5: Add logging to extraction routes

**Modify:** stocktrade/app.py

Log in extract_us_stocks() and extract_id_stocks() with IP.
Skip SSE endpoints (extract/progress, extract/status).

## Task 6: Add logging to BB Breakout routes

**Modify:** stocktrade/app.py

Log in screener_us_bb_breakout(), screener_id_bb_breakout(), run_bb_screener().
Skip bb-progress SSE.

## Task 7: Add /logs viewer page (optional)

**Create:** templates/logs.html
**Modify:** stocktrade/app.py

New route GET /logs calling read_recent_logs() with template showing recent entries including IP.

---

**Log file location:** logs/usage-YYYY-MM-DD.log
**Not logged:** SSE progress endpoints (too noisy, called every second)
**Each log entry includes:** timestamp, feature, action, params, status, duration_ms, detail, ip
